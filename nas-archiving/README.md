Python Scripts
==============

nas-archiving
-------------

**Description**

Scripts to manage the creation of image storage archives that can be exported to glacier.

**setup.py:** Before building or testing run the script which will create a target
folder for creating the archive into.

**clean-test-archive.py:** The create-glacier-archive.py is designed not to overwrite an existing archive.  On a nas a large archive can create a long time to build.  There is no force function the user has to remove the archive deliberately outside the script.  This script will clean the test output and can be called before running the script during testing to clear down.  In pycharm you can add a runner for this and call that from any test runners.

**create-glacier-archive.py:** Install this script on a nas to create a tar suitable for uploading to glacier.  Pass -h to see the instructions.  The idea behind it is to only take image files into the archive.  Ignores any os files or thumbnails etc.

