#!/usr/bin/env python3
"""
flatten_folder.py

Take a nested folder tree and copy or move every file into one flat output
folder. This is the "I do not care how cursed this download folder is, just give
me all the files in one place" tool.

Dependency policy:
    - Standard library only.
    - No pip packages, no apt packages, no internet nonsense.

Default behavior:
    - Scans recursively.
    - Copies files, does not move them unless --move is passed.
    - Creates a sibling output folder named <input>_flattened.
    - Prefixes parent folder names onto files so duplicates are less likely.
    - Still collision-proofs every output path with _001, _002, etc.
    - Skips hidden files/folders unless --include-hidden is passed.

Examples:
    python flatten_folder.py ./downloads
    python flatten_folder.py ./downloads --dry-run
    python flatten_folder.py ./downloads -o ./flat_downloads --move
    python flatten_folder.py ./downloads --no-parent-prefix
"""

from __future__ import annotations

import argparse
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FlattenAction:
    """One file copy or move action in the flattening plan."""

    source: Path
    destination: Path


def check_dependencies() -> None:
    """This script is stdlib-only; the dependency check is intentionally boring."""

    return None


def is_hidden(path: Path, root: Path) -> bool:
    """Return True if the path is hidden relative to the scan root."""

    try:
        relative = path.relative_to(root)
    except ValueError:
        return False
    return any(part.startswith(".") for part in relative.parts)


def is_inside(child: Path, parent: Path) -> bool:
    """Return True when child is inside parent.

    We use this to avoid recursively copying the output folder into itself, which
    is one of those dumb mistakes that creates a fractal trash monster on disk.
    """

    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def unique_path(path: Path, reserved: set[Path]) -> Path:
    """Return a path that does not exist and is not already reserved."""

    if not path.exists() and path not in reserved:
        return path

    parent = path.parent
    stem = path.stem
    suffix = path.suffix
    counter = 1

    while True:
        candidate = parent / f"{stem}_{counter:03d}{suffix}"
        if not candidate.exists() and candidate not in reserved:
            return candidate
        counter += 1


def make_flat_name(source: Path, root: Path, separator: str, parent_prefix: bool) -> str:
    """Make the destination filename for a source file."""

    relative = source.relative_to(root)

    if not parent_prefix or len(relative.parts) == 1:
        return source.name

    # Preserve some location context by prefixing parent folder names. This is
    # useful for image dumps and extracted archives where everything is named
    # "image001.png" in every damn folder.
    prefix = separator.join(part for part in relative.parts[:-1] if part)
    return f"{prefix}{separator}{source.name}"


def build_plan(args: argparse.Namespace, root: Path, output: Path) -> list[FlattenAction]:
    """Build the flattening plan without copying or moving anything yet."""

    reserved: set[Path] = set()
    actions: list[FlattenAction] = []

    for source in root.rglob("*"):
        if not source.is_file():
            continue
        if not args.include_hidden and is_hidden(source, root):
            continue
        if is_inside(source, output):
            continue

        flat_name = make_flat_name(source, root, args.separator, not args.no_parent_prefix)
        destination = unique_path(output / flat_name, reserved)
        reserved.add(destination)
        actions.append(FlattenAction(source=source, destination=destination))

    return actions


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Flatten a nested folder into one output folder.")
    parser.add_argument("path", type=Path, help="Folder to flatten.")
    parser.add_argument("-o", "--output", type=Path, help="Output folder. Defaults to <input>_flattened beside the input folder.")
    parser.add_argument("--move", action="store_true", help="Move files instead of copying them.")
    parser.add_argument("--dry-run", action="store_true", help="Show planned actions without touching files.")
    parser.add_argument("--include-hidden", action="store_true", help="Include hidden dot-files and dot-folders.")
    parser.add_argument("--no-parent-prefix", action="store_true", help="Use original filenames only, relying on counters for collisions.")
    parser.add_argument("--separator", default="__", help="Separator used when prefixing parent folder names.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    check_dependencies()
    args = parse_args(argv or sys.argv[1:])

    root = args.path.resolve()
    if not root.exists():
        print(f"ERROR: Folder does not exist: {root}", file=sys.stderr)
        return 1
    if not root.is_dir():
        print(f"ERROR: Expected a folder: {root}", file=sys.stderr)
        return 1

    output = args.output.resolve() if args.output else root.with_name(f"{root.name}_flattened")
    if output == root:
        print("ERROR: Output folder cannot be the same as input folder.", file=sys.stderr)
        return 1

    actions = build_plan(args, root, output)

    if not actions:
        print("No files found to flatten.")
        return 0

    for action in actions:
        verb = "WOULD MOVE" if args.move and args.dry_run else "WOULD COPY" if args.dry_run else "MOVE" if args.move else "COPY"
        print(f"{verb}: {action.source} -> {action.destination}")

    if args.dry_run:
        print(f"\nDry run complete. Planned {len(actions)} file operation(s).")
        return 0

    output.mkdir(parents=True, exist_ok=True)

    for action in actions:
        action.destination.parent.mkdir(parents=True, exist_ok=True)
        if args.move:
            shutil.move(str(action.source), str(action.destination))
        else:
            shutil.copy2(action.source, action.destination)

    mode = "Moved" if args.move else "Copied"
    print(f"\nDone. {mode} {len(actions)} file(s) into: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
