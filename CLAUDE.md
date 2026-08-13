# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository structure

This is a monorepo of independent Python utility scripts, each living in its own top-level directory with its own `pyproject.toml`/`uv` environment. Currently the only project is `nas-archiving/`; treat each subproject as self-contained (own venv, own lint/test config) rather than assuming a shared root-level toolchain.

## nas-archiving

Creates a `.tar.bz2` archive of a photo store folder for offline/Glacier backup, filtering out OS cruft, thumbnails, and symlinks, and validates archive contents against a checksum file.

### Setup and commands

All commands run from the `nas-archiving/` directory. Python 3.14 is pinned via `.python-version`; dependency/env management is via `uv` (never `pip`/`poetry`/`conda`, per `.cursorrules`).

```bash
uv sync                          # install/update the venv (run after clone or dependency changes)

uv run pytest tests/ -v          # run tests
uv run ruff check .              # lint
uv run ruff format --check .     # format check

uv run python src/setup.py             # create target/ folder (needed once before test-archive runs)
uv run python src/clean-test-archive.py  # remove test archive + hash files before re-running by hand
```

Run a single test: `uv run pytest tests/test_create_glacier_archive.py::TestCheckSha256::test_valid_sha256 -v`

The CLI entry point is installed as `nas-archiving` (see `[project.scripts]` in `pyproject.toml`); `uv run python main.py` at the project root is equivalent and takes the same flags. CI (`.github/workflows/ci.yml`) runs ruff check, ruff format check, and pytest on push/PR to `main`/`develop`.

### Architecture

Everything lives in one module, `nas_archiving/create_glacier_archive.py`; `nas_archiving/__main__.py` and root `main.py` are both thin `sys.argv` wrappers around its `main()`. The flow is:

1. **Walk** (`list_tree`) — recursively walks the input dir, splitting entries into `included_files` (a `set[str]` of absolute paths) and `skipped_files` (a `set[FileStatus]`, deduped/sorted by filename). Symlinks are always skipped; glob patterns in `IGNORE_PATTERNS` (`*.DS_Store`, `*.@__thumb`, `*@Transcode`) are skipped via `shutil.ignore_patterns`. `OSError`s hit while walking (e.g. permission-denied subdirs) are collected rather than raised immediately, aggregated into a single `ArchiveWalkError` at the top of the recursion so one bad subtree doesn't abort the whole walk.
2. **Build destination** (`build_tar_location` / `create_to_dir`) — derives the output folder/filename from the *input* directory's basename (e.g. archiving `.../store0035/` produces `backup_store0035/store0035.tar.bz2`), defaulting the output root to `/share/backup-jobs/aws-glacier` unless `-o` is given.
3. **Create** (`create_archive`) — writes the bz2 tar (refuses to overwrite an existing tar — exits instead), then writes a sidecar hash file via `write_hash`.
4. **Hash** — new archives get a `.sha256` file in `sha256sum`-compatible format (`<hex>  <basename>`). Legacy `.md5` files (plain hex, no filename) are still read for validation of old archives; `write_hash` only implements the sha256 path. `check_archive_hash` prefers `.sha256` over `.md5` when both exist.
5. **Validate** (`check_archive`, `--check-contents`/`-c`) — three independent checks, all must pass: `match_members_with_fs` (byte-for-byte compares each tar member against the file on disk), `match_fs_with_members` (every filesystem-side included file is present in the tar), and `check_archive_hash` (sha256/md5 hash match). `--check-sha256`/`--check-md5` run only the hash check standalone and exit early.

Args are parsed by hand with `getopt` (not argparse/click) into a `Flags` dataclass-like container. There's no `-h`-less short-circuit: calling `main([])` or `main(None)` prints help and exits with code 2.

### Testing notes

Tests use a real fixture tree at `test-files/image-test-in-area/.../store0035/` (containing real symlinks and a `.@__thumb` dir) to exercise `list_tree` end-to-end rather than mocking the filesystem — see `tests/test_create_glacier_archive.py` for the expected include/skip counts if that fixture tree changes. `test-files` is excluded from ruff's traversal (`tool.ruff.exclude`) and from the uv cache glob in CI because the symlinks inside it can cause `ELOOP`.

Pytest is configured (`pyproject.toml`) with `--cov=nas_archiving --cov-report=term-missing` on by default via `addopts`.
