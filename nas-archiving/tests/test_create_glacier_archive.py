"""Tests for nas_archiving.create_glacier_archive."""

import os
import shutil
import tarfile
import tempfile
from pathlib import Path

import pytest

from nas_archiving.create_glacier_archive import (
    HASH_ALGORITHM,
    HASH_EXT,
    IGNORE_PATTERNS,
    MD5_EXT,
    FileStatus,
    Flags,
    add_skip_file,
    build_tar_location,
    check_archive,
    check_archive_hash,
    check_md5,
    check_sha256,
    create_archive,
    create_to_dir,
    generate_hash,
    generate_md5,
    list_tree,
    match_fs_with_members,
    match_members_with_fs,
    print_list,
    print_summary,
    write_hash,
)

# ---------------------------------------------------------------------------
# Paths – resolved from this file so tests work from any cwd and in CI
# ---------------------------------------------------------------------------

_NAS_ARCHIVING_ROOT = Path(__file__).resolve().parent.parent
TEST_FILES_STORE = (
    _NAS_ARCHIVING_ROOT
    / "test-files"
    / "image-test-in-area"
    / "share"
    / "Multimedia-enc"
    / "pictures"
    / "Archive_PS1"
    / "store0035"
)


# ===========================================================================
# Phase 1 – Pure / data helpers
# ===========================================================================


class TestFileStatus:
    """FileStatus data class."""

    def test_creation(self) -> None:
        fs = FileStatus(fileName="/a/b.txt", why="reason")
        assert fs.fileName == "/a/b.txt"
        assert fs.why == "reason"

    def test_equality_same_name(self) -> None:
        a = FileStatus(fileName="x", why="r1")
        b = FileStatus(fileName="x", why="r2")
        assert a == b

    def test_inequality_different_name(self) -> None:
        a = FileStatus(fileName="x")
        b = FileStatus(fileName="y")
        assert a != b

    def test_eq_not_implemented_for_other_types(self) -> None:
        fs = FileStatus(fileName="x")
        assert fs.__eq__("x") is NotImplemented

    def test_hash_same_for_equal(self) -> None:
        a = FileStatus(fileName="x", why="r1")
        b = FileStatus(fileName="x", why="r2")
        assert hash(a) == hash(b)

    def test_hash_differs_for_different_name(self) -> None:
        a = FileStatus(fileName="x")
        b = FileStatus(fileName="y")
        assert hash(a) != hash(b)

    def test_ordering_lt(self) -> None:
        a = FileStatus(fileName="a")
        b = FileStatus(fileName="b")
        assert a < b
        assert not b < a

    def test_lt_not_implemented_for_other_types(self) -> None:
        fs = FileStatus(fileName="x")
        assert fs.__lt__("y") is NotImplemented

    def test_usable_in_sorted_set(self) -> None:
        items = {FileStatus(fileName="c"), FileStatus(fileName="a"), FileStatus(fileName="b")}
        assert [fs.fileName for fs in sorted(items)] == ["a", "b", "c"]


class TestFlags:
    """Flags command-line options container."""

    def test_defaults_all_false(self) -> None:
        f = Flags()
        assert not f.verbose
        assert not f.summary
        assert not f.list_only
        assert not f.check_contents
        assert not f.chk_md5
        assert not f.chk_sha256

    def test_custom_values(self) -> None:
        f = Flags(
            verbose=True,
            summary=True,
            list_only=True,
            check_contents=True,
            chk_md5=True,
            chk_sha256=True,
        )
        assert f.verbose
        assert f.summary
        assert f.list_only
        assert f.check_contents
        assert f.chk_md5
        assert f.chk_sha256


class TestAddSkipFile:
    """add_skip_file helper."""

    def test_adds_to_set(self) -> None:
        skipped: set[FileStatus] = set()
        add_skip_file(skipped, "/src", "file.txt", "reason")
        assert len(skipped) == 1
        entry = next(iter(skipped))
        assert entry.fileName == os.path.join("/src", "file.txt")
        assert entry.why == "reason"

    def test_duplicate_filename_not_added_twice(self) -> None:
        skipped: set[FileStatus] = set()
        add_skip_file(skipped, "/src", "file.txt", "r1")
        add_skip_file(skipped, "/src", "file.txt", "r2")
        assert len(skipped) == 1  # same fileName -> same hash -> dedup


