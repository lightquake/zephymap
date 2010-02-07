#!/usr/bin/python

import ConfigParser, os.path
import sys
from emailhandler import EmailHandler
import zephyr
import time
import getpass
from threading import Thread
import logging
import re
import getopt

version = "0.1"
config_file = "~/.zephymap.conf"
global_section = "zephyr"
logger = logging.getLogger("zephymap")
logger.setLevel(logging.DEBUG)
default_interval = 20
usage = """
usage: zephymap.py [-v|-V]
must have a ~/.zephymap.conf file. 
For configuration and installation instructions, see the README.
"""

class EmailThread(Thread):
    def __init__(self, handler, name, interval=20):
        Thread.__init__(self, name=name)
        self.handler = handler
        self.interval = interval
        self.logger = logging.getLogger("zephymap.%s" % name)

    def run(self):
        while True:
            self.check()
            time.sleep(self.interval)

    def check(self):
        logger = self.logger
        logger.info("Checking for messages.")
        msgs = self.handler.check() # grab message headers
        # some e-mail providers support tagging, resulting in dupe messages
        # in folders. we only want to notify once, so we group by message ID.
        msg_groups = group(msgs, lambda x: x["Message-ID"])
        n_mesgs = len(msg_groups)
        logger.info("%d message%s." % (n_mesgs,  "" if n_mesgs == 1 else "s"))
        
        for msg_id in msg_groups:
            msg_group = msg_groups[msg_id]
            folders = ','.join([msg["folder"] for msg in msg_group]) # all folders the message is in
            msg = msg_group[0] # the only difference is the folder, so 0 is as good as any
            instance_name = "%s.%s" % (self.getName(), folders) # e.g., Gmail.INBOX
            body = """
You have new mail in %s.

From: %s
Subject: %s
To: %s
""".strip() % (instance_name, msg["From"], msg["Subject"], msg["To"])
            logger.info("Sending notification to instance %s, subject %s." % (instance_name, msg["Subject"]))
            zephyr.ZNotice(cls=target_class, instance=instance_name, fields=[msg_id, body],
                           recipient=target, sender="zephymap", isPrivate=True).send()
        

def load_config():
    """
    Load handlers and other appropriate state.
    Returns a dict of handler identifier -> EmailHandler object
    """
    # globals shared among all handlers
    global target_class
    global target
    global default_interval

    scp = ConfigParser.SafeConfigParser()

    # bail on a bad read
    logger.info("Loading config.")
    if (scp.read(os.path.expanduser(config_file)) == []):
        print "Failed to read config file at %s." % config_file
        sys.exit(1)

    handlers = {}

    target = scp.get(global_section, "recipient")
    target_class = "MAIL"
    if scp.has_option(global_section, "class"):
        target_class = scp.get(global_section, "class")

    if scp.has_option(global_section, "interval"):
        default_interval = scp.getint(global_section, "interval")

    # loop through each account
    for section in scp.sections():
        if section == global_section: continue # zephyr is for globals
        
        logger.info("Parsing section %s." % section)
        kwargs = {}
        kwargs['username'] = username = scp.get(section, "username")
        kwargs['server'] = server = scp.get(section, "server")
        if scp.has_option(section, "password"):
            password = scp.get(section, "password")
        else:
            password = getpass.getpass("Password for server %s, username %s: " % (server, username))

        kwargs['password'] = password
            
        # determine whether to use ssl; defaults to yes
    
        if scp.has_option(section, "ssl") and not scp.getboolean(section, "ssl"):
            ssl = False
            default_port = 143
        else:
            ssl = True
            default_port = 993

        kwargs['use_ssl'] = ssl

        if scp.has_option(section, "port"):
            port = scp.getint("port")
        else:
            port = default_port

        kwargs['port'] = port

        if scp.has_option(section, "interval"):
            interval = scp.getint(section, "interval")
        else:
            interval = default_interval

        interval = max(interval, 10) # don't want to be constantly checking.


        if scp.has_option(section, "regex"):
            is_regex = scp.get(section, "regex")
        else:
            is_regex = False

        if scp.has_option(section, "include"):
            include = scp.get(section, "include")
            if is_regex: include_re = include
            else: include_re = clude_to_re(include)
        else: include_re = "^.*$"

        if scp.has_option(section, "exclude"):
            exclude = scp.get(section, "exclude")
            if is_regex: exclude_re = exclude
            else: exclude_re = clude_to_re(exclude)
        else: exclude_re = "^$"

        kwargs['include'] = include_re
        kwargs['exclude'] = exclude_re

        
        logger.debug("Constructing handler for section %s: server %s, username %s, ssl %s, port %d, interval %d, is_regex %s, include_re %s, exclude_re %s."
                     % (section, server, username, ssl, port, interval, is_regex, include_re, exclude_re))
        handlers[section] = EmailHandler(**kwargs)
        handlers[section].interval = interval

    return handlers    
        

def group(things, f):
    f_dict = {}
    f_vals = list(set(map(f, things))) # unique values of f[thing]
    for f_val in f_vals:
        f_dict[f_val] = filter(lambda x: f(x) == f_val, things)
    return f_dict

def clude_to_re(s):
    elements = s.split(";")
    regexified = [r'(^%s(/.*)?$)' % re.escape(elem.strip()) for elem in elements]
    return "|".join(regexified)
    

if __name__ == "__main__":
    root_logger = logging.getLogger()
    ch = logging.StreamHandler()

    ch.setLevel(logging.WARN)

    try:
        opts, args = getopt.getopt(sys.argv[1:], "vV", ["help", "version"])
    except getopt.GetoptError, e: # Unknown option passed
        print str(e)
        print usage
        sys.exit(2)
    for o, a in opts:
        if o == "-v": ch.setLevel(logging.INFO)
        elif o == "-V": ch.setLevel(logging.DEBUG)
        elif o == "--help":
            print usage
            sys.exit()
        elif o == "--version":
            print version
            sys.exit()
        else:
            assert False, "unknown, unhandled option"

    # strictly, I should pad to the longest thread name length, but that would require me to
    # know that information before I print anything out, and I want to print when I'm loading
    # a config file.
    ch.setFormatter(logging.Formatter("%(asctime)s - %(name)20s - %(levelname)8s - %(message)s"))
    root_logger.addHandler(ch)

    logger.info("Initializing zephyr.")
    zephyr.init()
    handlers = load_config()

    for name in handlers:
        t = EmailThread(handlers[name], name, handlers[name].interval)
        t.start()
