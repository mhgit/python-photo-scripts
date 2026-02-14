"""Tests for nas_archiving.create_glacier_archive."""

import os
import tempfile

from nas_archiving.create_glacier_archive import (
    IGNORE_PATTERNS,
    generate_hash,
    generate_md5,
)


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
