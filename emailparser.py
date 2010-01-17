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
        time_received = calendar.timegm(date_tuple[0:8]) - date_tuple[9]
        return time_received > self.last_check
    

        
    def check(self):
        """
        Check for messages received since the last check.
        Return the number of unread messages.
        """
        folders = map(lambda x: x.split(' ')[2].strip('"'), self.imap.list()[1])
        notifications = []
        for folder in folders:
            if "[Gmail]" in folder: continue
            if self.imap.select(folder, True)[0] == "NO": continue # open read-only
            response, unseen = self.imap.search(None, 'UNSEEN')
            indices = unseen[0].split()
            nmessages = len(indices)
            i = nmessages - 1
            while i >= 0:
                # Fetch the received date and remove the preceding 'Date: '
                rfc2822 = self.imap.fetch(indices[i], '(BODY[HEADER.FIELDS (DATE)])')[1][0][1][6:]
                time_received = time.mktime(email.utils.parsedate(rfc2822))
                if time_received + 10 * 60 < self.last_check:
                    break
                sender = self.imap.fetch(indices[i], '(BODY[HEADER.FIELDS (FROM)])')[1][0][1][6:-4]
                subject = self.imap.fetch(indices[i], '(BODY[HEADER.FIELDS (SUBJECT)])')[1][0][1][9:-4]
                notifications.append({"sender" : sender, "subject" : subject})
                i -= 1
        self.last_check = time.time()
        return notifications

def get_field(name, field_string):
    fields = filter(lambda x: x.startswith(name.capitalize() + ":"), field_string.split("\r\n"))
    if fields == []: return None
    else: return fields[0].lstrip(name.capitalize() + ": ")            
                
                