class TestBuildTarLocation:
    """build_tar_location and create_to_dir."""

    def test_build_tar_location(self, tmp_path: Path) -> None:
        result = build_tar_location("/some/path/store0035/", str(tmp_path))
        expected_dir = tmp_path / "backup_store0035"
        assert result == str(expected_dir / "store0035.tar.bz2")
        assert expected_dir.is_dir()

    def test_create_to_dir_new(self, tmp_path: Path) -> None:
        result = create_to_dir(str(tmp_path), "backup_", "store0035")
        assert result == str(tmp_path / "backup_store0035")
        assert (tmp_path / "backup_store0035").is_dir()

    def test_create_to_dir_already_exists(self, tmp_path: Path) -> None:
        (tmp_path / "backup_store0035").mkdir()
        result = create_to_dir(str(tmp_path), "backup_", "store0035")
        assert result == str(tmp_path / "backup_store0035")
        assert (tmp_path / "backup_store0035").is_dir()


# ===========================================================================
# Phase 2 – list_tree (uses the real test-files tree)
# ===========================================================================


class TestListTree:
    """list_tree using the real test-files tree."""

    def test_store0035_with_ignore_patterns(self) -> None:
        """Full store with ignore patterns: 3 included, 5 skipped."""
        included: set[str] = set()
        skipped: set[FileStatus] = set()
        ignore = shutil.ignore_patterns(*IGNORE_PATTERNS)

        list_tree(str(TEST_FILES_STORE), included, skipped, ignore)

        # 3 regular files should be included
        basenames = {os.path.basename(f) for f in included}
        assert basenames == {"161030001.JPG", "20161030-0011.CR2", "20161030-0011.XMP"}
        assert len(included) == 3

        # 5 entries skipped: 2 pattern matches (.@__thumb) + 3 symlinks
        assert len(skipped) == 5

        skip_reasons = {fs.why for fs in skipped}
        assert "skip pattern match" in skip_reasons
        assert "skip symbolic link" in skip_reasons

        pattern_skips = {fs for fs in skipped if fs.why == "skip pattern match"}
        symlink_skips = {fs for fs in skipped if fs.why == "skip symbolic link"}
        assert len(pattern_skips) == 2
        assert len(symlink_skips) == 3

    def test_raw_subdir_with_ignore_patterns(self) -> None:
        """Only raw/: 2 included, 2 skipped (1 pattern + 1 symlink)."""
        included: set[str] = set()
        skipped: set[FileStatus] = set()
        ignore = shutil.ignore_patterns(*IGNORE_PATTERNS)

        list_tree(str(TEST_FILES_STORE / "raw"), included, skipped, ignore)

        basenames = {os.path.basename(f) for f in included}
        assert basenames == {"20161030-0011.CR2", "20161030-0011.XMP"}
        assert len(included) == 2

        # 1 pattern (.@__thumb) + 1 symlink (testfoldersim)
        assert len(skipped) == 2

    def test_no_ignore_function(self) -> None:
        """Without ignore, .@__thumb dirs are traversed -> 5 regular files, 3 symlinks."""
        included: set[str] = set()
        skipped: set[FileStatus] = set()

        list_tree(str(TEST_FILES_STORE), included, skipped, ignore=None)

        # Without ignore, .@__thumb dirs are entered -> their files are included
        basenames = {os.path.basename(f) for f in included}
        assert "161030001.JPG" in basenames
        assert "default20161030-0011A.JPG" in basenames
        assert "default20161030-0011.CR2" in basenames
        assert len(included) == 5

        # Only symlinks are skipped (no pattern filtering)
        assert len(skipped) == 3
        assert all(fs.why == "skip symbolic link" for fs in skipped)

    def test_empty_dir(self, tmp_path: Path) -> None:
        """Empty directory produces no files and no skips."""
        included: set[str] = set()
        skipped: set[FileStatus] = set()

        list_tree(str(tmp_path), included, skipped, ignore=None)

        assert len(included) == 0
        assert len(skipped) == 0


# ===========================================================================
# Phase 3 – Hash files, archives, validation
# ===========================================================================


# -- generate_hash / generate_md5 (preserved from original tests) -----------


def test_ignore_patterns_defined() -> None:
    """IGNORE_PATTERNS should include expected globs."""
    assert "*.DS_Store" in IGNORE_PATTERNS
    assert "*.@__thumb" in IGNORE_PATTERNS
    assert "*@Transcode" in IGNORE_PATTERNS
    assert len(IGNORE_PATTERNS) == 3


