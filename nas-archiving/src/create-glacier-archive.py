# Create a clean archive of a photo store.
# Sends the files to a default location that can be overridden.
#
# The folder will be based on the folder being archived.
# i.e. if you archive .../pictures/Archive_PS1/store0035/
# the final archive will be /share/backup-jobs/aws-glacier/backup_store0035/store0035.tar.bz2
#

import getopt
import hashlib
import os
import shutil
import sys
import tarfile
import types

IGNORE_PATTERNS = ('*.DS_Store', '*.@__thumb', '*@Transcode')

_dir_to_default = "/share/backup-jobs/aws-glacier"
_dir_to_prefix = "backup_"


class FileStatus(object):
    def __init__(self):
        """
        Collect the reasons why files are skipped
        """
        pass


class Flags(object):
    def __init__(self, verbose=False, summary=False, list_only=False, check_contents=False, chk_md5=False):
        """
        Collect args from the command line.
        :param verbose: Print progress and other notes.
        :param summary: Print summary information.
        :param list_only: Only list intentions.
        :param check_contents: Check the contents of an existing archive against the filesystem.
        :param chk_md5: Check an md5 file
        """
        self.verbose = verbose
        self.summary = summary
        self.list_only = list_only
        self.check_contents = check_contents
        self.chk_md5 = chk_md5


def print_help():
    print('')
    print(sys.argv[
              0] + ' [-h] [-l | list-only] [-c | check-contents] [-s | summary] [-v | verbose]' \
                   '\n [-i | input-dir] [-o | output-dir]' \
                   '\n [check-md5]')
    print('')
    print('Creates a tar cleaned of all files we do not want to send to offline archive.')
    print('Ignores symbolic links')
    print('Ignored patterns: [{}]'.format(IGNORE_PATTERNS))
    print('This also creates an md5 file for checking the hash of the tarfile.\n')

    print('\nTypical use cases:\n')

    print('Report a dry run:')
    print(sys.argv[0] + ' -d <input directory> -l\n')

    print('Report summary:')
    print(sys.argv[0] + ' -i <input directory> -s\n')

    print('Creating archives:')
    print('With no output the default location is used: [{}]'.format(_dir_to_default))
    print(sys.argv[0] + ' -i <input directory>')
    print(sys.argv[0] + ' -i <input directory> -o <output directory>\n')

    print('Verbose and summary')
    print(sys.argv[0] + ' -i <input directory> -o <output directory> -vs\n')

    print('Checking archives and validating the contents:\n')
    print('Its possible to validate the files for correctness against the originals and check none are missing in either direction.\n')
    print('This also checks the MD5 file against a hash of the tar.\n')
    print(sys.argv[0] + ' -i <input directory> -o <output directory> -c\n')

    print('\nThe --check-md5 flag will read in the buddy md5 file and check it against a hash of the tar.\n')
    print('This will just do the check and exit fast.\n')

    print('Most useful combination on creation is\n' + sys.argv[0] + ' -vsc -i <input directory> -o <output directory>\n\n')

    return


def add_skip_file(ignored_files, src, name, why):
    # type: (set, str, str, str) -> None

    """
    Collect skipped files
    :param ignored_files:
    :param src:
    :param name:
    :param why:
    """
    file_status = FileStatus()
    file_status.why = why
    file_status.fileName = os.path.join(src, name)
    ignored_files.add(file_status)

    return


def list_tree(src, included_files, skipped_files, ignore=None):
    # type: (str, set, set, types.FunctionType) -> None
    """
    Walk the tree and find all files.  Populates ignored_files and included_files
    :param src: Route folder name.
    :param skipped_files: Collect the skipped files
    :param included_files: Collect the included files
    :param ignore: Function for patterns to ignore.
    """
    names = os.listdir(src)

    if ignore is not None:
        ignored_names = ignore(src, names)
    else:
        ignored_names = set()

    errors = []
    for name in names:
        if name in ignored_names:
            add_skip_file(skipped_files, src, name, 'skip pattern match')
            continue

        srcname = os.path.join(src, name)
        try:
            if os.path.isdir(srcname) and not os.path.islink(srcname):
                list_tree(srcname, included_files, skipped_files, ignore)
            elif os.path.islink(srcname):
                add_skip_file(skipped_files, src, name, 'skip symbolic link')
            else:
                included_files.add(srcname)

        # What about devices, sockets etc.?
        except (IOError, os.error) as why:
            errors.append((srcname, str(why)))
        # catch the Error from the recursive tree so that we can
        # continue with other files
        except EnvironmentError as err:
            errors.extend(err.args[0])

    if errors:
        raise Exception(errors)

    return


