#!/usr/bin/env python3
"""
batch_rename_numbered.py

Rename a batch of files into a clean numbered sequence like:

    photo_0001.jpg
    photo_0002.jpg
    photo_0003.jpg

This is for camera dumps, exported frames, sample packs, scanned pages, image
sets, web downloads, or any other folder where the names are garbage and the
order is what actually matters.

Dependency policy:
    - Standard library only.

Default behavior:
    - Renames files in one folder, not recursively unless --recursive is passed.
    - Preserves each file extension.
    - Sorts by filename by default.
    - Uses a two-phase temporary rename so collisions do not brick the operation.
    - Dry-run mode is available and strongly recommended before first use.

Examples:
    python batch_rename_numbered.py ./frames --prefix frame --dry-run
    python batch_rename_numbered.py ./frames --prefix frame
    python batch_rename_numbered.py ./samples --prefix kick --start 0 --digits 3
    python batch_rename_numbered.py ./photos --prefix photo --sort mtime
"""

from __future__ import annotations

import argparse
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RenameAction:
    """One final rename action."""

    source: Path
    destination: Path


def check_dependencies() -> None:
    """Stdlib-only dependency hook."""

    return None


def is_hidden(path: Path, root: Path) -> bool:
    try:
        relative = path.relative_to(root)
    except ValueError:
        return False
    return any(part.startswith(".") for part in relative.parts)


def collect_files(root: Path, recursive: bool, include_hidden: bool, extensions: list[str]) -> list[Path]:
    """Collect files eligible for renaming."""

    wanted_extensions = {ext.lower().lstrip(".") for ext in extensions}
    iterator = root.rglob("*") if recursive else root.iterdir()
    files: list[Path] = []

    for path in iterator:
        if not path.is_file():
            continue
        if not include_hidden and is_hidden(path, root):
            continue
        if wanted_extensions and path.suffix.lower().lstrip(".") not in wanted_extensions:
            continue
        files.append(path)

    return files


def sort_files(files: list[Path], mode: str) -> list[Path]:
    """Sort files in the requested order."""

    if mode == "name":
        return sorted(files, key=lambda path: path.name.lower())
    if mode == "mtime":
        return sorted(files, key=lambda path: path.stat().st_mtime)
    if mode == "size":
        return sorted(files, key=lambda path: path.stat().st_size)
    raise ValueError(f"Unsupported sort mode: {mode}")


def unique_destination(destination: Path, reserved: set[Path]) -> Path:
    """Make sure the generated name does not collide."""

    if not destination.exists() and destination not in reserved:
        return destination

    parent = destination.parent
    stem = destination.stem
    suffix = destination.suffix
    counter = 1

    while True:
        candidate = parent / f"{stem}_{counter:03d}{suffix}"
        if not candidate.exists() and candidate not in reserved:
            return candidate
        counter += 1


def build_plan(args: argparse.Namespace, root: Path) -> list[RenameAction]:
    """Build rename actions."""

    files = collect_files(root, recursive=args.recursive, include_hidden=args.include_hidden, extensions=args.ext)
    files = sort_files(files, args.sort)

    reserved: set[Path] = set()
    actions: list[RenameAction] = []

    number = args.start
    for source in files:
        suffix = source.suffix if args.preserve_extension else ""
        new_name = f"{args.prefix}{args.separator}{number:0{args.digits}d}{suffix}"
        destination = unique_destination(source.with_name(new_name), reserved)
        reserved.add(destination)
        number += args.step

        if source.resolve() != destination.resolve():
            actions.append(RenameAction(source=source, destination=destination))

    return actions


def execute_two_phase(actions: list[RenameAction]) -> None:
    """Execute renames using temporary names first.

    This is the important part. If you directly rename file A to file B while B
    already exists and is also part of the operation, you can create conflicts.
    The two-phase approach moves everything to weird temporary names first, then
    moves those temp names to the final numbered names. Boring, safe, correct.
    """

    temp_actions: list[tuple[Path, Path, Path]] = []

    for action in actions:
        temp_name = action.source.with_name(f".{action.source.name}.renametmp_{uuid.uuid4().hex}")
        action.source.rename(temp_name)
        temp_actions.append((temp_name, action.destination, action.source))

    try:
        for temp_path, final_path, _original_path in temp_actions:
            final_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path.rename(final_path)
    except Exception:
        # Best-effort rollback. If final renaming goes sideways, try to put temp
        # files back where they came from instead of leaving a folder full of
        # rename goblin puke.
        for temp_path, _final_path, original_path in temp_actions:
            if temp_path.exists() and not original_path.exists():
                temp_path.rename(original_path)
        raise


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch rename files into a numbered sequence.")
    parser.add_argument("path", type=Path, help="Folder containing files to rename.")
    parser.add_argument("--prefix", required=True, help="Prefix for renamed files, like photo or frame.")
    parser.add_argument("--separator", default="_", help="Separator between prefix and number.")
    parser.add_argument("--start", type=int, default=1, help="Starting number.")
    parser.add_argument("--step", type=int, default=1, help="Number increment.")
    parser.add_argument("--digits", type=int, default=4, help="Zero-padding width.")
    parser.add_argument("--sort", choices=["name", "mtime", "size"], default="name", help="Ordering for the rename sequence.")
    parser.add_argument("--recursive", action="store_true", help="Rename files recursively.")
    parser.add_argument("--include-hidden", action="store_true", help="Include hidden dot-files/folders.")
    parser.add_argument("--ext", action="append", default=[], help="Only rename this extension. Can be used multiple times, e.g. --ext jpg --ext png.")
    parser.add_argument("--no-preserve-extension", dest="preserve_extension", action="store_false", help="Do not keep original extensions.")
    parser.add_argument("--dry-run", action="store_true", help="Print planned renames without touching files.")
    parser.set_defaults(preserve_extension=True)
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

    actions = build_plan(args, root)

    if not actions:
        print("No files need renaming.")
        return 0

    for action in actions:
        verb = "WOULD RENAME" if args.dry_run else "RENAME"
        print(f"{verb}: {action.source} -> {action.destination}")

    if args.dry_run:
        print(f"\nDry run complete. Planned {len(actions)} rename(s).")
        return 0

    execute_two_phase(actions)
    print(f"\nDone. Renamed {len(actions)} file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
