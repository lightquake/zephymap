#!/usr/bin/python

import ConfigParser, os.path
import sys
from emailhandler import EmailHandler
import zephyr
import time
import getpass
from threading import Thread

class EmailThread(Thread):
    def __init__(self, handler, interval=20):
        Thread.__init__(self)
        self.handler = handler
        self.interval = interval

    def run(self):
        while True:
            check_handler(self.handler)
            time.sleep(self.interval)

config_file = "~/.zephymap.conf"
global_section = "zephyr"

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

        handlers[section] = EmailHandler(server=server, username=username, password=password, use_ssl=ssl)

    return handlers    

def check_handler(handler):
    """
    Check the handler with the given name and send zephyrs as appropriate.
    """

    print "Checking handler %s at %s." % (handler, time.asctime())
    msgs = handlers[handler].check() # grab message headers
    # some e-mail providers support tagging, resulting in dupe messages
    # in folders. we only want to notify once, so we group by message ID.
    msg_groups = group(msgs, lambda x: x["Message-ID"])
    n_mesgs = len(msg_groups)
    print "%d message%s." % (n_mesgs,  "" if n_mesgs == 1 else "s")
    for msg_id in msg_groups:
        msg_group = msg_groups[msg_id]
        folders = ','.join([msg["folder"] for msg in msg_group]) # all folders the message is in
        msg = msg_group[0] # the only difference is the folder, so 0 is as good as any
        instance_name = "%s.%s" % (handler, folders) # e.g., Gmail.INBOX
        body = "New mail from %s.\nSubject: %s" % (msg["From"], msg["Subject"])
        zephyr.ZNotice(cls=target_class, instance=instance_name, fields=[msg_id, body],
                       recipient=target, sender="zephymap", isPrivate=True).send()
        

def group(things, f):
    f_dict = {}
    f_vals = list(set(map(f, things))) # unique values of f[thing]
    for f_val in f_vals:
        f_dict[f_val] = filter(lambda x: f(x) == f_val, things)
    return f_dict


if __name__ == "__main__":
    zephyr.init()
    handlers = load_config()

    for handler in handlers:
        t = EmailThread(handler, 20)
        t.start()
