# Repository Guidelines

## Project Overview

This repo is a **monorepo of independent Python utility scripts**. Each subproject lives in its own top-level directory with its own `pyproject.toml`/`uv` environment — there is no shared root-level toolchain. The only subproject today is `nas-archiving/`.

`nas-archiving` creates a `.tar.bz2` archive of a photo-store folder for offline/Glacier backup: it walks a directory tree, filters out OS cruft/thumbnails/symlinks, writes the archive plus a SHA-256 sidecar hash, and can validate an existing archive's contents against the filesystem and hash file.

## Architecture & Data Flow

All core logic lives in **one module**, `nas-archiving/nas_archiving/create_glacier_archive.py` (~570 lines); `nas_archiving/__main__.py` and root `nas-archiving/main.py` are both thin `sys.argv` wrappers that just call its `main(argv)`. There is no `argparse`/`click` — CLI parsing uses `getopt`.

The pipeline `main()` orchestrates, in order:

1. **Walk** — `list_tree(src, included_files, skipped_files, ignore=None)` recursively walks the input dir, splitting entries into `included_files` (`set[str]` of absolute paths) and `skipped_files` (`set[FileStatus]`, deduped/sorted by filename). Symlinks are always skipped; glob patterns in `IGNORE_PATTERNS` (`*.DS_Store`, `*.@__thumb`, `*@Transcode`) are filtered via `shutil.ignore_patterns`. `OSError`s hit while walking (e.g. permission-denied subdirs) are collected per level and aggregated into a single `ArchiveWalkError(errors: list[tuple[str, str]])` rather than raised immediately — one bad subtree doesn't abort the whole walk.
2. **Build destination** — `build_tar_location(dir_from, dir_to)` / `create_to_dir(...)` derive the output folder/filename from the *input* directory's basename (e.g. archiving `.../store0035/` produces `backup_store0035/store0035.tar.bz2`), defaulting the output root to `/share/backup-jobs/aws-glacier` unless `-o` is given.
3. **Create** — `create_archive(tar_filename, included_files, flags)` writes the bz2 tar (refuses to overwrite an existing tar — exits instead, does not raise), adding each file with `arcname` set to its absolute path.
4. **Hash** — `write_hash()` / `generate_hash()` write a `sha256sum`-compatible `.sha256` sidecar (`<hex>  <basename>`) for new archives. Legacy `.md5` files (plain hex, no filename) are still read via `check_md5`/`generate_md5` for validating old archives; hash writing only implements the SHA-256 path.
5. **Validate** (`-c`/`--check-contents`) — `check_archive()` orchestrates three independent checks that must **all** pass: `match_members_with_fs` (byte-for-byte compare of each tar member against the file on disk), `match_fs_with_members` (every filesystem-side included file is present in the tar), and `check_archive_hash` (prefers `.sha256` over `.md5` when both exist).

## Key Directories

- `nas-archiving/nas_archiving/` — the single core module (`create_glacier_archive.py`), plus `__init__.py` (version marker only, no re-exports) and `__main__.py` (thin wrapper).
- `nas-archiving/tests/` — pytest suite mirroring the module's function groups.
- `nas-archiving/test-files/image-test-in-area/.../store0035/` — a **real fixture tree** (actual `.CR2`/`.JPG`/`.XMP` files, real symlinks, a `.@__thumb` dir) used to exercise `list_tree` end-to-end instead of mocking the filesystem.
- `nas-archiving/src/` — standalone helper scripts for local testing (`setup.py`, `clean-test-archive.py`); not part of the installed package.
- `.github/workflows/`, `.github/dependabot.yml` — CI and dependency automation, scoped to `nas-archiving/`.

## Development Commands

All commands run **from `nas-archiving/`** (own venv, own lint/test config — do not run from repo root):

```bash
uv sync                                   # install/update the venv (after clone or dependency changes)
uv add <package>                          # add a runtime dependency
uv add --dev <package>                    # add a dev-only dependency (the `dev` group in [dependency-groups])

uv run pytest tests/ -v                   # run the full test suite (coverage runs automatically, see below)
uv run pytest tests/test_create_glacier_archive.py::TestCheckSha256::test_valid_sha256 -v   # single test

uv run ruff check .                       # lint
uv run ruff format --check .              # format check

uv run python src/setup.py                # create target/ folder — run once before test-archive runs
uv run python src/clean-test-archive.py   # remove test archive + hash files before re-running by hand

uv run nas-archiving -i <input-dir> [-o <output-dir>] [-l] [-c] [-s] [-v] [--check-sha256] [--check-md5]
# or equivalently: uv run python main.py ...
```

Never hand-edit `uv.lock` — let `uv add`/`uv sync` regenerate it.

CI (`.github/workflows/ci.yml`) runs on push/PR to `main`/`develop`: `astral-sh/setup-uv@v7`, `uv python install`, `uv sync --all-groups`, `ruff check`, `ruff format --check`, `pytest tests/ -v`, all in one `ubuntu-latest` job scoped to the `nas-archiving/` working directory. Its `cache-dependency-glob` is pinned to the literal `nas-archiving/uv.lock` path (not a wildcard) specifically so uv's dependency-cache lookup doesn't walk into `test-files/` and hit `ELOOP` on the fixture symlinks.

