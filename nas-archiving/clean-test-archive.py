import os
import sys

try:
    filename = "./target/image-test-out-area/backup_store0035/store0035.tar.bz2"
    os.remove(filename)
except (IOError, os.error) as why:
    print ('Nothing to clean: {}'.format(filename))


try:
    filename = "./target/image-test-out-area/backup_store0035/store0035.tar.bz2.md5"
    os.remove(filename)
except (IOError, os.error) as why:
    print ('Nothing to clean: {}'.format(filename))


sys.exit()
