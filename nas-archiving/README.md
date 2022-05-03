Nas Photo Archiving Scripts
==============

nas-archiving
-------------

**Description**

Scripts to manage the creation of image storage archives.  Originally written to tar and validate the important files before exporting to glacier.  An MD5 can be produced for checking after a restore.

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