def create_archive(tar_filename, included_files, flags):
    # type: (str, set, Flags) -> None
    """
    Create the archive and an associate md5 file.
    :param tar_filename:
    :param included_files:
    :param flags:
    """
    i = len(included_files)

    if os.path.isfile(tar_filename):
        sys.exit("Tar exists! Will not overwrite, user must remove. [{}]".format(tar_filename))

    with tarfile.open(tar_filename, "w:bz2") as tar:
        for name in included_files:
            if flags.verbose:
                print('a [{}] {}'.format(i, name))
            tar.add(name, arcname=os.path.abspath(name))
            i -= 1

    write_md5(tar_filename, flags)

    return


def print_list(included_files, skipped_files):
    # type: (set, set) -> None
    """
    Print files which will be [added, not added] to archive
    :param included_files:
    :param skipped_files:
    """
    print('\n** List files only! **')
    print('\nIgnore Names: [{}]'.format(', '.join(IGNORE_PATTERNS)))

    print('--Include--')
    for file_name in sorted(included_files):
        print('[{}]'.format(file_name))

    print('')
    print('--Ignored--')
    for file_status in sorted(skipped_files):
        print('[{}],[{}]'.format(file_status.why, file_status.fileName))
    return


def print_summary(included_files, skipped_files):
    # type: (set, set) -> None
    """
    Print a sum totals.
    :param included_files:
    :param skipped_files:
    """
    print('')
    print('--Summary--')
    print('{} included files.'.format(len(included_files)))
    print('{} ignored files.\n'.format(len(skipped_files)))
    return


def create_to_dir(dir_to, dir_to_prefix, dir_to_suffix):
    # type: (str, str, str) -> str
    """
    Create a new location for the file based on its name
    :param dir_to: Folder to write too.
    :param dir_to_prefix: Prefix for the folder. i.e backup_
    :param dir_to_suffix: Suffix for the folder. i.e store0035
    :return: folder name where the tar will be sent
    """
    create_dir = os.path.join(dir_to, dir_to_prefix + dir_to_suffix)

    if not os.path.exists(create_dir):
        os.mkdir(create_dir, 0o755)

    return create_dir


def build_tar_location(dir_from, dir_to):
    # type: (str, str) -> str
    """
    Create the folder where the tar will be written and return the name.
    :param dir_from: Where to find the files.
    :param dir_to: Where to send the files.
    :return: The name of the tar being created.
    """
    to_dir_path_end = os.path.basename(os.path.normpath(dir_from))
    archive_to_dir = create_to_dir(dir_to, _dir_to_prefix, to_dir_path_end)
    tar_filename = archive_to_dir + '/' + to_dir_path_end + '.tar.bz2'

    return tar_filename


def check_archive(tar_filename, included_files):
    # type: (str, set) -> bool
    """
    Check the contents of the tar against the original files.
    Check no files are missing in the archive.
    :param tar_filename: The archive to check.
    :param included_files: The list of files the archive should contain.
    :return True if archive is ok
    """
    print('\nChecking tar: [{}]'.format(tar_filename))

    good_archive = True
    if not match_members_with_fs(tar_filename):
        good_archive = False
    if not match_fs_with_members(tar_filename, included_files):
        good_archive = False

    if not check_md5(tar_filename):
        print("\nERROR: MD5 Not Matched!")
        good_archive = False
    else:
        print("\nMD5 Matched.")

    return good_archive


def check_md5(tar_filename):
    # type: (str) -> bool
    """
    Generate an md5 off the tar and check it against the one on the fs.
    :param tar_filename: Archive to generate from.
    """
    md5_filename = tar_filename + '.md5'
    if os.path.isfile(md5_filename):
        md5_hash = generate_md5(tar_filename)
        with open(md5_filename, 'r') as f:
            stored_md5_hash = f.read()
            if not md5_hash == stored_md5_hash:
                return False
            else:
                return True


