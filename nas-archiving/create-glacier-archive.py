# Create a clean archive of a photo store.
# Sends the files to a default location that can be overridden.
#
# The folder will be based on the folder being archived.
# i.e. if you archive .../pictures/Archive_PS1/store0035/
# the final archive will be /share/backup-jobs/aws-glacier/backup_store0035/store0035.tar.bz2
#
# todo list
# Validate the file entries.
# Validate the files against the originals.
# Create md5 file for tar
# Flag to compare md5 against original file.
# http://stackoverflow.com/questions/2018512/reading-tar-file-contents-without-untarring-it-in-python-script
# http://stackoverflow.com/questions/254350/in-python-is-there-a-concise-way-of-comparing-whether-the-contents-of-two-text
# http://stackoverflow.com/questions/3431825/generating-an-md5-checksum-of-a-file


import getopt
import os
import shutil
import sys
import tarfile

IGNORE_PATTERNS = ('*.DS_Store', '*.@__thumb')

_dir_to_default = "/share/backup-jobs/aws-glacier"
_dir_to_prefix = "backup_"

_ignored_files = set()
_included_files = set()


class FileStatus:
    def __init__(self):
        pass


class Flags:
    def __init__(self):
        pass


def print_help():
    print ''
    print sys.argv[
              0] + ' [-h] [-l | list] [-c | check-contents] [-s | summary] [-v | verbose]' \
                   '\n [-i | input-dir] [-o | output-dir]'
    print ''
    print 'Creates a tar cleaned of all files we do not want to send to offline archive.'
    print 'Ignores symbolic links'
    print 'Ignored names: [{}]'.format(', '.join(IGNORE_PATTERNS)).join('\n')

    print 'Typical use cases:\n'

    print 'Report a dry run:'
    print sys.argv[0] + ' -d <input directory> -l\n'

    print 'Report summary:'
    print ''.join(sys.argv[0]) + (' -i <input directory> -s\n')

    print 'Creating archives:'
    print 'With no output the default location is used: [{}]'.format(_dir_to_default)
    print sys.argv[0] + ' -i <input directory>'
    print sys.argv[0] + ' -i <input directory> -o <output directory>\n'

    print 'Verbose and summary'
    print sys.argv[0] + ' -i <input directory> -o <output directory> -vs\n'

    print 'Checking archives and validating the contents:'

    print sys.argv[0] + ' -i <input directory> -o <output directory> -c\n'


#
# Collect skipped file
def add_skip_file(ignored_files, src, name, why):
    file_status = FileStatus()
    file_status.why = why
    file_status.fileName = os.path.join(src, name)
    ignored_files.add(file_status)

    return


#
# Find files
def list_tree(src, ignore=None):
    names = os.listdir(src)

    if ignore is not None:
        ignored_names = ignore(src, names)
    else:
        ignored_names = set()

    errors = []
    for name in names:
        if name in ignored_names:
            add_skip_file(_ignored_files, src, name, 'skip pattern match')
            continue

        srcname = os.path.join(src, name)
        try:
            if os.path.isdir(srcname) and not os.path.islink(srcname):
                list_tree(srcname, ignore)
            elif os.path.islink(srcname):
                add_skip_file(_ignored_files, src, name, 'skip symbolic link')
            else:
                _included_files.add(srcname)

        # What about devices, sockets etc.?
        except (IOError, os.error) as why:
            errors.append((srcname, str(why)))
        # catch the Error from the recursive listtree so that we can
        # continue with other files
        except EnvironmentError as err:
            errors.extend(err.args[0])

    if errors:
        raise Exception(errors)

    return


#
# Print files which will be added / not added to archive
def print_list(included_files, ignored_files):
    print 'Ignore Names: [{}]'.format(', '.join(IGNORE_PATTERNS))

    print '--Include--'
    for file_name in sorted(included_files):
        print '[{}]'.format(file_name)

    print ''
    print '--Ignored--'
    for file_status in sorted(ignored_files):
        print '[{}],[{}]'.format(file_status.why, file_status.fileName)
    return


#
# Print a sum totals.
def print_summary(included_files, ignored_files):
    print ''
    print '--Summary--'
    print '{} included files.'.format(len(included_files))
    print '{} ignored files.'.format(len(ignored_files))
    return


#
# Create a new location for the file based on its name
def create_to_dir(dir_to, dir_to_prefix, to_dir_path_end):
    create_dir = os.path.join(dir_to, dir_to_prefix + to_dir_path_end)

    if not os.path.exists(create_dir):
        os.mkdir(create_dir, 0755)

    return create_dir


#
# Build the compressed archive
def create_archive(dir_from, dir_to, dir_to_prefix, included_files, flags):
    to_dir_path_end = os.path.basename(os.path.normpath(dir_from))
    archive_to_dir = create_to_dir(dir_to, dir_to_prefix, to_dir_path_end)
    tar_path = archive_to_dir + '/' + to_dir_path_end + '.tar.bz2'

    if flags.verbose:
        print 'Archive to: [{}]'.format(tar_path)

    i = len(included_files)

    if os.path.isfile(tar_path):
        raise Exception("Tar exists! Will not overwrite! " + tar_path)

    with tarfile.open(tar_path, "w:bz2") as tar:
        for name in included_files:
            if flags.verbose:
                print 'a[{}] {}'.format(i, name)
            tar.add(name, arcname=os.path.abspath(name))
            i -= 1
    return


#
# Create a clean archive.  Process incoming args.
def main(argv):
    flags = Flags()
    flags.verbose = False
    flags.summary = False
    flags.list = False

    dir_from = ''
    dir_to = _dir_to_default

    if (argv is None) or (len(argv) == 0):
        print_help()
        sys.exit(2)

    try:
        opts, args = getopt.getopt(argv, "hi:lo:svc",
                                   ["input-dir=", "list", "output-dir=", "summary", "verbose", "check-contents"])
    except getopt.GetoptError:
        print_help()
        sys.exit(2)

    for opt, arg in opts:
        if opt == "-h":
            print_help()
            sys.exit()

        if opt in ("-o", "--output-dir"):
            dir_to = arg

        if opt in ("-i", "--input-dir"):
            dir_from = arg
            list_tree(src=dir_from, ignore=shutil.ignore_patterns(*IGNORE_PATTERNS))

        if opt in ("-s", "--summary"):
            flags.summary = True

        if opt in ("-v", "--verbose"):
            flags.verbose = True

        if opt in ("-l", "--list"):
            flags.list = True

        if opt in ("-c", "--check-contents"):
            flags.check_contents = True
            print 'NOT IMPLEMENTED'
            sys.exit(3)

    if flags.list:
        print_list(_included_files, _ignored_files)

    if flags.summary:
        print_summary(_included_files, _ignored_files)

    # Do no further processing if we are only asked to list, this is a dry run.
    if flags.list:
        sys.exit()

    create_archive(dir_from, dir_to, _dir_to_prefix, _included_files, flags)

    sys.exit()


if __name__ == "__main__":
    main(sys.argv[1:])
