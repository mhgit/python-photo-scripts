#!/usr/local/bin/python

# Create a clean archive of a photo store.
# Sends the files to a default location that can be overridden.
# Todo, would be handy to be able to create an optional log for checking before the
# archive is sent to glacier.  Just use --log=DEBUG then log at info level.

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
class Flags:
   pass



def printHelp():
   print ''
   print sys.argv[0] + ' [-h] [l | list] [s | summary] [v | verbose] [i | input-dir] [o | output-dir]'
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
   print sys.argv[0] + ' -i <input directory> -o <output directory [{}]>'
   print 'Verbose and summary'
   print sys.argv[0] + ' -i <input directory> -o <output directory [{}]> -vs'

   print ''


# Collect skipped file
def addSkipFile(ignoredFiles, src, name, why):
   fileStatus = FileStatus()
   fileStatus.why = why
   fileStatus.fileName = os.path.join(src, name)
   ignoredFiles.add(fileStatus)

   return;

# Find files
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
         if os.path.isdir(srcname) and not os.path.islink(srcname):
            listtree(srcname, ignore)
         elif os.path.islink(srcname):
            addSkipFile(ignoredFiles, src, name, 'skip symbolic link')
         else:
            includedFiles.add(srcname)

      # What about devices, sockets etc.?
      except (IOError, os.error) as why:
         errors.append((srcname, str(why)))
      # catch the Error from the recursive listtree so that we can
      # continue with other files
      except EnvironmentError as err:
         errors.extend(err.args[0])

   if errors:
      raise Exception(errors)

   return;

def printList(includedFiles, ignoredFiles):
   print 'Ignore Names: [{}]'.format(', '.join(IGNORE_PATTERNS))

   print '--Include--'
   for fileName in sorted(includedFiles):
      print '[{}]'.format(fileName)

   print '--Ignored--'
   for fileStatus in sorted(ignoredFiles):
      print '[{}],[{}]'.format(fileStatus.why, fileStatus.fileName)
   return;

def printSummary(includedFiles, ignoredFiles):
   print ''
   print '--Summary--'
   print '{} included files.'.format(len(includedFiles))
   print '{} ignored files.'.format(len(ignoredFiles))
   return;

def main(argv):
   flags = Flags()
   flags.verbose = False
   flags.summary = False
   flags.list = False

   dirFrom = ''
   dirTo = dirToDefault

   try:
      opts, args = getopt.getopt(argv, "hi:lo:sv", ["input-dir=","list","output-dir=","summary","verbose"])
   except getopt.GetoptError:
      printHelp()
      sys.exit(2)

   for opt, arg in opts:
      if opt == "-h":
         printHelp()
         sys.exit()

      if opt in ("-o", "--output-dir"):
         dirTo = arg

      if opt in ("-i", "--input-dir"):
         dirFrom = arg
         listtree(src=dirFrom, ignore=shutil.ignore_patterns(*IGNORE_PATTERNS))

      if opt in ("-s", "--summary"):
         flags.summary = True

      if opt in ("-v", "--verbose"):
         flags.verbose = True

      if opt in ("-l", "--list"):
         flags.list = True


   if (flags.list == True):
      printList(includedFiles, ignoredFiles)

   if (flags.summary == True):
      printSummary(includedFiles, ignoredFiles)

   # Do no further processing if we are only asked to list, this is a dry run.
   if (flags.list == True):
      sys.exit()


   # todo this is where the tar will be made.
   # implement verbose setting as you go i.e print progress
   sys.exit()

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



