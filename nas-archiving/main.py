"""
Convenience entry point when run from project root. Delegates to the package CLI.
"""
import sys

from nas_archiving.create_glacier_archive import main

if __name__ == "__main__":
    main(sys.argv[1:])
