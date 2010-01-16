import ConfigParser, os.path
import sys
import imaplib
config_file = "~/.zephymap.conf"
scp = ConfigParser.SafeConfigParser()
if (scp.read(os.path.expanduser(config_file)) == []):
    print "Failed to read config file at %s." % config_file
    sys.exit(1)
