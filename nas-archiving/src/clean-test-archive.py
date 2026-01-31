import os
import sys

try:
    filename = "./target/image-test-out-area/backup_store0035/store0035.tar.bz2"
    os.remove(filename)
except OSError:
    print(f"Nothing to clean: {filename}")


try:
    filename = "./target/image-test-out-area/backup_store0035/store0035.tar.bz2.md5"
    os.remove(filename)
except OSError:
    print(f"Nothing to clean - legacy md5: {filename}")


try:
    filename = "./target/image-test-out-area/backup_store0035/store0035.tar.bz2.sha256"
    os.remove(filename)
except OSError:
    print(f"Nothing to clean: {filename}")


sys.exit()
