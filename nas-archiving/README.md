Nas Photo Archiving Scripts
==============

nas-archiving
-------------

**Description**

Scripts to manage the creation of file storage archives. Builds a tar archive and validates files. The archive can then be uploaded to Glacier or similar; you're responsible for what you do next. An MD5 file is produced for checking after a restore.

**Tools setup**

- **Python:** 3.14 (pinned in `.python-version`).
- **uv:** [uv](https://docs.astral.sh/uv/) is used for dependency and environment management. Install it (e.g. `curl -LsSf https://astral.sh/uv/install.sh | sh` or `pip install uv`), then from the `nas-archiving` directory run:
  ```bash
  uv sync
  ```
  This creates a virtual environment and installs the project and its CLI. You only need to run `uv sync` after cloning or when dependencies change.

**Scripts**

- **setup.py** (`src/setup.py`): Creates the `target/` folder used for test output. Run once before testing if `target/` does not exist.
- **clean-test-archive.py** (`src/clean-test-archive.py`): Removes the test archive and its MD5 file. The main script will not overwrite an existing archive, so use this before re-running tests (or delete the archive manually).
- **Main CLI:** The `nas-archiving` command creates a tar suitable for uploading to Glacier. It only includes image-related files and ignores OS cruft and thumbnails. It can also validate an existing archive and its MD5.

**CLI details**

Creates a tar cleaned of all files we do not want to send to offline archive.

- Ignores symbolic links.
- Ignored patterns: `*.DS_Store`, `*.@__thumb`, `*@Transcode`.

**Flags**

| Flag | Description |
|------|-------------|
| `-h` | Show help |
| `-l`, `--list-only` | Dry run: list file operations only |
| `-c`, `--check-contents` | Validate archive contents against original files |
| `-s`, `--summary` | Summary report |
| `-v`, `--verbose` | Verbose output |
| `-i`, `--input-dir` | Input directory to archive (required) |
| `-o`, `--output-dir` | Output directory for the archive |
| `--check-md5` | Check the buddy MD5 file against a hash of the tar |

**Commands (from `nas-archiving` directory)**

All commands assume you have run `uv sync` at least once.

```bash
# Create target folder (if missing)
uv run python src/setup.py

# Dry run — list what would be archived
uv run nas-archiving -vsl -i test-files/image-test-in-area/share/Multimedia-enc/pictures/Archive_PS1/store0035/ -o target/image-test-out-area

# Create the test archive and validate it
uv run nas-archiving -vsc -i test-files/image-test-in-area/share/Multimedia-enc/pictures/Archive_PS1/store0035/ -o target/image-test-out-area

# Remove test archive before re-running (optional)
uv run python src/clean-test-archive.py
```

You can use `uv run python main.py` instead of `uv run nas-archiving` with the same flags.

**Example: create and check a real archive**

```bash
uv run nas-archiving -vsc -i /path/to/your/photos -o /path/to/backup/output
```