`.github/dependabot.yml` runs weekly (Sunday 09:00 `Europe/London`) `uv` updates scoped to `/nas-archiving`: non-security version updates are grouped into a single PR against `develop` (`open-pull-requests-limit: 5`). **Security PRs always target the repo's default branch (`main`)** per GitHub's own policy — the per-ecosystem `target-branch` and group config have no effect on them, so expect them to land on `main` ungrouped; merge there, then sync `develop` from `main`. All Dependabot commits use the `deps` prefix.

## Code Conventions & Common Patterns

- **No `@dataclass` decorator**: `Flags` and `FileStatus` are manually-`__init__`'d containers with full type hints instead. `FileStatus` uses `@total_ordering` with `__eq__`/`__lt__` comparing only `fileName` (dedup/sort by name, ignoring the skip reason).
- **Error aggregation, not fail-fast**: `ArchiveWalkError` collects `(path, reason)` tuples across a whole recursion level before raising once — follow this pattern for any new walk/batch logic rather than raising on the first error.
- **CLI parsing is `getopt`**, not `argparse`/`click`; there's no `-h`-less short-circuit — calling `main([])` or `main(None)` prints help and exits code `2`.
- **Exit via `sys.exit(message)`** for user-facing failures (overwrite guard, validation failure, usage errors) rather than raising — only `list_tree`'s internal walk errors use an exception (`ArchiveWalkError`).
- **Output is `print()`**, gated by the `verbose`/`summary` flags on `Flags` — no `logging` module.
- **Naming**: `snake_case` functions/variables, `UPPER_CASE` module constants (`IGNORE_PATTERNS`, `HASH_ALGORITHM`, `HASH_EXT`, `MD5_EXT`), leading-underscore "private" module constants (`_dir_to_default`, `_dir_to_prefix`).
- **Docstrings**: brief one-liner plus `:param`/`:return` lines (not Google/NumPy `Args:`/`Returns:` headers) — match this style for any new function.
- Type hints on every signature, including collection element types (e.g. `included_files: set[str]`).

## Important Files

- `nas-archiving/nas_archiving/create_glacier_archive.py` — all core logic (walk, path building, archive creation, hashing, validation, CLI `main()`).
- `nas-archiving/nas_archiving/__main__.py`, `nas-archiving/main.py` — entry-point wrappers; both just call `create_glacier_archive.main(sys.argv[1:])`.
- `nas-archiving/pyproject.toml` — package metadata, `[project.scripts]` entry point (`nas-archiving = "nas_archiving.__main__:main"`), ruff config, pytest config.
- `nas-archiving/README.md` — full CLI flag reference and example workflows (dry run, create+validate, cleanup).
- `nas-archiving/src/setup.py`, `nas-archiving/src/clean-test-archive.py` — test-environment lifecycle helpers, not shipped in the package.
- Root `README.md` — one-line pointer to the `nas-archiving` subproject; not a source of detail.

## Runtime/Tooling Preferences

- **Python 3.14**, pinned via `nas-archiving/.python-version` and `requires-python = ">=3.14.0"`.
- **`uv` only** for dependency/env management — never `pip`, `poetry`, or `conda` (enforced by `.vscode/settings.json`, which points the VS Code interpreter at `nas-archiving/.venv/bin/python`). No `mise` or other runtime-version manager is used — the only pin is `.python-version`.
- **Ruff** is the sole lint/format tool: `target-version = "py314"`, `line-length = 120`, rule set `["E", "F", "I", "UP", "B", "SIM"]` (pycodestyle errors, pyflakes, isort, pyupgrade, bugbear, flake8-simplify). `test-files/` is excluded from ruff traversal — its real symlinks cause `ELOOP` on recursive scans; the same directory is excluded from the CI `uv` cache glob for the same reason.
- Package build backend is `hatchling`; `[tool.uv] package = true`.
- When suggesting shell commands for this project, prefer `eza --icons` for directory listings; the user's terminal is Ghostty with a Nerd Font, so ANSI-colored tool output is expected to render correctly.

## Testing & QA

- **Framework**: pytest, with class-based `TestXxx` groupings per function/concept (e.g. `TestFileStatus`, `TestListTree`, `TestCheckSha256`, `TestCreateArchive`, `TestMatchFunctions`, `TestMain`) plus a few standalone `test_*` functions for simple utilities. No `@pytest.mark.parametrize` usage — follow the existing per-case test style rather than introducing parametrization.
- **Coverage runs by default**: `[tool.pytest.ini_options] addopts = "-v --cov=nas_archiving --cov-report=term-missing"` in `pyproject.toml`, so plain `uv run pytest` already reports missing-line coverage.
- **`TestListTree` exercises the real fixture tree** at `test-files/image-test-in-area/share/Multimedia-enc/pictures/Archive_PS1/store0035/` end-to-end (no filesystem mocking). It has known, exact expectations that will break if the fixture changes: with `IGNORE_PATTERNS` applied, the full store yields **3 included files** + **5 skipped** (2 `.@__thumb` pattern matches + 3 symlinks); `raw/` alone yields 2 included + 2 skipped; with no ignore function, 5 included + 3 symlinks. Check `tests/test_create_glacier_archive.py` for the current counts before modifying the fixture tree.
- Run the whole suite with `uv run pytest tests/ -v` from `nas-archiving/`; run one test with the fully-qualified node id, e.g. `uv run pytest tests/test_create_glacier_archive.py::TestCheckSha256::test_valid_sha256 -v`.
- Before running the CLI against the test fixtures by hand, run `uv run python src/setup.py` once to create the `target/` output folder, and `uv run python src/clean-test-archive.py` to remove a previous test archive/hash files (the main CLI refuses to overwrite an existing tar).
