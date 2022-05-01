import os
import sys

# Run to setup test output folder.

_output_folder = "./target/image-test-out-area/"

try:
    if not os.path.isdir(_output_folder):
        os.makedirs(_output_folder)
        print ('Folder init: [{}]'.format(_output_folder))
except (IOError, os.error) as why:
    print ('Unable to create output folder: [{}]'.format(_output_folder))
    sys.exit(1)

print ('Setup complete.')
sys.exit()
