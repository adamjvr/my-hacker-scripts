#!/usr/bin/env python3
"""
sanitize_filenames.py

Clean ugly filenames and folder names into boring automation-friendly names.

This is for the real-world mess: downloads from the internet, Google Drive
exports, camera folders, random vendor ZIPs, copied Windows folders, KiCad junk,
image datasets, and whatever other cursed pile of files needs to stop being a
problem before it goes into Git, a backup, a shell script, or another tool.

Dependency policy:
    - This script uses ONLY the Python standard library.
    - So the dependency checker is intentionally a no-op.
    - It is still here because the rest of this script collection has the same
      pattern: check first, bootstrap if possible, then do the actual work.

Default behavior:
    - Renames files and folders in the target directory.
    - Does NOT recurse unless --recursive is passed.
    - Lowercases names unless --preserve-case is passed.
    - Replaces whitespace and sketchy punctuation with underscores.
    - Keeps normal file extensions intact.
    - Never overwrites existing paths. If a name is taken, it appends _001.
    - Uses a safe planning pass first so we know what will happen before doing it.

Examples:
    python sanitize_filenames.py ./messy_folder --recursive --dry-run
    python sanitize_filenames.py ./messy_folder --recursive
    python sanitize_filenames.py ./messy_folder --recursive --preserve-case
    python sanitize_filenames.py ./messy_folder --recursive --separator - --ascii-only
"""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RenameAction:
    """A single rename we plan to perform.

    Keeping this as a tiny dataclass makes the script easier to reason about:
    first we build a list of actions, then we print or execute that list. That
    is much safer than walking the tree and renaming things immediately like a
    little filesystem goblin with no brakes.
    """

    source: Path
    destination: Path


def check_dependencies() -> None:
    """Dependency check hook for consistency with the rest of the collection.

    This particular script is deliberately stdlib-only. There is nothing to pip
    install, nothing to apt install, and nothing weird hiding behind the curtain.
    The function exists so every script in the pack starts with the same mental
    model: dependencies first, work second.
    """

    return None


def normalize_unicode(text: str, ascii_only: bool) -> str:
    """Normalize Unicode into something predictable.

    Unicode filenames are allowed on Linux, but automation tools are not always
    equally chill about them. When --ascii-only is used, accented characters get
    folded down where possible, so "Beyoncé" becomes "Beyonce" instead of some
    cursed byte soup that looks normal until a script chokes on it.
    """

    normalized = unicodedata.normalize("NFKD", text)
    if ascii_only:
        return normalized.encode("ascii", "ignore").decode("ascii")
    return unicodedata.normalize("NFC", normalized)


def clean_stem(stem: str, *, separator: str, lowercase: bool, ascii_only: bool, max_length: int) -> str:
    """Clean the stem portion of a filename or directory name.

    The stem is the name without the final extension. We clean this part hard:
    whitespace becomes the chosen separator, runs of junk collapse down, and the
    result gets stripped so we do not create names like "___thing___" unless the
    original file was truly fighting us.
    """

    stem = normalize_unicode(stem, ascii_only=ascii_only)

    if lowercase:
        stem = stem.lower()

    # Any whitespace run becomes one separator. Tabs, newlines, normal spaces,
    # all of it. If it looks like a space to a human, make it one boring token.
    stem = re.sub(r"\s+", separator, stem)

    # Keep letters, numbers, dots, underscores, and dashes. Everything else is
    # treated as punctuation noise and becomes the separator.
    stem = re.sub(r"[^A-Za-z0-9._-]+", separator, stem)

    # Collapse repeated separators so "my   file!!!name" does not become a
    # hideous snake pile. Also collapse repeated dots because names like
    # "thing...final...real" tend to create shell annoyance later.
    escaped = re.escape(separator)
    stem = re.sub(rf"{escaped}+", separator, stem)
    stem = re.sub(r"\.{2,}", ".", stem)

    stem = stem.strip("._- ")

    # A filename cannot be empty. If the original name was only emojis or trash
    # punctuation, use a boring placeholder instead of failing weirdly later.
    if not stem:
        stem = "unnamed"

    if max_length > 0 and len(stem) > max_length:
        stem = stem[:max_length].rstrip("._- ") or "unnamed"

    return stem


def sanitize_component(
    name: str,
    *,
    separator: str,
    lowercase: bool,
    ascii_only: bool,
    max_length: int,
    preserve_extension: bool,
) -> str:
    """Return one cleaned path component.

    For files, we preserve the final extension by default. That means
    "Big Messy Photo.JPG" becomes "big_messy_photo.jpg" instead of losing the
    extension or treating every dot as sacred. Multi-extension archive names are
    handled reasonably by preserving only the last suffix because the goal here
    is filename hygiene, not archive semantics.
    """

    if preserve_extension and "." in name and not name.startswith("."):
        path_name = Path(name)
        stem = path_name.stem
        suffix = path_name.suffix
    else:
        stem = name
        suffix = ""

    cleaned_stem = clean_stem(
        stem,
        separator=separator,
        lowercase=lowercase,
        ascii_only=ascii_only,
        max_length=max_length,
    )

    if suffix:
        suffix = normalize_unicode(suffix, ascii_only=ascii_only)
        suffix = suffix.lower() if lowercase else suffix
        suffix = re.sub(r"[^A-Za-z0-9.]", "", suffix)

    return f"{cleaned_stem}{suffix}"


