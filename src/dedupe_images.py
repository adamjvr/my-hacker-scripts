"""
Advanced Image Deduplication Script (Pop!_OS safe)

Features:
- dHash (no SciPy / NumPy ABI issues)
- Keeps highest resolution
- Keeps largest filesize on tie
- Option to move duplicates instead of deleting
- Optional CSV report
- Progress bars

Author: You
"""

import os
import csv
import shutil
import argparse
from itertools import combinations
from PIL import Image
import imagehash
from tqdm import tqdm

# ---------------- CONFIG ----------------

HASH_THRESHOLD = 6
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"}

# ---------------- HELPERS ----------------

def image_info(path):
    """
    Return (hash, resolution, filesize)
    """
    try:
        with Image.open(path) as img:
            img = img.convert("RGB")
            h = imagehash.dhash(img)
            w, hgt = img.size
        size = os.path.getsize(path)
        return h, w * hgt, size
    except Exception as e:
        print(f"[ERROR] {path}: {e}")
        return None

def collect_images(folder):
    images = []
    for root, _, files in os.walk(folder):
        for f in files:
            if os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS:
                images.append(os.path.join(root, f))
    return images

# ---------------- DEDUPE ----------------

def find_duplicates(images):
    metadata = {}

    print("[INFO] Hashing images...")
    for img in tqdm(images, desc="Hashing", unit="img"):
        info = image_info(img)
        if info:
            metadata[img] = info

    print("[INFO] Comparing images...")
    dupes = []

    for (p1, (h1, _, _)), (p2, (h2, _, _)) in tqdm(
        combinations(metadata.items(), 2),
        desc="Comparing",
        unit="pair",
        total=len(metadata) * (len(metadata) - 1) // 2,
    ):
        dist = h1 - h2
        if dist <= HASH_THRESHOLD:
            dupes.append((p1, p2, dist))

    return dupes, metadata

# ---------------- RESOLUTION LOGIC ----------------

def choose_keeper(a, b, meta):
    """
    Decide which image to keep.
    """
    _, res_a, size_a = meta[a]
    _, res_b, size_b = meta[b]

    if res_a > res_b:
        return a, b
    if res_b > res_a:
        return b, a

    if size_a >= size_b:
        return a, b
    return b, a

# ---------------- APPLY ACTION ----------------

def process_duplicates(dupes, meta, move_dir=None, csv_path=None):
    handled = set()
    report_rows = []

    if move_dir:
        os.makedirs(move_dir, exist_ok=True)

    for a, b, dist in dupes:
        if a in handled or b in handled:
            continue

        keep, remove = choose_keeper(a, b, meta)
        handled.add(remove)

        print(f"[DUPLICATE]")
        print(f"  Keep:   {keep}")
        print(f"  Remove: {remove} (distance={dist})")

        action = "kept"

        if move_dir:
            dest = os.path.join(move_dir, os.path.basename(remove))
            shutil.move(remove, dest)
            action = "moved"
        else:
            os.remove(remove)
            action = "deleted"

        report_rows.append([
            keep,
            remove,
            meta[keep][1],
            meta[remove][1],
            meta[keep][2],
            meta[remove][2],
            dist,
            action,
        ])

    if csv_path and report_rows:
        write_csv(csv_path, report_rows)

    print(f"\n[SUMMARY] {len(handled)} duplicates handled")

# ---------------- CSV ----------------

def write_csv(path, rows):
    headers = [
        "kept_file",
        "duplicate_file",
        "kept_resolution",
        "duplicate_resolution",
        "kept_filesize",
        "duplicate_filesize",
        "hash_distance",
        "action",
    ]
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)

    print(f"[INFO] CSV report written to {path}")

# ---------------- MAIN ----------------

def main():
    parser = argparse.ArgumentParser(description="Advanced image deduplicator")
    parser.add_argument("folder", help="Image folder")
    parser.add_argument("--move-duplicates", metavar="DIR",
                        help="Move duplicates to DIR instead of deleting")
    parser.add_argument("--csv-report", metavar="FILE",
                        help="Write CSV report to FILE")
    args = parser.parse_args()

    images = collect_images(args.folder)
    print(f"[INFO] Found {len(images)} images")

    dupes, meta = find_duplicates(images)

    if not dupes:
        print("[INFO] No duplicates found")
        return

    process_duplicates(
        dupes,
        meta,
        move_dir=args.move_duplicates,
        csv_path=args.csv_report
    )

if __name__ == "__main__":
    main()
