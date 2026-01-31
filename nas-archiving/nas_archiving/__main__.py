"""Entry point for the nas-archiving CLI."""

import sys

from nas_archiving.create_glacier_archive import main as cli_main


def main() -> None:
    """Entry point for the console script (no args; uses sys.argv)."""
    cli_main(sys.argv[1:])


if __name__ == "__main__":
    main()
