# Create a clean archive of a photo store.
# Sends the files to a default location that can be overridden.
#
# The folder will be based on the folder being archived.
# i.e. if you archive .../pictures/Archive_PS1/store0035/
# the final archive will be /share/backup-jobs/aws-glacier/backup_store0035/store0035.tar.bz2
#

from __future__ import annotations

import getopt
import hashlib
import os
import shutil
import sys
import tarfile
from collections.abc import Callable
from functools import total_ordering

IGNORE_PATTERNS = ("*.DS_Store", "*.@__thumb", "*@Transcode")

HASH_ALGORITHM = "sha256"
HASH_EXT = ".sha256"
MD5_EXT = ".md5"

_dir_to_default = "/share/backup-jobs/aws-glacier"
_dir_to_prefix = "backup_"


class ArchiveWalkError(Exception):
    """
    Raised when one or more paths could not be walked.
    Carries every error collected during the walk, including those
    propagated up from recursive calls.
    """

    def __init__(self, errors: list[tuple[str, str]]):
        super().__init__(errors)
        self.errors = errors


@total_ordering
class FileStatus:
    def __init__(self, fileName=None, why=None):
        """
        Collect the reasons why files are skipped
        """
        self.fileName = fileName
        self.why = why

    def __eq__(self, other):
        if not isinstance(other, FileStatus):
            return NotImplemented
        return self.fileName == other.fileName

    def __hash__(self):
        return hash((self.fileName,))

    def __lt__(self, other):
        if not isinstance(other, FileStatus):
            return NotImplemented
        return self.fileName < other.fileName


class Flags:
    def __init__(
        self,
        verbose=False,
        summary=False,
        list_only=False,
        check_contents=False,
        chk_md5=False,
        chk_sha256=False,
    ):
        """
        Collect args from the command line.
        :param verbose: Print progress and other notes.
        :param summary: Print summary information.
        :param list_only: Only list intentions.
        :param check_contents: Check the contents of an existing archive against the filesystem.
        :param chk_md5: Check legacy .md5 file only.
        :param chk_sha256: Check .sha256 file only.
        """
        self.verbose = verbose
        self.summary = summary
        self.list_only = list_only
        self.check_contents = check_contents
        self.chk_md5 = chk_md5
        self.chk_sha256 = chk_sha256


def print_help():
    print("")
    print(
        sys.argv[0] + " [-h] [-l | list-only] [-c | check-contents] [-s | summary] [-v | verbose]"
        "\n [-i | input-dir] [-o | output-dir]"
        "\n [--check-md5] [--check-sha256]"
    )
    print("")
    print("Creates a tar cleaned of all files we do not want to send to offline archive.")
    print("Ignores symbolic links")
    print(f"Ignored patterns: [{IGNORE_PATTERNS}]")
    print("New archives get a .sha256 file (sha256sum-style). Legacy .md5 files are still read for validation.\n")

    print("\nTypical use cases:\n")

    print("Report a dry run:")
    print(sys.argv[0] + " -d <input directory> -l\n")

    print("Report summary:")
    print(sys.argv[0] + " -i <input directory> -s\n")

    print("Creating archives:")
    print(f"With no output the default location is used: [{_dir_to_default}]")
    print(sys.argv[0] + " -i <input directory>")
    print(sys.argv[0] + " -i <input directory> -o <output directory>\n")

    print("Verbose and summary")
    print(sys.argv[0] + " -i <input directory> -o <output directory> -vs\n")

    print("Checking archives and validating the contents:\n")
    print(
        "Its possible to validate the files for correctness against the "
        "originals and check none are missing in either direction.\n"
    )
    print("With -c, the hash file (.sha256 if present, else .md5) is checked against the tar.\n")
    print(sys.argv[0] + " -i <input directory> -o <output directory> -c\n")

    print("--check-sha256: check only the .sha256 file (exit after check).")
    print("--check-md5: check only the legacy .md5 file (exit after check).\n")

    print(
        "Most useful combination on creation is\n"
        + sys.argv[0]
        + " -vsc -i <input directory> -o <output directory>\n\n"
    )

    return


def add_skip_file(ignored_files: set[FileStatus], src: str, name: str, why: str) -> None:
    """
    Collect skipped files
    :param ignored_files:
    :param src:
    :param name:
    :param why:
    """

    file_status = FileStatus(fileName=os.path.join(src, name), why=why)
    ignored_files.add(file_status)

    return


