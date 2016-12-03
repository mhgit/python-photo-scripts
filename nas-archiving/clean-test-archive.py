import os

try:
    os.remove("../../image-test-out-area/backup_store0035/store0035.tar.bz2")
except (IOError, os.error) as why:
    print 'No tar found to cleanup'



