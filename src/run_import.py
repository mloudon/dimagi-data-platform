'''
Created on Jun 8, 2014

@author: mel
'''
import datetime
import getpass
import logging

from commcare_export.commcare_hq_client import CommCareHqClient

from dimagi_data_platform import incoming_data_tables, data_warehouse_db, conf
from dimagi_data_platform.data_warehouse_db import Domain
from dimagi_data_platform.extractors import ExcelExtractor, \
    CommCareExportCaseExtractor, CommCareExportFormExtractor, \
    CommCareExportUserExtractor, CommCareExportDeviceLogExtractor, \
    CommCareExportWebUserExtractor, \
    CommCareSlumberFormDefExtractor, CommCareExportExtractor
from dimagi_data_platform.incoming_data_tables import IncomingDomain, \
    IncomingDomainAnnotation, IncomingFormAnnotation, IncomingForm, \
    IncomingCases, IncomingDeviceLog
from dimagi_data_platform.loaders import DomainLoader, \
    UserLoader, FormLoader, CasesLoader, CaseEventLoader, \
    VisitLoader, FormDefLoader, WebUserLoader, DeviceLogLoader
from dimagi_data_platform.utils import get_domains, configure_logger


logger = logging.getLogger('dimagi_data_platform')
db = conf.PEEWEE_DB_CON
        
def setup():
    configure_logger(logger)
    incoming_data_tables.create_missing_tables()
    data_warehouse_db.create_missing_tables()
    
def update_hq_admin_data():
    '''
    update domains, form definitions, and anything else that is not extracted per-domain from APIs
    '''
    importers = []
    importers.append(ExcelExtractor(IncomingDomain, "domains.xlsx"))
    importers.append(ExcelExtractor(IncomingDomainAnnotation, "domain_annotations.xlsx"))
    importers.append(ExcelExtractor(IncomingFormAnnotation, "form_annotations.xlsx"))
    
    for importer in importers:
        importer.do_extract()
    
    table_updaters = []
    table_updaters.append(DomainLoader())
        
    for table_updater in table_updaters:
        table_updater.do_load()
        
    for importer in importers:
            importer.do_cleanup()

@db.commit_on_success            
def update_for_domain(dname, password):
    d = Domain.get(name=dname)
    since = d.last_hq_import
    
    extracters = []
    extracters.append(CommCareExportCaseExtractor(since, dname))
    extracters.append(CommCareExportFormExtractor(since, dname))
    extracters.append(CommCareExportUserExtractor(since, dname))
    extracters.append(CommCareExportWebUserExtractor(since, dname))
    extracters.append(CommCareExportDeviceLogExtractor(since, dname))   
    extracters.append(CommCareSlumberFormDefExtractor('v0.5', dname, conf.CC_USER, password))        

    logger.info('TIMESTAMP starting commcare export for domain %s %s' % (d.name, datetime.datetime.now()))
    api_client = CommCareHqClient('https://www.commcarehq.org',dname,version='0.5').authenticated(conf.CC_USER, password)
    
    for extracter in extracters:
        if (isinstance(extracter, CommCareExportExtractor)):
            extracter.set_api_client(api_client)
        extracter.do_extract()
        
    d.last_hq_import = datetime.datetime.now()
    d.save()
    
    loaders = []
    # these loaders should run even if there are no new forms, cases or device logs
    loaders.append(UserLoader(dname))
    loaders.append(FormDefLoader(dname))
    loaders.append(WebUserLoader(dname))
    
    forms_to_import = IncomingForm.get_unimported(dname).count()
    cases_to_import = IncomingCases.get_unimported(dname).count()
    device_logs_to_import = IncomingDeviceLog.get_unimported(dname).count()
    
    if (cases_to_import > 0):
        logger.info('We have %d cases to import' % cases_to_import)
        loaders.append(CasesLoader(dname))
        
    if (forms_to_import > 0):
        logger.info('We have %d forms to import' % forms_to_import)
        loaders.append(FormLoader(dname))
        loaders.append(CaseEventLoader(dname))
        loaders.append(VisitLoader(dname))
    
    if (device_logs_to_import > 0):
        logger.info('We have %d device log entries to import' % device_logs_to_import)
        loaders.append(DeviceLogLoader(dname))
        
    logger.info('TIMESTAMP starting standard table updates for domain %s %s' % (d.name, datetime.datetime.now()))
    
    for loader in loaders:
        loader.do_load()
        
    for extracter in extracters:
        extracter.do_cleanup()
            
def update_for_domains(domainlist, password):
    '''
    update per-domain data for domains in domainlist, using given HQ password and username specified in config_sys.json for API calls.
    '''   
    for dname in domainlist:
        try:
            update_for_domain(dname, password)
                
        except Exception, e:
                logger.error('DID NOT FINISH IMPORT/UPDATE FOR DOMAIN %s ' % dname)
                logger.exception(e)

        
def main():
        logger.info('TIMESTAMP starting run %s' % datetime.datetime.now())
        setup()
        password = getpass.getpass()
        
        logger.info('TIMESTAMP updating hq admin data - domains, forms definitions %s' % datetime.datetime.now())
        update_hq_admin_data()
        domain_list = get_domains(conf.RUN_CONF_JSON)
        
        logger.info('TIMESTAMP starting domain updates %s' % datetime.datetime.now())
        logger.info('domains for run are: %s' % ','.join(domain_list))
        update_for_domains(domain_list, password)
    
if __name__ == '__main__':
    main()

