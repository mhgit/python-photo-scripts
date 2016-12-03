import os
import sys

try:
    os.remove("./target/image-test-out-area/backup_store0035/store0035.tar.bz2")
except (IOError, os.error) as why:
    print 'No tar found to cleanup'
    sys.exit(0)

sys.exit()
