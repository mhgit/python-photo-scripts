Nas Photo Archiving Scripts
==============

nas-archiving
-------------

**Description**

Scripts to manage the creation of file storage archives.  Builds a tar archive and validate files.  The archive can then be uploaded to glacier or similar, but your responsible what what you do next.  An MD5 is be produced for checking after a restore.

**setup.py:** Before building or testing run the script which will create a target
folder for creating the archive into.

**clean-test-archive.py:** The create-glacier-archive.py is designed not to overwrite an existing archive.  On a nas a large archive can create a long time to build.  There is no force function the user has to remove the archive deliberately outside the script.  This script will clean the test output and can be called before running the script during testing to clear down.  In pycharm you can add a runner for this and call that from any test runners.

**The main script.**

**create-glacier-archive.py:** Creates a tar suitable for uploading to glacier.  Pass -h to see the instructions.  The idea behind it is to only take image files into the archive.  Ignores any os files or thumbnails etc.

In addition, the script has facilities for checking and validating the archive and buddy md5 file.

**Details**

Creates a tar cleaned of all files we do not want to send to offline archive.

Ignores symbolic links

Ignored patterns: \[('*.DS_Store', '*.@__thumb', '*@Transcode')]

Flags: 

 \[-h]                  - Show the help
 
 \[-l | list-only]      - Dry run list file operations.
 
 \[-c | check-contents] - Validate archive contents against original files.
 
 \[-s | summary]        - Summary report
 
 \[-v | verbose]
  
 \[-i | input-dir]
  
 \[-o | output-dir]
 
 \[check-md5]           - read in the buddy md5 file and check it against a hash of the tar.


**Testing**
The project contains some small test images and some folders to use during manual testing.  Commands:

# Dry run
python src/create-glacier-archive.py -vsl -i test-files/image-test-in-area/share/Multimedia-enc/pictures/Archive_PS1/store0035/ -o target/image-test-out-area/backup_store0035

# Create the test archive
python src/create-glacier-archive.py -vsc -i test-files/image-test-in-area/share/Multimedia-enc/pictures/Archive_PS1/store0035/ -o target/image-test-out-area/backup_store0035
