"""Restore the fixed Parcel Workbench demo database to its initial fixtures."""

import sqlite3
import sys

from .store import ROOT, Store


def main(argv=None, *, root=ROOT):
    args = sys.argv[1:] if argv is None else argv
    if args:
        print("Usage: python -m backend.reset   (no path arguments)", file=sys.stderr)
        return 2
    try:
        Store(root).initialize(reset=True)
    except (OSError, sqlite3.Error, ValueError) as exc:
        print(f"Reset refused: {exc}", file=sys.stderr)
        return 1
    print("Restored .demo/parcel.sqlite3 to its initial inventory.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
