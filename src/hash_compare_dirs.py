#!/usr/bin/env python3
"""
hash_compare_dirs.py

Compare two folders by file content hashes instead of trusting filenames.

This is useful after backups, Google Drive downloads, archive extraction, repo
migration, or any situation where you need to know whether two folders contain
the same actual bytes, not just files with similar names.

Dependency policy:
    - Standard library only.
    - Hashing is handled by hashlib.
    - CSV output is handled by csv.

What it reports:
    - Same relative path and same hash.
    - Same relative path but different hash.
    - Files only found in folder A.
    - Files only found in folder B.
    - Possible renamed/moved files based on matching hashes.

Examples:
    python hash_compare_dirs.py ./old_backup ./new_backup
    python hash_compare_dirs.py ./a ./b --ignore-hidden
    python hash_compare_dirs.py ./a ./b --csv report.csv
    python hash_compare_dirs.py ./a ./b --algorithm sha1
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FileRecord:
    """Hash metadata for one file."""

    relative_path: str
    absolute_path: Path
    size_bytes: int
    digest: str


def check_dependencies() -> None:
    """Stdlib-only dependency hook."""

    return None


def is_hidden(path: Path, root: Path) -> bool:
    try:
        relative = path.relative_to(root)
    except ValueError:
        return False
    return any(part.startswith(".") for part in relative.parts)


def hash_file(path: Path, algorithm: str, chunk_size: int = 1024 * 1024) -> str:
    """Hash a file in chunks so huge files do not explode memory."""

    hasher = hashlib.new(algorithm)
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def scan_folder(root: Path, algorithm: str, ignore_hidden: bool) -> dict[str, FileRecord]:
    """Return a map of relative path -> FileRecord for a folder."""

    records: dict[str, FileRecord] = {}

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if ignore_hidden and is_hidden(path, root):
            continue

        relative = path.relative_to(root).as_posix()
        try:
            stat = path.stat()
            digest = hash_file(path, algorithm=algorithm)
        except PermissionError:
            print(f"SKIP permission denied: {path}", file=sys.stderr)
            continue

        records[relative] = FileRecord(
            relative_path=relative,
            absolute_path=path,
            size_bytes=stat.st_size,
            digest=digest,
        )

    return records


def invert_by_hash(records: dict[str, FileRecord]) -> dict[str, list[FileRecord]]:
    """Build digest -> list of records, useful for moved/renamed detection."""

    by_hash: dict[str, list[FileRecord]] = {}
    for record in records.values():
        by_hash.setdefault(record.digest, []).append(record)
    return by_hash


def compare(a: dict[str, FileRecord], b: dict[str, FileRecord]) -> list[dict[str, str]]:
    """Compare two record maps and return rows of report data."""

    rows: list[dict[str, str]] = []
    all_relative_paths = sorted(set(a) | set(b))

    for relative in all_relative_paths:
        left = a.get(relative)
        right = b.get(relative)

        if left and right:
            if left.digest == right.digest:
                status = "same"
            else:
                status = "different_same_relative_path"
            rows.append({
                "status": status,
                "path_a": left.relative_path,
                "path_b": right.relative_path,
                "size_a": str(left.size_bytes),
                "size_b": str(right.size_bytes),
                "hash_a": left.digest,
                "hash_b": right.digest,
            })
        elif left:
            rows.append({
                "status": "only_in_a",
                "path_a": left.relative_path,
                "path_b": "",
                "size_a": str(left.size_bytes),
                "size_b": "",
                "hash_a": left.digest,
                "hash_b": "",
            })
        elif right:
            rows.append({
                "status": "only_in_b",
                "path_a": "",
                "path_b": right.relative_path,
                "size_a": "",
                "size_b": str(right.size_bytes),
                "hash_a": "",
                "hash_b": right.digest,
            })

    # A second pass finds files with the same hash but different names/locations.
    # This is not magic diffing, but it is extremely useful for "did this file get
    # moved or renamed?" after backup and cleanup jobs.
    a_by_hash = invert_by_hash(a)
    b_by_hash = invert_by_hash(b)

    for digest in sorted(set(a_by_hash) & set(b_by_hash)):
        for left in a_by_hash[digest]:
            for right in b_by_hash[digest]:
                if left.relative_path != right.relative_path:
                    rows.append({
                        "status": "same_hash_different_path_possible_move_or_rename",
                        "path_a": left.relative_path,
                        "path_b": right.relative_path,
                        "size_a": str(left.size_bytes),
                        "size_b": str(right.size_bytes),
                        "hash_a": left.digest,
                        "hash_b": right.digest,
                    })

    return rows


def write_csv(rows: list[dict[str, str]], output: Path) -> None:
    """Write the full report to CSV."""

    output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["status", "path_a", "path_b", "size_a", "size_b", "hash_a", "hash_b"]
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def print_report(rows: list[dict[str, str]], show_same: bool) -> None:
    """Print a human-readable report to stdout."""

    counts: dict[str, int] = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
        if row["status"] == "same" and not show_same:
            continue
        print(f"{row['status']}: {row['path_a']} :: {row['path_b']}")

    print("\nSummary:")
    for status in sorted(counts):
        print(f"  {status}: {counts[status]}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare two directories by file hashes.")
    parser.add_argument("folder_a", type=Path, help="First folder.")
    parser.add_argument("folder_b", type=Path, help="Second folder.")
    parser.add_argument("--algorithm", default="sha256", choices=sorted(hashlib.algorithms_guaranteed), help="Hash algorithm to use.")
    parser.add_argument("--ignore-hidden", action="store_true", help="Ignore hidden dot-files and dot-folders.")
    parser.add_argument("--show-same", action="store_true", help="Also print files that match exactly.")
    parser.add_argument("--csv", type=Path, help="Optional CSV output path.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    check_dependencies()
    args = parse_args(argv or sys.argv[1:])

    folder_a = args.folder_a.resolve()
    folder_b = args.folder_b.resolve()

    for folder in (folder_a, folder_b):
        if not folder.exists():
            print(f"ERROR: Folder does not exist: {folder}", file=sys.stderr)
            return 1
        if not folder.is_dir():
            print(f"ERROR: Expected a folder: {folder}", file=sys.stderr)
            return 1

    print(f"Scanning A: {folder_a}")
    records_a = scan_folder(folder_a, algorithm=args.algorithm, ignore_hidden=args.ignore_hidden)
    print(f"Scanning B: {folder_b}")
    records_b = scan_folder(folder_b, algorithm=args.algorithm, ignore_hidden=args.ignore_hidden)

    rows = compare(records_a, records_b)
    print_report(rows, show_same=args.show_same)

    if args.csv:
        write_csv(rows, args.csv.resolve())
        print(f"\nCSV written: {args.csv.resolve()}")

    # Exit code 0 means identical enough by relative path and hash. Exit code 3
    # means differences exist. This is useful for shell scripts and cron jobs.
    bad_statuses = {"only_in_a", "only_in_b", "different_same_relative_path"}
    return 3 if any(row["status"] in bad_statuses for row in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
