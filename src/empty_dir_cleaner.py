#!/usr/bin/env python3
"""
empty_dir_cleaner.py

Find and optionally delete empty directories. This is the cleanup pass you run
after moving files around, flattening folders, extracting archives, or deleting
build output that left a bunch of useless empty shells behind.

Dependency policy:
    - Standard library only.
    - No packages to install.

Default behavior:
    - Safe report mode only.
    - It does NOT delete anything unless --delete is passed.
    - Scans deepest-first so parent folders can become empty after children are
      removed and then also be removed in the same run.

Examples:
    python empty_dir_cleaner.py ./project
    python empty_dir_cleaner.py ./project --delete
    python empty_dir_cleaner.py ./project --include-hidden --delete
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def check_dependencies() -> None:
    """Stdlib-only dependency hook, kept for consistency across the collection."""

    return None


def is_hidden(path: Path, root: Path) -> bool:
    """Return True when any path component under root starts with a dot."""

    try:
        relative = path.relative_to(root)
    except ValueError:
        return False
    return any(part.startswith(".") for part in relative.parts)


def directory_is_empty(path: Path) -> bool:
    """Return True if a directory has no entries.

    pathlib does not have a direct is_empty method, so we ask the iterator for
    one item. If it immediately raises StopIteration, the folder is empty. This
    avoids building a giant list of directory contents for no reason.
    """

    try:
        next(path.iterdir())
        return False
    except StopIteration:
        return True


def find_empty_dirs(root: Path, include_hidden: bool) -> list[Path]:
    """Return empty directories deepest-first."""

    directories = [path for path in root.rglob("*") if path.is_dir()]
    directories.sort(key=lambda path: len(path.parts), reverse=True)

    empty_dirs: list[Path] = []

    for directory in directories:
        if not include_hidden and is_hidden(directory, root):
            continue
        try:
            if directory_is_empty(directory):
                empty_dirs.append(directory)
        except PermissionError:
            print(f"SKIP permission denied: {directory}", file=sys.stderr)

    return empty_dirs


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Find and optionally delete empty folders.")
    parser.add_argument("path", type=Path, nargs="?", default=Path.cwd(), help="Folder to scan. Defaults to current directory.")
    parser.add_argument("--delete", action="store_true", help="Actually remove empty folders. Without this, the script only reports.")
    parser.add_argument("--include-hidden", action="store_true", help="Include hidden dot-folders in the scan.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    check_dependencies()
    args = parse_args(argv or sys.argv[1:])
    root = args.path.resolve()

    if not root.exists():
        print(f"ERROR: Path does not exist: {root}", file=sys.stderr)
        return 1
    if not root.is_dir():
        print(f"ERROR: Expected a folder: {root}", file=sys.stderr)
        return 1

    empty_dirs = find_empty_dirs(root, include_hidden=args.include_hidden)

    if not empty_dirs:
        print("No empty directories found.")
        return 0

    for directory in empty_dirs:
        print(("DELETE" if args.delete else "EMPTY") + f": {directory}")

    if not args.delete:
        print(f"\nReport complete. Found {len(empty_dirs)} empty directorie(s). Add --delete to remove them.")
        return 0

    deleted = 0
    for directory in empty_dirs:
        try:
            directory.rmdir()
            deleted += 1
        except OSError as exc:
            # If something appeared inside the folder between scan and delete,
            # rmdir will refuse to remove it. Good. That is what we want.
            print(f"SKIP could not remove {directory}: {exc}", file=sys.stderr)

    print(f"\nDone. Deleted {deleted} empty directorie(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
