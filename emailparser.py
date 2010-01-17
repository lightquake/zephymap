#!/usr/bin/python
import imaplib, time, email.utils, email.parser, calendar


class EmailParser:
    def __init__(self, server, username, password, port=None, use_ssl=False, last_check=time.time()):
        self.server = server
        if not port:
            if use_ssl: self.port = 993
            else: self.port = 110
        else:
            self.port = port
        if use_ssl: self.imap = imaplib.IMAP4_SSL(self.server, self.port)
        else: self.imap = imaplib.IMAP4_SSL(self.server, self.port)
        self.imap.login(username, password)
        self.last_check = last_check

    def is_new(self, mail_string):
        """ Takes a string of the form
        
        Date: Sun, 17 Jan 2010 00:59:10 -0500 (EST)
        From: John Doe <anyman@example.com>
        Subject: TPS reports

        and returns whether that e-mail was received since last check.
        """
        date_header = get_field("Date", mail_string)
        date_tuple = email.utils.parsedate_tz(date_header)
        #timezone fuckery due to parsedate not interpreting other timezones properly
        time_received = calendar.timegm(date_tuple[0:8]) - date_tuple[9]
        return time_received > self.last_check
    

        
    def check(self):
        """
        Check for messages received since the last check.
        Return the number of unread messages.
        """
        folders = map(lambda x: x.split(' ')[2].strip('"'), self.imap.list()[1])
        headers = []
        
        for folder in folders:
            if "[Gmail]" in folder: continue
            if self.imap.select(folder, True)[0] == "NO": continue # open read-only
            throwaway, unseen = self.imap.search(None, 'UNSEEN')
            if unseen == ['']: continue
            indices = ','.join(unseen[0].split())
            print folder
            # for some reason, I get )s mixed in with actual header/response pair information.
            new_headers = [x[1] for x in self.imap.fetch(indices, "(BODY[HEADER.FIELDS (DATE FROM SUBJECT)])")[1] if x != ')' and self.is_new(x[1])]
            headers += new_headers
            
        self.last_check = time.time()
        return headers

def get_field(name, field_string):
    fields = filter(lambda x: x.startswith(name.capitalize() + ":"), field_string.split("\r\n"))
    if fields == []: return None
    else: return fields[0].lstrip(name.capitalize() + ": ")            
                
                