def list_tree(
    src: str,
    included_files: set[str],
    skipped_files: set[FileStatus],
    ignore: Callable[[str, list[str]], set[str]] | None = None,
) -> None:
    """
    Walk the tree and find all files.  Populates ignored_files and included_files
    :param src: Route folder name.
    :param skipped_files: Collect the skipped files
    :param included_files: Collect the included files
    :param ignore: Function for patterns to ignore.
    """
    names = os.listdir(src)

    ignored_names = ignore(src, names) if ignore is not None else set()

    errors: list[tuple[str, str]] = []
    for name in names:
        if name in ignored_names:
            add_skip_file(skipped_files, src, name, "skip pattern match")
            continue

        srcname = os.path.join(src, name)
        try:
            if os.path.isdir(srcname) and not os.path.islink(srcname):
                list_tree(srcname, included_files, skipped_files, ignore)
            elif os.path.islink(srcname):
                add_skip_file(skipped_files, src, name, "skip symbolic link")
            else:
                included_files.add(srcname)

        # What about devices, sockets etc.?
        except OSError as why:
            errors.append((srcname, str(why)))
        # collect the errors from the recursive walk so that we can
        # continue with other files
        except ArchiveWalkError as err:
            errors.extend(err.errors)

    if errors:
        raise ArchiveWalkError(errors)

    return


def create_archive(tar_filename: str, included_files: set[str], flags: Flags) -> None:
    """
    Create the archive and an associate md5 file.
    :param tar_filename:
    :param included_files:
    :param flags:
    """
    i = len(included_files)

    if os.path.isfile(tar_filename):
        sys.exit(f"Tar exists! Will not overwrite, user must remove. [{tar_filename}]")

    with tarfile.open(tar_filename, "w:bz2") as tar:
        for name in included_files:
            if flags.verbose:
                print(f"a [{i}] {name}")
            tar.add(name, arcname=os.path.abspath(name))
            i -= 1

    write_hash(tar_filename, flags, HASH_ALGORITHM)

    return


def print_list(included_files: set[str], skipped_files: set[FileStatus]) -> None:
    """
    Print files which will be [added, not added] to archive
    :param included_files:
    :param skipped_files:
    """
    print("\n** List files only! **")
    print("\nIgnore Names: [{}]".format(", ".join(IGNORE_PATTERNS)))

    print("--Include--")
    for file_name in sorted(included_files):
        print(f"[{file_name}]")

    print("")
    print("--Ignored--")
    for file_status in sorted(skipped_files):
        print(f"[{file_status.why}],[{file_status.fileName}]")
    return


def print_summary(included_files: set[str], skipped_files: set[FileStatus]) -> None:
    """
    Print a sum totals.
    :param included_files:
    :param skipped_files:
    """
    print("")
    print("--Summary--")
    print(f"{len(included_files)} included files.")
    print(f"{len(skipped_files)} ignored files.\n")
    return


def create_to_dir(dir_to: str, dir_to_prefix: str, dir_to_suffix: str) -> str:
    """
    Create a new location for the file based on its name
    :param dir_to: Folder to write too.
    :param dir_to_prefix: Prefix for the folder. i.e backup_
    :param dir_to_suffix: Suffix for the folder. i.e store0035
    :return: folder name where the tar will be sent
    """
    create_dir = os.path.join(dir_to, dir_to_prefix + dir_to_suffix)

    if not os.path.exists(create_dir):
        os.makedirs(create_dir, 0o755)

    return create_dir


def build_tar_location(dir_from: str, dir_to: str) -> str:
    """
    Create the folder where the tar will be written and return the name.
    :param dir_from: Where to find the files.
    :param dir_to: Where to send the files.
    :return: The name of the tar being created.
    """
    to_dir_path_end = os.path.basename(os.path.normpath(dir_from))
    archive_to_dir = create_to_dir(dir_to, _dir_to_prefix, to_dir_path_end)
    tar_filename = archive_to_dir + "/" + to_dir_path_end + ".tar.bz2"

    return tar_filename


def check_archive(tar_filename: str, included_files: set[str]) -> bool:
    """
    Check the contents of the tar against the original files.
    Check no files are missing in the archive.
    :param tar_filename: The archive to check.
    :param included_files: The list of files the archive should contain.
    :return True if archive is ok
    """
    print(f"\nChecking tar: [{tar_filename}]")

    good_archive = True
    if not match_members_with_fs(tar_filename):
        good_archive = False
    if not match_fs_with_members(tar_filename, included_files):
        good_archive = False

    if not check_archive_hash(tar_filename):
        print("\nERROR: Hash Not Matched!")
        good_archive = False
    else:
        print("\nHash Matched.")

    return good_archive


def check_md5(tar_filename: str) -> bool:
    """
    Generate an md5 off the tar and check it against the one on the fs (legacy).
    :param tar_filename: Archive to generate from.
    """
    md5_filename = tar_filename + MD5_EXT
    if os.path.isfile(md5_filename):
        md5_hash = generate_md5(tar_filename)
        with open(md5_filename) as f:
            stored_md5_hash = f.read().strip()
            return md5_hash == stored_md5_hash
    return False


def check_sha256(tar_filename: str) -> bool:
    """
    Check the tar against its .sha256 file (sha256sum-style: hex  basename).
    :param tar_filename: Archive to check.
    """
    sha256_filename = tar_filename + HASH_EXT
    if not os.path.isfile(sha256_filename):
        return False
    with open(sha256_filename) as f:
        line = f.read().strip()
    # First 64 hex chars are the digest (sha256sum format)
    if len(line) < 64:
        return False
    stored_hex = line[:64]
    if not all(c in "0123456789abcdef" for c in stored_hex.lower()):
        return False
    computed = generate_hash(tar_filename, HASH_ALGORITHM)
    return computed == stored_hex.lower()


