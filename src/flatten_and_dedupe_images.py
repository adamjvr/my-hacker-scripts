#!/usr/bin/env python3
"""
flatten_and_dedupe_images.py

Recursively:
1. Finds all images in a directory tree
2. Moves them to the root folder
3. Deduplicates based on SHA256 hash
4. Keeps the largest file when duplicates exist
5. Deletes empty folders
6. Generates CSV report
7. Shows progress bars

Requires:
    pip install tqdm

Author: Ultra-Verbose Engineering Edition
"""

import os
import sys
import csv
import shutil
import hashlib
from pathlib import Path
from tqdm import tqdm

# -----------------------------------------------------------------------------
# CONFIGURATION
# -----------------------------------------------------------------------------

IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".webp", ".gif",
    ".bmp", ".tiff", ".tif", ".heic"
}

CSV_REPORT_NAME = "dedupe_report.csv"

# -----------------------------------------------------------------------------
# HELPER FUNCTIONS
# -----------------------------------------------------------------------------

def is_image_file(path: Path) -> bool:
    return path.suffix.lower() in IMAGE_EXTENSIONS


def compute_sha256(file_path: Path) -> str:
    """
    Compute SHA256 hash in chunks to prevent high memory usage.
    """
    hash_sha256 = hashlib.sha256()

    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hash_sha256.update(chunk)

    return hash_sha256.hexdigest()


def safe_move_to_root(file_path: Path, root_path: Path) -> Path:
    """
    Move file safely to root directory.
    Avoid overwriting by appending numeric suffix.
    """
    destination = root_path / file_path.name
    counter = 1

    while destination.exists():
        destination = root_path / f"{file_path.stem}_{counter}{file_path.suffix}"
        counter += 1

    shutil.move(str(file_path), str(destination))
    return destination


def remove_empty_directories(root_path: Path):
    """
    Remove empty directories bottom-up.
    """
    for dirpath, _, _ in os.walk(root_path, topdown=False):
        path = Path(dirpath)

        if path == root_path:
            continue

        if not any(path.iterdir()):
            print(f"🗑 Removing empty folder: {path}")
            path.rmdir()


# -----------------------------------------------------------------------------
# CORE LOGIC
# -----------------------------------------------------------------------------

def collect_all_images(root_directory: Path):
    """
    Collect all image files recursively.
    """
    return [p for p in root_directory.rglob("*") if p.is_file() and is_image_file(p)]


def flatten_images(root_directory: Path, all_images: list):
    """
    Move all images from subfolders to root directory.
    """
    move_log = []

    print("\n📦 Flattening images...")

    for path in tqdm(all_images, desc="Moving images"):
        if path.parent != root_directory:
            new_path = safe_move_to_root(path, root_directory)
            move_log.append((str(path), str(new_path)))

    return move_log


def dedupe_images(root_directory: Path):
    """
    Deduplicate images in root directory.
    Keeps largest file.
    Returns structured dedupe report data.
    """
    print("\n🧠 Deduplicating images...")

    root_images = [
        p for p in root_directory.iterdir()
        if p.is_file() and is_image_file(p)
    ]

    hash_map = {}

    # Progress bar for hashing
    for file_path in tqdm(root_images, desc="Hashing images"):
        file_hash = compute_sha256(file_path)
        hash_map.setdefault(file_hash, []).append(file_path)

    dedupe_log = []

    # Process duplicates
    for file_hash, files in hash_map.items():
        if len(files) > 1:

            # Sort largest first
            files_sorted = sorted(
                files,
                key=lambda f: f.stat().st_size,
                reverse=True
            )

            keep_file = files_sorted[0]

            for duplicate in files_sorted[1:]:
                dedupe_log.append({
                    "hash": file_hash,
                    "kept_file": keep_file.name,
                    "kept_size": keep_file.stat().st_size,
                    "removed_file": duplicate.name,
                    "removed_size": duplicate.stat().st_size,
                })

                duplicate.unlink()

    return dedupe_log


def generate_csv_report(root_directory: Path, move_log, dedupe_log):
    """
    Generate CSV report containing:
    - Moves
    - Duplicates removed
    """
    report_path = root_directory / CSV_REPORT_NAME

    print(f"\n📄 Writing CSV report: {report_path}")

    with open(report_path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)

        # Section 1: Moves
        writer.writerow(["=== MOVED FILES ==="])
        writer.writerow(["Original Path", "New Path"])

        for original, new in move_log:
            writer.writerow([original, new])

        writer.writerow([])
        writer.writerow(["=== DUPLICATES REMOVED ==="])
        writer.writerow([
            "Hash",
            "Kept File",
            "Kept Size (bytes)",
            "Removed File",
            "Removed Size (bytes)"
        ])

        for entry in dedupe_log:
            writer.writerow([
                entry["hash"],
                entry["kept_file"],
                entry["kept_size"],
                entry["removed_file"],
                entry["removed_size"]
            ])

    print("✅ CSV report generated.")


# -----------------------------------------------------------------------------
# ENTRY POINT
# -----------------------------------------------------------------------------

def main():

    if len(sys.argv) != 2:
        print("Usage:")
        print("    python flatten_and_dedupe_images.py /path/to/image_folder")
        sys.exit(1)

    root_directory = Path(sys.argv[1]).resolve()

    if not root_directory.exists() or not root_directory.is_dir():
        print("❌ Invalid directory.")
        sys.exit(1)

    print(f"\n🚀 Processing: {root_directory}")

    # Step 1: Collect all images
    all_images = collect_all_images(root_directory)
    print(f"📸 Found {len(all_images)} images total.")

    # Step 2: Flatten
    move_log = flatten_images(root_directory, all_images)

    # Step 3: Deduplicate
    dedupe_log = dedupe_images(root_directory)

    # Step 4: Remove empty folders
    remove_empty_directories(root_directory)

    # Step 5: CSV Report
    generate_csv_report(root_directory, move_log, dedupe_log)

    print("\n🎉 Done. Folder flattened, deduplicated, and reported.")


if __name__ == "__main__":
    main()