def match_fs_with_members(tar_filename, included_files):
    # type: (str, set) -> bool
    """
    Check the tar contains a file match for every one on the filesystem.
    :param tar_filename: The archive to check.
    :param included_files: The names of the expected files from the filesystem.
    :return True if archive is ok
    """
    good_archive = True

    with tarfile.open(tar_filename, "r") as tar:
        member_fs_names = set()
        for member in tar.getmembers():
            member_name_fs = os.path.join('/', member.name)
            member_fs_names.add(member_name_fs)

        for fs_name in included_files:
            if not os.path.abspath(fs_name) in member_fs_names:
                print('MISSING FROM TAR [{}]'.format(fs_name))
                good_archive = False

    return good_archive


def match_members_with_fs(tar_filename):
    # type: (str) -> bool
    """
    Read each file in the archive and deep match agains the original on the filesystem.
    :param tar_filename: The archive to check.
    :return: True if the archive is ok
    """
    good_archive = True

    with tarfile.open(tar_filename, "r") as tar:

        for member in tar.getmembers():
            member_name_fs = os.path.join('/', member.name)

            if os.path.isfile(member_name_fs):
                member_as_file = tar.extractfile(member)
                with open(member_name_fs, "rb") as original_file:
                    if member_as_file.read() == original_file.read():
                        print('MATCHED {}'.format(member_name_fs))
                    else:
                        print('CORRUPT {}'.format(member_name_fs))
                        good_archive = False
            else:
                print('MISSING FROM  FS [{}]'.format(member_name_fs))
                good_archive = False

    return good_archive


def generate_md5(filename):
    # type: (str) -> str
    """
    Read the archive and produce an md5 string.
    :param filename: Archive filename to read.
    :return: md5
    """
    hash_md5 = hashlib.md5()
    with open(filename, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def write_md5(tar_filename, flags):
    # type: (str, Flags) -> None
    """
    Write out an md5 string to file
    :param tar_filename:
    """
    md_filename = tar_filename + '.md5'
    if flags.verbose:
        print('\nWriting MD5 file: [{}]'.format(md_filename))

        md5_hex = generate_md5(tar_filename)
        with open(md_filename, 'w') as f:
            f.write(md5_hex)

    return


def main(argv):
    # type: (list) -> None
    """
    Create a clean archive.  Process incoming args.
    :param argv: Program arguments.
    """
    flags = Flags()

    dir_from = ''
    dir_to = _dir_to_default

    skipped_files = set()
    included_files = set()

    if (argv is None) or (len(argv) == 0):
        print_help()
        sys.exit(2)

    try:
        opts, args = getopt.getopt(argv, "chi:lo:sv",
                                   ["check-contents", "check-md5", "input-dir=", "list-only"
                                       , "output-dir=", "summary", "verbose", ])
    except getopt.GetoptError:
        print_help()
        sys.exit(2)

    for opt, arg in opts:
        if opt == "-h":
            print_help()
            sys.exit(0)

        if opt in ("-o", "--output-dir"):
            dir_to = arg

        if opt in ("-i", "--input-dir"):
            dir_from = arg
            list_tree(src=dir_from
                      , included_files=included_files
                      , skipped_files=skipped_files
                      , ignore=shutil.ignore_patterns(*IGNORE_PATTERNS))

            if len(included_files) == 0:
                sys.exit("* No files found to archive! **")

        if opt in ("-s", "--summary"):
            flags.summary = True

        if opt in ("-v", "--verbose"):
            flags.verbose = True

        if opt in ("-l", "--list-only"):
            flags.list_only = True

        if opt in ("-c", "--check-contents"):
            flags.check_contents = True

        if opt == "--check-md5":
            flags.chk_md5 = True

    if not dir_from:
        print_help()
        sys.exit("\n ERROR: -i flag is mandatory!")

    if flags.list_only:
        print_list(included_files, skipped_files)

    if flags.summary:
        print_summary(included_files, skipped_files)

    if flags.list_only:
        sys.exit(0)

    tar_filename = build_tar_location(dir_from, dir_to)

    if (not flags.check_contents) and flags.chk_md5:
        if not check_md5(tar_filename):
            sys.exit("\nERROR: MD5 Not Matched!")
        else:
            print("\nMD5 Matched.")
            sys.exit(0)

    if flags.verbose:
        print('Archive to: [{}]\n'.format(tar_filename))

    if not flags.list_only:
        create_archive(tar_filename, included_files, flags)

    if flags.check_contents:
        if not check_archive(tar_filename, included_files):
            sys.exit("** Archive Matching Error: Check report! **")
        print('\n** Archive Validation Success! **')

    sys.exit(0)


if __name__ == "__main__":
    main(sys.argv[1:])
