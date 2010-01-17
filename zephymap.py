import ConfigParser, os.path
import sys
import imaplib

config_file = "~/.zephymap.conf"

scp = ConfigParser.SafeConfigParser()
if (scp.read(os.path.expanduser(config_file)) == []):
    print "Failed to read config file at %s." % config_file
    sys.exit(1)

servers = {}

# TODO: global settings
for section in scp.sections(): # loop through accounts
    username = scp.get(section, "username")
    password = scp.get(section, "password")
    server = scp.get(section, "server")
    # TODO: support other ports

    # determine whether to use
    if scp.has_option(section, "ssl") and scp.getboolean(section, "ssl"):
        constructor = imaplib.IMAP4_SSL
    else:
        constructor = imaplib.IMAP4
   
    imap = constructor(server)
    imap.login(username, password)
    servers[section] = imap
    
def check(server):
    # grab the folder list. I'm truly sorry for this code.
    folders = map(lambda x: x.split(' ')[2].strip('"'), server.list()[1])
    unread = {}
    for folder in folders:
        if server.select(folder)[0] == "NO": continue
        unseens = server.search(None, "UNSEEN")[1][0]
        n_unseen = len(unseens.split(' '))
        unread[folder] = n_unseen

    return unread
