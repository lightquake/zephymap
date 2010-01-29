#!/usr/bin/python
import imaplib, time, email.utils, email, calendar
import re
from socket import sslerror
from sys import stderr

class EmailHandler:
    def __init__(self, server, username, password, port=None, use_ssl=False, last_check=time.time(), regex=".*"):
        self.server = server
        if not port:
            if use_ssl: self.port = 993
            else: self.port = 143
        else:
            self.port = port
        if use_ssl: self.imap = imaplib.IMAP4_SSL(self.server, self.port)
        else: self.imap = imaplib.IMAP4(self.server, self.port)
        self.username = username
        self.password = password
        self.imap.login(self.username, self.password)
        self.last_check = last_check
        self.regex = regex
        self.set_last_uids()
        
        
    def set_last_uids(self):
        self.last_uid = {}
        for folder in self.get_folders():
            if "[Gmail]" in folder: continue
            selection = self.imap.select(folder, True) # open read-only
            if selection[0] == "NO": continue
            if selection[1][0] == '0':
                self.last_uid[folder] = 0
                continue
            last_msgid = selection[1][0]
            uid_text = self.imap.fetch(last_msgid, "UID")[1][0]
            self.last_uid[folder] = int(re.search("\(UID (\d+)\)", uid_text).group(1))
            
    def get_folders(self):
        # folders are indicated like (\\HasNoChildren) "." "INBOX.Foo"; we just want INBOX.Foo
        folder_re = re.compile(r'\(.*?\) ".*" (?P<name>.*)')
        predicate_re = re.compile(self.regex)
        folders = [folder_re.match(f_str).groups()[0].strip('"')
                for f_str in self.imap.list()[1]]
        return [f for f in folders if predicate_re.match(f)]
    
    def check(self):
        """
        Check for messages received since the last check.
        Return the number of unread messages.
        """
        headers = []
        try:
            for folder in self.get_folders():
                if "[Gmail]" in folder: continue
                response, [nmesgs] = self.imap.select(folder, True)  # open read-only
                if response == "NO": continue
                # XXX: large number is because * will always return the last message
                throwaway, new = self.imap.search(None, 'UNSEEN', "(UID %d:99999999)" % (self.last_uid[folder] + 1))
                if new == ['']: continue # skip all-read folders
                print "Checking folder %s at %s." % (folder, time.asctime())
                indices = ','.join(new[0].split(' '))

                # for some reason, I get )s mixed in with actual header/response pair information.
                new_headers = [email.message_from_string(x[1]) for x in self.imap.fetch(indices, "(BODY[HEADER])")[1] if x != ')']
                for new_header in new_headers: new_header["folder"] = folder
                headers += new_headers
                uid_text = self.imap.fetch(nmesgs, "UID")[1][0]
                self.last_uid[folder] =  int(re.search("\(UID (\d+)\)", uid_text).group(1))
                
        except (imaplib.IMAP4.abort, sslerror), e:
            # Okay. There's this stupid bug in the SSL library that I don't feel like finding the cause of
            # that means that sometimes I get a random EOF. I don't know what state it leaves the connection
            # in, so just reinitialize everything.
            # Also, sometimes imaplib will just randomly abort. Again, fuck it and reinitialize.
            if isinstance(e, sslerror) and e[0] != 8:
                raise

            if isinstance(self.imap, imaplib.IMAP4_SSL):
                self.imap = imaplib.IMAP4_SSL(self.server)
            else:
                self.imap = imaplib.IMAP4(self.server)
            self.imap.login(self.username, self.password)
            if isinstance(e, sslerror):
                print >> stderr, "SSL bug in server %s at %s." % (self.server, time.asctime())
            elif isinstance(e, imaplib.IMAP4.abort):
                print >> stderr, "abort bug in server %s at %s." % (self.server, time.asctime())
            return self.check()
            
            
        return headers
