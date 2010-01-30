#!/usr/bin/python

import ConfigParser, os.path
import sys
from emailhandler import EmailHandler
import zephyr
import time
import getpass
from threading import Thread
import logging

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
            body = "New mail from %s.\nSubject: %s" % (msg["From"], msg["Subject"])
            logger.info("Sending notification to instance %s, subject %s." % (instance_name, msg["Subject"]))
            zephyr.ZNotice(cls=target_class, instance=instance_name, fields=[msg_id, body],
                           recipient=target, sender="zephymap", isPrivate=True).send()
        

config_file = "~/.zephymap.conf"
global_section = "zephyr"
logger = logging.getLogger("zephymap")
logger.setLevel(logging.DEBUG)

def load_config():
    """
    Load handlers and other appropriate state.
    Returns a dict of handler identifier -> EmailHandler object
    """
    # globals shared among all handlers
    global target_class
    global target

    scp = ConfigParser.SafeConfigParser({"regex": ".*"})

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

    # loop through each account
    for section in scp.sections():
        if section == global_section: continue # zephyr is for globals
        
        logger.info("Parsing section %s." % section)
        username = scp.get(section, "username")
        server = scp.get(section, "server")
        if scp.has_option(section, "password"):
            password = scp.get(section, "password")
        else:
            password = getpass.getpass("Password for server %s, username %s: " % (server, username))
            
        # determine whether to use ssl; defaults to yes
        # TODO: support other ports
        ssl = True
        if scp.has_option(section, "ssl") and not scp.getboolean(section, "ssl"):
            ssl = False

        logger.debug("Constructing handler for section %s: server %s, username %s, ssl %s"
                     % (section, server, username, ssl))
        handlers[section] = EmailHandler(server=server, username=username, password=password, use_ssl=ssl)

    return handlers    
        

def group(things, f):
    f_dict = {}
    f_vals = list(set(map(f, things))) # unique values of f[thing]
    for f_val in f_vals:
        f_dict[f_val] = filter(lambda x: f(x) == f_val, things)
    return f_dict


if __name__ == "__main__":
    root_logger = logging.getLogger()
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)

    # strictly, I should pad to the longest thread name length, but that would require me to
    # know that information before I print anything out, and I want to print when I'm loading
    # a config file.
    ch.setFormatter(logging.Formatter("%(asctime)s - %(name)20s - %(levelname)5s - %(message)s"))
    root_logger.addHandler(ch)

    logger.info("Initializing zephyr.")
    zephyr.init()
    handlers = load_config()

    for name in handlers:
        t = EmailThread(handlers[name], name, 20)
        t.start()
