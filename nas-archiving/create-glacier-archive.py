#!/usr/local/bin/python

# move files from one directory to another
# if files alrady exist there, they will be overwritten
# retains original file date/time

import os
import shutil
import sys, getopt
from sets import Set

IGNORE_PATTERNS = ('*.DS_Store','*.@__thumb')

dirToDefault = "/share/backup-jobs/aws-glacier"
dirToTarFilePrefix = "backup_"

ignoredFiles = set()
includedFiles = set()

class FileStatus:
   pass


def printHelp():
   print ''
   print sys.argv[0] + ' [-h] [l | list] [s | summary] [i | input-dir] [o | output-dir]'
   print ''
   print 'Creates a tar cleaned of all files we do not want to send to offline archive.'
   print 'Ignores symbolic links'
   print 'Ignored names: [{}]'.format(', '.join(IGNORE_PATTERNS))

   print ''
   print 'Typical use cases:'
   print ''

   print 'Report a dry run:'
   print sys.argv[0] + ' -d <input directory> -l'
   print ''

   print 'Report summary:'
   print sys.argv[0] + ' -i <input directory> -s'
   print ''

   print 'Creating archives:'
   print 'With no output the default location is used: [{}]'.format(dirToDefault)
   print sys.argv[0] + ' -i <input directory>'
   print sys.argv[0] + ' -i <input directory> -o <output directory [{}]>'.format(dirToDefault)
   print ''


# Collect skipped file
def addSkipFile(ignoredFiles, src, name, why):
   fileStatus = FileStatus()
   fileStatus.why = why
   fileStatus.fileName = os.path.join(src, name)
   ignoredFiles.add(fileStatus)

   return;

# list files
def listtree(src, ignore=None):
   names = os.listdir(src)
   if ignore is not None:
      ignoredNames = ignore(src, names)
   else:
      ignoredNames = set()

   errors = []
   for name in names:
      if name in ignoredNames:
         addSkipFile(ignoredFiles, src, name, 'skip pattern match')
         continue
      srcname = os.path.join(src, name)
      try:
         if os.path.isdir(srcname):
            listtree(srcname, ignore)
         elif os.path.islink(srcname):
            addSkipFile(ignoredFiles, src, name, 'skip symbolic link')
         else:
            includedFiles.add(srcname)

      # XXX What about devices, sockets etc.?
      except (IOError, os.error) as why:
         errors.append((srcname, str(why)))
      # catch the Error from the recursive listtree so that we can
      # continue with other files
      except EnvironmentError as err:
         errors.extend(err.args[0])
   if errors:
      raise Exception(errors)


   return;


def main(argv):
   dirFrom = ''
   dirTo = dirToDefault

   try:
      opts, args = getopt.getopt(argv, "hi:lo:s", ["input-dir=","list","output-dir=","summary"])
   except getopt.GetoptError:
      printHelp()
      sys.exit(2)
#todo improve the help
   for opt, arg in opts:
      if opt == '-h':
         printHelp()
         sys.exit()

      elif opt in ("-o", "--output-dir"):
         dirTo = arg

      elif opt in ("-i", "--input-dir"):
         dirFrom = arg
         listtree(src=dirFrom, ignore=shutil.ignore_patterns(*IGNORE_PATTERNS))

      elif opt in ('-l', "--list"):
         print 'Ignore Names: [{}]'.format(', '.join(IGNORE_PATTERNS))

         print '--Include--'
         for fileName in sorted(includedFiles):
            print '[{}]'.format(fileName)

         print '--Ignored--'
         for fileStatus in sorted(ignoredFiles):
            print '[{}],[{}]'.format(fileStatus.why, fileStatus.fileName)








if __name__ == "__main__":
   main(sys.argv[1:])



# making a tar
def make_tarfile(output_filename, source_dir):
    with tarfile.open(output_filename, "w:gz") as tar:
        tar.add(source_dir, arcname=os.path.basename(source_dir))

# The old script used to take tars and put them into a folder based on their names.
# I would suggest just creating the tar in the right place in the first place.
# This is because glacier backups begin with a source folder.
# i.e. backup_tarfilename