def test_generate_hash_sha256() -> None:
    """generate_hash should return sha256 hex digest of file contents."""
    with tempfile.NamedTemporaryFile(mode="wb", delete=False) as f:
        f.write(b"hello\n")
        path = f.name
    try:
        digest = generate_hash(path, "sha256")
        assert len(digest) == 64
        assert all(c in "0123456789abcdef" for c in digest)
    finally:
        os.unlink(path)


def test_generate_hash_known_value() -> None:
    """generate_hash sha256 of empty file is known."""
    with tempfile.NamedTemporaryFile(mode="wb", delete=False) as f:
        path = f.name
    try:
        digest = generate_hash(path, "sha256")
        assert digest == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    finally:
        os.unlink(path)


def test_generate_md5_delegates() -> None:
    """generate_md5 should return 32-char hex (md5)."""
    with tempfile.NamedTemporaryFile(mode="wb", delete=False) as f:
        f.write(b"x")
        path = f.name
    try:
        digest = generate_md5(path)
        assert len(digest) == 32
        assert all(c in "0123456789abcdef" for c in digest)
    finally:
        os.unlink(path)


# -- write_hash --------------------------------------------------------------


class TestWriteHash:
    """write_hash writes sha256sum-style file."""

    def test_sha256_file_created(self, tmp_path: Path) -> None:
        data_file = tmp_path / "test.tar.bz2"
        data_file.write_bytes(b"fake tar content")

        flags = Flags(verbose=True)
        write_hash(str(data_file), flags, "sha256")

        hash_file = tmp_path / "test.tar.bz2.sha256"
        assert hash_file.exists()

        contents = hash_file.read_text()
        parts = contents.strip().split("  ")
        assert len(parts) == 2
        assert len(parts[0]) == 64  # sha256 hex
        assert parts[1] == "test.tar.bz2"  # basename
        assert parts[0] == generate_hash(str(data_file), "sha256")

    def test_non_sha256_does_nothing(self, tmp_path: Path) -> None:
        """write_hash only implements sha256; other algorithms are a no-op."""
        data_file = tmp_path / "test.tar.bz2"
        data_file.write_bytes(b"data")

        flags = Flags()
        write_hash(str(data_file), flags, "md5")

        # No .md5 file is created (write_hash only handles sha256)
        assert not (tmp_path / "test.tar.bz2.md5").exists()


# -- create_archive -----------------------------------------------------------


