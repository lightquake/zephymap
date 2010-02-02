#!/usr/bin/python
import imaplib, email.utils, email, calendar, time
import re
from socket import sslerror
from sys import stderr
import logging

logger = logging.getLogger("emailhandler")
logger.setLevel(logging.DEBUG)

class EmailHandler:
    def __init__(self, server, username, password, port=None, use_ssl=False, include=".*", exclude="^$"):
        self.server = server
        if not port: # default ports
            if use_ssl: self.port = 993
            else: self.port = 143
        else:
            self.port = port
        if use_ssl: self.imap = imaplib.IMAP4_SSL(self.server, self.port)
        else: self.imap = imaplib.IMAP4(self.server, self.port)
        self.username = username
        self.password = password
        self.imap.login(self.username, self.password)

        self.include = re.compile(include, re.I)
        self.exclude = re.compile(exclude, re.I)
        self.set_last_uids()
        
        
    def set_last_uids(self):
        """
        Set the last-seen UIDs for each folder.
        """
        
        self.last_uid = {}
        for folder in self.get_folders():
            if "[Gmail]" in folder: continue # Avoid checking Gmail's special folders.
            selection = self.imap.select(folder, True) # open read-only
            if selection[0] == "NO": continue
            last_msgid = selection[1][0]
            if last_msgid == '0': # No messages found.
                self.last_uid[folder] = 0
                continue
            uid_text = self.imap.fetch(last_msgid, "UID")[1][0] # looks like (UID 1234)
            self.last_uid[folder] = int(re.search("\(UID (\d+)\)", uid_text).group(1))
            
    def get_folders(self):
        """
        Get the list of folders.
        """
        # folders are indicated like (\\HasNoChildren) "." "INBOX.Foo"; we just want INBOX.Foo.
        # that middle thing is a separator, which we can ignore since we don't care about nesting.
        folder_re = re.compile(r'\(.*?\) "(?P<sep>.*)" (?P<name>.*)')
        matches = [folder_re.match(f_str).groups() for f_str in self.imap.list()[1]]
        logger.debug("Found folders %s." % [match[1] for match in matches])
        canonical_folders = [match[1].strip('"').replace(match[0], "/") for match in matches]
        matching_folders = [folder for folder in canonical_folders
                            if self.include.search(folder) and not self.exclude.search(folder)]
        logger.debug("Matched folders %s." % matching_folders)
        return matching_folders

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
                logger.info("Checking folder %s on server %s." % (folder, self.server))

                indices = new[0].replace(' ', ',') # it gives me '2 3 4', but it requires '2,3,4'. god I hate IMAP.
                
                # for some reason, I get )s mixed in with actual header/response pair information.
                new_headers = [email.message_from_string(x[1]) for x in self.imap.fetch(indices, "(BODY[HEADER])")[1] if x != ')']
                logger.info("Found %d message%s in folder %s on server %s." % (len(new_headers), "" if len(new_headers) == 1 else "s",
                                                                               folder, self.server))
                for new_header in new_headers: new_header["folder"] = folder # tag with folder information
                headers += new_headers
                uid_text = self.imap.fetch(nmesgs, "UID")[1][0] # mark that we read the UID
                self.last_uid[folder] = int(re.search("\(UID (\d+)\)", uid_text).group(1))
                
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
                logger.warning("SSL bug in server %s at %s." % (self.server, time.asctime()))
            elif isinstance(e, imaplib.IMAP4.abort):
                logger.warning("abort bug in server %s at %s." % (self.server, time.asctime()))

            # Try it again
            return self.check()
            
            
        return headers