def is_hidden(path: Path, root: Path) -> bool:
    """Return True if any component below root starts with a dot."""

    try:
        relative = path.relative_to(root)
    except ValueError:
        return False
    return any(part.startswith(".") for part in relative.parts)


def unique_destination(destination: Path, reserved: set[Path]) -> Path:
    """Return a destination path that is not taken and not already planned.

    We need to check both the real filesystem and the names reserved by earlier
    planned actions. Otherwise two ugly files could both sanitize into the same
    clean name and one would stomp the other. Stomping user files is loser shit,
    so we append _001, _002, etc.
    """

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


def collect_paths(root: Path, recursive: bool, include_hidden: bool, files_only: bool, dirs_only: bool) -> list[Path]:
    """Collect paths that are eligible for renaming.

    Directories must be renamed deepest-first, or the traversal path changes
    underneath us and everything gets annoying. So this function returns every
    eligible path sorted by depth descending.
    """

    iterator = root.rglob("*") if recursive else root.iterdir()
    paths: list[Path] = []

    for path in iterator:
        if path == root:
            continue
        if not include_hidden and is_hidden(path, root):
            continue
        if files_only and not path.is_file():
            continue
        if dirs_only and not path.is_dir():
            continue
        paths.append(path)

    paths.sort(key=lambda p: len(p.parts), reverse=True)
    return paths


def build_plan(args: argparse.Namespace) -> list[RenameAction]:
    """Build the rename plan without touching the filesystem."""

    root = args.path.resolve()
    paths = collect_paths(
        root,
        recursive=args.recursive,
        include_hidden=args.include_hidden,
        files_only=args.files_only,
        dirs_only=args.dirs_only,
    )

    reserved: set[Path] = set()
    actions: list[RenameAction] = []

    for source in paths:
        preserve_extension = source.is_file() and not args.no_preserve_extension
        clean_name = sanitize_component(
            source.name,
            separator=args.separator,
            lowercase=not args.preserve_case,
            ascii_only=args.ascii_only,
            max_length=args.max_length,
            preserve_extension=preserve_extension,
        )

        if clean_name == source.name:
            continue

        destination = unique_destination(source.with_name(clean_name), reserved)
        reserved.add(destination)
        actions.append(RenameAction(source=source, destination=destination))

    return actions


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sanitize filenames and folder names safely.")
    parser.add_argument("path", type=Path, nargs="?", default=Path.cwd(), help="Folder to clean. Defaults to current directory.")
    parser.add_argument("--recursive", action="store_true", help="Recurse through the folder tree.")
    parser.add_argument("--dry-run", action="store_true", help="Print what would happen without renaming anything.")
    parser.add_argument("--preserve-case", action="store_true", help="Do not lowercase names.")
    parser.add_argument("--ascii-only", action="store_true", help="Fold Unicode down to ASCII where possible.")
    parser.add_argument("--separator", default="_", choices=["_", "-", "."], help="Replacement separator for spaces and junk characters.")
    parser.add_argument("--max-length", type=int, default=180, help="Maximum cleaned stem length. Use 0 to disable.")
    parser.add_argument("--files-only", action="store_true", help="Rename only files.")
    parser.add_argument("--dirs-only", action="store_true", help="Rename only directories.")
    parser.add_argument("--include-hidden", action="store_true", help="Include hidden dot-files and dot-folders.")
    parser.add_argument("--no-preserve-extension", action="store_true", help="Sanitize full file names without treating the suffix specially.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    check_dependencies()
    args = parse_args(argv or sys.argv[1:])
    root = args.path.resolve()

    if args.files_only and args.dirs_only:
        print("ERROR: Pick --files-only or --dirs-only, not both.", file=sys.stderr)
        return 2
    if not root.exists():
        print(f"ERROR: Path does not exist: {root}", file=sys.stderr)
        return 1
    if not root.is_dir():
        print(f"ERROR: Expected a folder: {root}", file=sys.stderr)
        return 1

    actions = build_plan(args)

    if not actions:
        print("Nothing to rename. The folder is already clean enough.")
        return 0

    for action in actions:
        verb = "WOULD RENAME" if args.dry_run else "RENAME"
        print(f"{verb}: {action.source} -> {action.destination}")

    if args.dry_run:
        print(f"\nDry run complete. Planned {len(actions)} rename(s).")
        return 0

    for action in actions:
        action.source.rename(action.destination)

    print(f"\nDone. Renamed {len(actions)} path(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
