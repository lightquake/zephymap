import ConfigParser, os.path
import sys
from emailparser import EmailParser
import zephyr
import time


def group_by_id(things, f):
    f_dict = {}
    for f_val in list(set(map(f, things))):
        f_dict[f_val] = [thing for thing in things if f(thing) == f_val]
    return f_dict

config_file = "~/.zephymap.conf"
global_section = "zephyr"

zephyr.init()
scp = ConfigParser.SafeConfigParser()
if (scp.read(os.path.expanduser(config_file)) == []):
    print "Failed to read config file at %s." % config_file
    sys.exit(1)

servers = {}

target = scp.get(global_section, "recipient")
target_cls = "MAIL"
if scp.has_option(global_section, "class"):
    target_cls = scp.get(global_section, "class")

for section in scp.sections(): # loop through accounts
    if section == global_section: continue # zephyr is for globals
    username = scp.get(section, "username")
    password = scp.get(section, "password")
    server = scp.get(section, "server")
    # TODO: support other ports

    # determine whether to use ssl
    ssl = True
    if scp.has_option(section, "ssl") and not scp.getboolean(section, "ssl"):
        ssl = False
    
    servers[section] = EmailParser(server=server, username=username, password=password, use_ssl=ssl)    


while True:
    for server in servers:
        print "Checking server %s at %s." % (server, time.asctime())
        msgs = servers[server].check()
        msg_groups = group_by_id(msgs, lambda x: x["Message-ID"])
        print msgs
        for msg_id in msg_groups:
            msg_group = msg_groups[msg_id]
            folders = ','.join([msg["folder"] for msg in msg_group]) # all folders the message is in
            msg = msg_group[0] # the only difference is the folder, so 0 is as good as any
            instance_name = "%s.%s" % (server, folders) # gmail.INBOX
            zephyr.ZNotice(cls=target_cls, instance=instance_name, fields=["zephymap!",
                           "New mail from %s.\nSubject: %s" % (msg["From"], msg["Subject"])],
                           recipient=target, sender="zephymap", isPrivate=True).send()

    time.sleep(20)


