#!/usr/bin/python

import ConfigParser, os.path
import sys
from emailhandler import EmailHandler
import zephyr
import time
import getpass
from threading import Thread

config_file = "~/.zephymap.conf"
global_section = "zephyr"

def load_servers():
    global target_class
    global target
    
    scp = ConfigParser.SafeConfigParser({"regex": ".*"})
    if (scp.read(os.path.expanduser(config_file)) == []):
        print "Failed to read config file at %s." % config_file
        sys.exit(1)

    servers = {}

    target = scp.get(global_section, "recipient")
    target_class = "MAIL"
    if scp.has_option(global_section, "class"):
        target_class = scp.get(global_section, "class")

    for section in scp.sections(): # loop through accounts
        if section == global_section: continue # zephyr is for globals
        username = scp.get(section, "username")
        server = scp.get(section, "server")
        if scp.has_option(section, "password"):
            password = scp.get(section, "password")
        else:
            password = getpass.getpass("Password for server %s, username %s: " % (server, username))
        regex = scp.get(section, "regex")
        # TODO: support other ports

        # determine whether to use ssl
        ssl = True
        if scp.has_option(section, "ssl") and not scp.getboolean(section, "ssl"):
            ssl = False

        servers[section] = EmailHandler(server=server, username=username, password=password, use_ssl=ssl, regex=regex)

    return servers      

def check_server(server):
    print "Checking server %s at %s." % (server, time.asctime())
    msgs = servers[server].check()
    msg_groups = group_by_id(msgs, lambda x: x["Message-ID"])
    n_mesgs = len(msg_groups)
    print "%d message%s." % (n_mesgs,  "" if n_mesgs == 1 else "s")
    for msg_id in msg_groups:
        msg_group = msg_groups[msg_id]
        folders = ','.join([msg["folder"] for msg in msg_group]) # all folders the message is in
        msg = msg_group[0] # the only difference is the folder, so 0 is as good as any
        instance_name = "%s.%s" % (server, folders) # gmail.INBOX
        body = "New mail from %s.\nSubject: %s" % (msg["From"], msg["Subject"])
        zephyr.ZNotice(cls=target_class, instance=instance_name, fields=[msg_id, body],
                       recipient=target, sender="zephymap", isPrivate=True).send()
def check_loop(server):
    while True:
        check_server(server)
        time.sleep(20)
        

def group_by_id(things, f):
    f_dict = {}
    for f_val in list(set(map(f, things))):
        f_dict[f_val] = [thing for thing in things if f(thing) == f_val]
    return f_dict


if __name__ == "__main__":
    zephyr.init()
    servers = load_servers()

    for server in servers:
        t = Thread(target=check_loop, args=(server,))
        t.start()
