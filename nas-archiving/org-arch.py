#!/usr/local/bin/python

# move files from one directory to another
# if files alrady exist there, they will be overwritten
# retains original file date/time

import os
import shutil

# make sure that these directories exist
dir_src = "/share/backup-jobs/aws-glacier"
dir_prefix = "backup_"
 
for file in os.listdir(dir_src):

  src_file = os.path.join(dir_src, file)

  if os.path.isdir(src_file):
    # skip directories
    continue

# Create a new location for the file based on its name
  index_of_dot = file.index('.') 
  file_no_ext = file[:index_of_dot]
    
  folder = os.path.join(dir_src, dir_prefix + file_no_ext)

  if not os.path.exists(folder):
    os.mkdir( folder, 0755 )

# Move the file to its new location
  dst_file = os.path.join(folder, file)

  if not os.path.isfile(dst_file):

    print 'From: ' + src_file
    print '  To: ' + dst_file

    shutil.move(src_file, dst_file)


