import os
import sys

# Run to setup test output folder.

_output_folder = "./target/image-test-out-area/"

try:
    if not os.path.isdir(_output_folder):
        os.makedirs(_output_folder)
        print(f"Folder init: [{_output_folder}]")
except OSError:
    print(f"Unable to create output folder: [{_output_folder}]")
    sys.exit(1)

print("Setup complete.")
sys.exit()