class TestCreateArchive:
    """create_archive creates tar and hash file."""

    def test_creates_tar_and_hash(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        src.mkdir()
        (src / "a.txt").write_text("hello")
        (src / "b.txt").write_text("world")

        tar_path = tmp_path / "out" / "test.tar.bz2"
        tar_path.parent.mkdir()

        included = {str(src / "a.txt"), str(src / "b.txt")}
        flags = Flags(verbose=True)

        create_archive(str(tar_path), included, flags)

        assert tar_path.exists()
        assert Path(str(tar_path) + HASH_EXT).exists()

        # Verify tar contains the expected members
        with tarfile.open(str(tar_path), "r:bz2") as tar:
            member_names = {os.path.join("/", m.name) for m in tar.getmembers()}
        for f in included:
            assert os.path.abspath(f) in member_names

    def test_refuses_overwrite(self, tmp_path: Path) -> None:
        tar_path = tmp_path / "exists.tar.bz2"
        tar_path.write_bytes(b"")

        with pytest.raises(SystemExit):
            create_archive(str(tar_path), set(), Flags())


# -- check_sha256 -------------------------------------------------------------


class TestCheckSha256:
    """check_sha256 validation."""

    def _make_tar(self, tmp_path: Path) -> Path:
        src = tmp_path / "data.txt"
        src.write_text("test data")
        tar_path = tmp_path / "archive.tar.bz2"
        with tarfile.open(str(tar_path), "w:bz2") as tar:
            tar.add(str(src), arcname="data.txt")
        return tar_path

    def test_valid_sha256(self, tmp_path: Path) -> None:
        tar_path = self._make_tar(tmp_path)
        digest = generate_hash(str(tar_path), HASH_ALGORITHM)
        Path(str(tar_path) + HASH_EXT).write_text(f"{digest}  {tar_path.name}\n")

        assert check_sha256(str(tar_path)) is True

    def test_missing_sha256_file(self, tmp_path: Path) -> None:
        tar_path = self._make_tar(tmp_path)
        assert check_sha256(str(tar_path)) is False

    def test_corrupt_sha256(self, tmp_path: Path) -> None:
        tar_path = self._make_tar(tmp_path)
        Path(str(tar_path) + HASH_EXT).write_text("0" * 64 + "  archive.tar.bz2\n")

        assert check_sha256(str(tar_path)) is False

    def test_short_sha256_file(self, tmp_path: Path) -> None:
        tar_path = self._make_tar(tmp_path)
        Path(str(tar_path) + HASH_EXT).write_text("tooshort\n")

        assert check_sha256(str(tar_path)) is False

    def test_non_hex_sha256(self, tmp_path: Path) -> None:
        tar_path = self._make_tar(tmp_path)
        Path(str(tar_path) + HASH_EXT).write_text("z" * 64 + "  archive.tar.bz2\n")

        assert check_sha256(str(tar_path)) is False


# -- check_md5 ----------------------------------------------------------------


class TestCheckMd5:
    """check_md5 legacy validation."""

    def _make_tar(self, tmp_path: Path) -> Path:
        src = tmp_path / "data.txt"
        src.write_text("test data")
        tar_path = tmp_path / "archive.tar.bz2"
        with tarfile.open(str(tar_path), "w:bz2") as tar:
            tar.add(str(src), arcname="data.txt")
        return tar_path

    def test_valid_md5(self, tmp_path: Path) -> None:
        tar_path = self._make_tar(tmp_path)
        digest = generate_md5(str(tar_path))
        Path(str(tar_path) + MD5_EXT).write_text(digest)

        assert check_md5(str(tar_path)) is True

    def test_missing_md5_file(self, tmp_path: Path) -> None:
        tar_path = self._make_tar(tmp_path)
        assert check_md5(str(tar_path)) is False

    def test_corrupt_md5(self, tmp_path: Path) -> None:
        tar_path = self._make_tar(tmp_path)
        Path(str(tar_path) + MD5_EXT).write_text("0" * 32)

        assert check_md5(str(tar_path)) is False


# -- check_archive_hash -------------------------------------------------------


class TestCheckArchiveHash:
    """check_archive_hash preference: sha256 > md5 > none."""

    def _make_tar(self, tmp_path: Path) -> Path:
        src = tmp_path / "data.txt"
        src.write_text("test data")
        tar_path = tmp_path / "archive.tar.bz2"
        with tarfile.open(str(tar_path), "w:bz2") as tar:
            tar.add(str(src), arcname="data.txt")
        return tar_path

    def test_prefers_sha256(self, tmp_path: Path) -> None:
        tar_path = self._make_tar(tmp_path)
        digest = generate_hash(str(tar_path), HASH_ALGORITHM)
        Path(str(tar_path) + HASH_EXT).write_text(f"{digest}  {tar_path.name}\n")
        # Also write a (wrong) md5 – should still pass because sha256 is preferred
        Path(str(tar_path) + MD5_EXT).write_text("0" * 32)

        assert check_archive_hash(str(tar_path)) is True

    def test_falls_back_to_md5(self, tmp_path: Path) -> None:
        tar_path = self._make_tar(tmp_path)
        digest = generate_md5(str(tar_path))
        Path(str(tar_path) + MD5_EXT).write_text(digest)
        # No .sha256 file

        assert check_archive_hash(str(tar_path)) is True

    def test_no_hash_file(self, tmp_path: Path) -> None:
        tar_path = self._make_tar(tmp_path)
        assert check_archive_hash(str(tar_path)) is False


# -- match_fs_with_members / match_members_with_fs ----------------------------


class TestMatchFunctions:
    """match_fs_with_members and match_members_with_fs."""

    def _create_test_tar(self, tmp_path: Path) -> tuple[Path, set[str]]:
        """Create a tar with known content; files remain on disk."""
        src = tmp_path / "src"
        src.mkdir()
        f1 = src / "a.txt"
        f2 = src / "b.txt"
        f1.write_text("content a")
        f2.write_text("content b")

        included = {str(f1), str(f2)}
        tar_path = tmp_path / "test.tar.bz2"
        with tarfile.open(str(tar_path), "w:bz2") as tar:
            for name in included:
                tar.add(name, arcname=os.path.abspath(name))
        return tar_path, included

    def test_match_fs_with_members_all_present(self, tmp_path: Path) -> None:
        tar_path, included = self._create_test_tar(tmp_path)
        assert match_fs_with_members(str(tar_path), included) is True

    def test_match_fs_with_members_missing(self, tmp_path: Path) -> None:
        tar_path, included = self._create_test_tar(tmp_path)
        # Add an extra file that's not in the tar
        extra = tmp_path / "src" / "c.txt"
        extra.write_text("extra")
        included.add(str(extra))

        assert match_fs_with_members(str(tar_path), included) is False

    def test_match_members_with_fs_all_present(self, tmp_path: Path) -> None:
        tar_path, _ = self._create_test_tar(tmp_path)
        assert match_members_with_fs(str(tar_path)) is True

    def test_match_members_with_fs_file_missing(self, tmp_path: Path) -> None:
        tar_path, included = self._create_test_tar(tmp_path)
        # Delete one source file so it's missing from FS
        first = next(iter(included))
        os.unlink(first)

        assert match_members_with_fs(str(tar_path)) is False


# -- check_archive (integration) ---------------------------------------------


class TestCheckArchive:
    """check_archive combines match + hash checks."""

    def test_valid_archive(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        src.mkdir()
        f1 = src / "file.txt"
        f1.write_text("hello world")

        included = {str(f1)}
        tar_path = tmp_path / "archive.tar.bz2"

        with tarfile.open(str(tar_path), "w:bz2") as tar:
            for name in included:
                tar.add(name, arcname=os.path.abspath(name))

        digest = generate_hash(str(tar_path), HASH_ALGORITHM)
        Path(str(tar_path) + HASH_EXT).write_text(f"{digest}  {tar_path.name}\n")

        assert check_archive(str(tar_path), included) is True

    def test_archive_with_bad_hash(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        src.mkdir()
        f1 = src / "file.txt"
        f1.write_text("hello world")

        included = {str(f1)}
        tar_path = tmp_path / "archive.tar.bz2"

        with tarfile.open(str(tar_path), "w:bz2") as tar:
            for name in included:
                tar.add(name, arcname=os.path.abspath(name))

        # Write wrong sha256
        Path(str(tar_path) + HASH_EXT).write_text("0" * 64 + "  archive.tar.bz2\n")

        assert check_archive(str(tar_path), included) is False


# ===========================================================================
# Phase 4 – Print helpers and main
# ===========================================================================


class TestPrintFunctions:
    """print_list and print_summary output."""

    def test_print_list(self, capsys: pytest.CaptureFixture[str]) -> None:
        included = {"/a/b.txt", "/a/c.txt"}
        skipped = {FileStatus(fileName="/a/d.txt", why="skip symbolic link")}

        print_list(included, skipped)

        captured = capsys.readouterr()
        assert "** List files only! **" in captured.out
        assert "--Include--" in captured.out
        assert "--Ignored--" in captured.out
        assert "/a/b.txt" in captured.out
        assert "/a/c.txt" in captured.out
        assert "skip symbolic link" in captured.out

    def test_print_summary(self, capsys: pytest.CaptureFixture[str]) -> None:
        included = {"a", "b", "c"}
        skipped = {FileStatus(fileName="x", why="r")}

        print_summary(included, skipped)

        captured = capsys.readouterr()
        assert "3 included" in captured.out
        assert "1 ignored" in captured.out


class TestMain:
    """main() argument handling."""

    def test_no_args_exits(self) -> None:
        from nas_archiving.create_glacier_archive import main

        with pytest.raises(SystemExit) as exc_info:
            main([])
        assert exc_info.value.code == 2

    def test_none_args_exits(self) -> None:
        from nas_archiving.create_glacier_archive import main

        with pytest.raises(SystemExit) as exc_info:
            main(None)
        assert exc_info.value.code == 2

    def test_help_exits_zero(self) -> None:
        from nas_archiving.create_glacier_archive import main

        with pytest.raises(SystemExit) as exc_info:
            main(["-h"])
        assert exc_info.value.code == 0

    def test_missing_input_dir_exits(self) -> None:
        from nas_archiving.create_glacier_archive import main

        with pytest.raises(SystemExit) as exc_info:
            main(["-v"])
        assert "mandatory" in str(exc_info.value.code).lower()

    def test_list_only(self, capsys: pytest.CaptureFixture[str]) -> None:
        from nas_archiving.create_glacier_archive import main

        with pytest.raises(SystemExit) as exc_info:
            main(["-i", str(TEST_FILES_STORE), "-l", "-s"])
        assert exc_info.value.code == 0

        captured = capsys.readouterr()
        assert "--Include--" in captured.out
        assert "161030001.JPG" in captured.out
        assert "3 included" in captured.out