def check_archive_hash(tar_filename: str) -> bool:
    """
    Check hash: prefer .sha256, else .md5 (legacy). Return False if no hash file.
    """
    sha256_path = tar_filename + HASH_EXT
    md5_path = tar_filename + MD5_EXT
    if os.path.isfile(sha256_path):
        return check_sha256(tar_filename)
    if os.path.isfile(md5_path):
        return check_md5(tar_filename)
    print("\nNo hash file found (expected .sha256 or .md5).")
    return False


def match_fs_with_members(tar_filename: str, included_files: set[str]) -> bool:
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
            member_name_fs = os.path.join("/", member.name)
            member_fs_names.add(member_name_fs)

        for fs_name in included_files:
            if os.path.abspath(fs_name) not in member_fs_names:
                print(f"MISSING FROM TAR [{fs_name}]")
                good_archive = False

    return good_archive


def match_members_with_fs(tar_filename: str) -> bool:
    """
    Read each file in the archive and deep match agains the original on the filesystem.
    :param tar_filename: The archive to check.
    :return: True if the archive is ok
    """
    good_archive = True

    with tarfile.open(tar_filename, "r") as tar:
        for member in tar.getmembers():
            member_name_fs = os.path.join("/", member.name)

            if os.path.isfile(member_name_fs):
                member_as_file = tar.extractfile(member)
                with open(member_name_fs, "rb") as original_file:
                    if member_as_file.read() == original_file.read():
                        print(f"MATCHED {member_name_fs}")
                    else:
                        print(f"CORRUPT {member_name_fs}")
                        good_archive = False
            else:
                print(f"MISSING FROM  FS [{member_name_fs}]")
                good_archive = False

    return good_archive


def generate_hash(filename: str, algorithm: str = "sha256") -> str:
    """
    Compute the hex digest of a file using the given algorithm.
    :param filename: Path to the file.
    :param algorithm: Hash algorithm name (e.g. "sha256", "md5").
    :return: Hex digest string.
    """
    h = hashlib.new(algorithm)
    with open(filename, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            h.update(chunk)
    return h.hexdigest()


def generate_md5(filename: str) -> str:
    """
    Read the file and produce an md5 hex string (for legacy .md5 read path).
    :param filename: Archive filename to read.
    :return: md5 hex digest
    """
    return generate_hash(filename, "md5")


def write_hash(tar_filename: str, flags: Flags, algorithm: str = "sha256") -> None:
    """
    Write hash to file. For sha256 uses sha256sum-style: hex  basename.
    :param tar_filename: Path to the tar file.
    :param flags: Verbose etc.
    :param algorithm: "sha256" (new archives) or "md5" (legacy).
    """
    if algorithm == "sha256":
        hash_filename = tar_filename + HASH_EXT
        if flags.verbose:
            print(f"\nWriting SHA-256 file: [{hash_filename}]")
        hex_digest = generate_hash(tar_filename, HASH_ALGORITHM)
        basename = os.path.basename(tar_filename)
        line = f"{hex_digest}  {basename}\n"
        with open(hash_filename, "w") as f:
            f.write(line)
    return


def main(argv: list[str]) -> None:
    """
    Create a clean archive.  Process incoming args.
    :param argv: Program arguments.
    """
    flags = Flags()

    dir_from = ""
    dir_to = _dir_to_default

    skipped_files = set()
    included_files = set()

    if (argv is None) or (len(argv) == 0):
        print_help()
        sys.exit(2)

    try:
        opts, args = getopt.getopt(
            argv,
            "chi:lo:sv",
            [
                "check-contents",
                "check-md5",
                "check-sha256",
                "input-dir=",
                "list-only",
                "output-dir=",
                "summary",
                "verbose",
            ],
        )
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
            list_tree(
                src=dir_from,
                included_files=included_files,
                skipped_files=skipped_files,
                ignore=shutil.ignore_patterns(*IGNORE_PATTERNS),
            )

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

        if opt == "--check-sha256":
            flags.chk_sha256 = True

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

    if (not flags.check_contents) and flags.chk_sha256:
        if not check_sha256(tar_filename):
            sys.exit("\nERROR: SHA-256 Not Matched!")
        print("\nSHA-256 Matched.")
        sys.exit(0)

    if (not flags.check_contents) and flags.chk_md5:
        if not check_md5(tar_filename):
            sys.exit("\nERROR: MD5 Not Matched!")
        print("\nMD5 Matched.")
        sys.exit(0)

    if flags.verbose:
        print(f"Archive to: [{tar_filename}]\n")

    if not flags.list_only:
        create_archive(tar_filename, included_files, flags)

    if flags.check_contents:
        if not check_archive(tar_filename, included_files):
            sys.exit("** Archive Matching Error: Check report! **")
        print("\n** Archive Validation Success! **")

    sys.exit(0)


if __name__ == "__main__":
    main(sys.argv[1:])
