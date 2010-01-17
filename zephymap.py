import ConfigParser, os.path
import sys
from emailparser import EmailParser
import zephyr

config_file = "~/.zephymap.conf"

zephyr.init()
scp = ConfigParser.SafeConfigParser()
if (scp.read(os.path.expanduser(config_file)) == []):
    print "Failed to read config file at %s." % config_file
    sys.exit(1)

servers = {}

target = scp.get("zephyr", "recipient")

for section in scp.sections(): # loop through accounts
    if section == "zephyr": continue # zephyr is for globals
    username = scp.get(section, "username")
    password = scp.get(section, "password")
    server = scp.get(section, "server")
    # TODO: support other ports

    # determine whether to use ssl
    ssl = scp.has_option(section, "ssl") and scp.getboolean(section, "ssl")
    
    servers[section] = EmailParser(server=server, username=username, password=password, use_ssl=ssl)    


while True:
    for server in servers:
        msgs = servers[server].check()
        for msg in msgs:
            print msg
            zephyr.ZNotice(cls="zephymap", instance=msg["folder"], fields=["zephymap!", "New mail from %s." % msg["from"]],
                           recipient=target, sender="zephymap", isPrivate=True).send()

    time.sleep(30)
