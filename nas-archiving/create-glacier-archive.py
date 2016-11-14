#!/usr/local/bin/python

# move files from one directory to another
# if files alrady exist there, they will be overwritten
# retains original file date/time

import os
import shutil
import sys, getopt

# make sure that these directories exist
dirToDefault = "/share/backup-jobs/aws-glacier"
dirToPrefix = "backup_"

# From folder probably needs to come in from a parameter.
# Next step, logon and test.  Pass in and check all parsing

def main(argv):
   dirFrom = ''
   dirTo = ''
   try:
      opts, args = getopt.getopt(argv, "hd:o:", ["input-dir=","output-dir="])
   except getopt.GetoptError:
      print 'org-arc.py -d <input director> -o <output directory>'
      sys.exit(2)

   for opt, arg in opts:
      if opt == '-h':
         print "opt [%], arg [%]" % (opt, arg)
         print sys.argv[0] + ' -d <input directory>'
         sys.exit()

      elif opt in ("-o", "--output-dir"):
         dirTo = arg

      elif opt in ("-d", "--input-dir"):
         dirFrom = arg

   if dirTo == '':
      dirTo = dirToDefault

   print 'input  directory is [%s]' % dirFrom
   print 'output directory is [%s]' % dirTo

if __name__ == "__main__":
   main(sys.argv[1:])

# moving files
def copytree(src, dst, symlinks=False, ignore=None):
    names = os.listdir(src)
    if ignore is not None:
        ignored_names = ignore(src, names)
    else:
        ignored_names = set()

    os.makedirs(dst)
    errors = []
    for name in names:
        if name in ignored_names:
            continue
        srcname = os.path.join(src, name)
        dstname = os.path.join(dst, name)
        try:
            if symlinks and os.path.islink(srcname):
                linkto = os.readlink(srcname)
                os.symlink(linkto, dstname)
            elif os.path.isdir(srcname):
                copytree(srcname, dstname, symlinks, ignore)
            else:
                copy2(srcname, dstname)
            # XXX What about devices, sockets etc.?
        except (IOError, os.error) as why:
            errors.append((srcname, dstname, str(why)))
        # catch the Error from the recursive copytree so that we can
        # continue with other files
        except Error as err:
            errors.extend(err.args[0])
    try:
        copystat(src, dst)
    except WindowsError:
        # can't copy file access times on Windows
        pass
    except OSError as why:
        errors.extend((src, dst, str(why)))
    if errors:
        raise Error(errors)

# making a tar
def make_tarfile(output_filename, source_dir):
    with tarfile.open(output_filename, "w:gz") as tar:
        tar.add(source_dir, arcname=os.path.basename(source_dir))

# The old script used to take tars and put them into a folder based on their names.
# I would suggest just creating the tar in the right place in the first place.
# This is because glacier backups begin with a source folder.
# i.e. backup_tarfilename



