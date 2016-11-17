#!/usr/local/bin/python

# Create a clean archive of a photo store.
# Sends the files to a default location that can be overridden.
# Todo, would be handy to be able to create an optional log for checking before the
# archive is sent to glacier.  Just use --log=DEBUG then log at info level.
# The folder will be based on the folder being archived.
# i.e. if you archive .../pictures/Archive_PS1/store0035/
# the final archive will be /share/backup-jobs/aws-glacier/backup_store0035/store0035.tar.bz2

import os
import shutil
import sys, getopt
import tarfile
from sets import Set

IGNORE_PATTERNS = ('*.DS_Store','*.@__thumb')

dirToDefault = "/share/backup-jobs/aws-glacier"
dirToPrefix = "backup_"

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

# Print files which will be added / not added to archive
def printList(includedFiles, ignoredFiles):
   print 'Ignore Names: [{}]'.format(', '.join(IGNORE_PATTERNS))

   print '--Include--'
   for fileName in sorted(includedFiles):
      print '[{}]'.format(fileName)

   print ''
   print '--Ignored--'
   for fileStatus in sorted(ignoredFiles):
      print '[{}],[{}]'.format(fileStatus.why, fileStatus.fileName)
   return;

# Print a sum totals.
def printSummary(includedFiles, ignoredFiles):
   print ''
   print '--Summary--'
   print '{} included files.'.format(len(includedFiles))
   print '{} ignored files.'.format(len(ignoredFiles))
   return;

# Create a new location for the file based on its name
def createToDir(dirFrom, dirTo, dirToPrefix, toDirPathEnd):

   createDir = os.path.join(dirTo, dirToPrefix + toDirPathEnd)

   if not os.path.exists(createDir):
      os.mkdir(createDir, 0755)

   return createDir;

# Build the compressed archive
def createArchive(dirFrom, dirTo, dirToPrefix, includedFiles, flags):

   toDirPathEnd = os.path.basename(os.path.normpath(dirFrom))
   archiveToDir = createToDir(dirFrom, dirTo, dirToPrefix, toDirPathEnd)
   tarPath = archiveToDir + '/' + toDirPathEnd + '.tar.bz2'


   if (flags.verbose == True):
      print 'Archive to: [{}]'.format(tarPath)

   with tarfile.open(tarPath, "w:bz2") as tar:
      for name in includedFiles:
         if (flags.verbose == True):
            print '+ {}'.format(name)
         tar.add(name, arcname=os.path.abspath(name))




   return;

#
# Create a clean archive.  Process incoming args.
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


   createArchive(dirFrom, dirTo, dirToPrefix, includedFiles, flags)

   sys.exit()

if __name__ == "__main__":
   main(sys.argv[1:])





