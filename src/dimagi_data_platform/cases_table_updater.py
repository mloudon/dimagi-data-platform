'''
Created on Jun 17, 2014

@author: mel
'''


from dimagi_data_platform.standard_table_updater import StandardTableUpdater


class CasesTableUpdater(StandardTableUpdater):
    '''
    updates the user table from form data
    '''

    def __init__(self, dbconn, domain):
        '''
        Constructor
        '''
        self.domain = domain
        super(CasesTableUpdater, self).__init__(dbconn)
        
    def update_table(self):
        with self.conn.cursor() as curs:
            curs.execute("delete from cases where domain like '%s'" % self.domain)
            curs.execute("insert into cases (case_id, user_id, owner_id, parent_id, case_type, date_opened, date_modified, closed, date_closed, domain) "
                             "(select case_id, a.id as user_id, b.id as owner_id, parent_id, case_type, date_opened, date_modified, closed, date_closed, incoming_cases.domain "
                             "from incoming_cases, users as a, users as b where a.user_id = incoming_cases.user_id and b.user_id = incoming_cases.owner_id "
                             " and incoming_cases.domain like '%s' "
                             "group by case_id, a.id, b.id, parent_id, case_type, date_opened, date_modified, closed, date_closed, incoming_cases.domain);" % (self.domain))
        
        