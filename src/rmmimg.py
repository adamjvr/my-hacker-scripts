#!/usr/bin/env python3
"""
rmmimg.py

Multicore image metadata stripper + renamer with progress bars.

Fix in this version:
- Linux "creation time" is NOT getctime(). We now:
  - Try true birth/creation time via: stat -c %W <file>  (epoch seconds)
  - If unavailable, fall back to mtime (modified time)

Features:
- Sorts by best-available creation timestamp
- Optional newest-first
- Renames to image0.ext, image1.ext, ...
- Removes ALL metadata
- Multicore via ProcessPoolExecutor
- Progress bar via tqdm
- Optional in-place replace with backup
"""

from __future__ import annotations

import argparse
import os
import sys
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple
from concurrent.futures import ProcessPoolExecutor, as_completed

from PIL import Image, ImageOps
from tqdm import tqdm


# ============================================================
# Timestamp handling (patched for Linux)
# ============================================================

def _linux_birthtime_stat(path: Path) -> Optional[float]:
    """
    Linux-only: try to read the file *birth time* (creation time) using coreutils `stat`.

    Command:
      stat -c %W <file>

    Output:
      - Seconds since epoch if supported by filesystem
      - -1 or 0 if not supported/unknown (varies by stat version/filesystem)

    Returns:
      float epoch seconds, or None if unavailable.
    """
    try:
        # `text=True` gives us a decoded string; `check=False` so we can handle errors.
        proc = subprocess.run(
            ["stat", "-c", "%W", str(path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            check=False,
        )
        s = (proc.stdout or "").strip()
        if not s:
            return None

        # %W is an integer epoch seconds, or -1/0 when unknown.
        val = int(s)
        if val > 0:
            return float(val)

        return None
    except Exception:
        return None


def get_best_creation_timestamp(path: Path) -> float:
    """
    Return best-available timestamp for ordering.

    Windows:
      - getctime() is true creation time -> use that.
    macOS / BSD:
      - st_birthtime may exist -> use that when present.
    Linux:
      - getctime() is inode change time (NOT creation). Avoid it.
      - Try true birth time via `stat -c %W` first.
      - If unavailable, fall back to mtime.

    Final fallback:
      - mtime
      - 0.0 if all else fails
    """
    try:
        st = path.stat()

        # macOS/BSD sometimes expose st_birthtime
        birth = getattr(st, "st_birthtime", None)
        if isinstance(birth, (int, float)) and birth > 0:
            return float(birth)

        # Linux: use `stat -c %W` if possible, otherwise mtime
        if sys.platform.startswith("linux"):
            bt = _linux_birthtime_stat(path)
            if bt is not None:
                return bt
            return float(os.path.getmtime(path))

        # Windows: getctime is actual creation time
        if os.name == "nt":
            ct = os.path.getctime(path)
            if ct and ct > 0:
                return float(ct)
            return float(os.path.getmtime(path))

        # Other Unix-like systems: best effort
        # (getctime may not be birth time, but it's sometimes closer than nothing)
        ct = os.path.getctime(path)
        if ct and ct > 0:
            return float(ct)

        return float(os.path.getmtime(path))

    except Exception:
        try:
            return float(os.path.getmtime(path))
        except Exception:
            return 0.0


# ============================================================
# Image collection
# ============================================================

def is_probably_image(path: Path) -> bool:
    if not path.is_file():
        return False
    return path.suffix.lower() in {
        ".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff",
        ".bmp", ".gif", ".heic", ".heif", ".avif"
    }


@dataclass(frozen=True)
class ImageFile:
    path: Path
    ts: float


def collect_images(input_dir: Path, newest_first: bool) -> list[ImageFile]:
    items: list[ImageFile] = []

    for p in sorted(input_dir.iterdir()):
        if not is_probably_image(p):
            continue
        items.append(ImageFile(path=p, ts=get_best_creation_timestamp(p)))

    # Deterministic ordering:
    # primary: timestamp
    # secondary: filename (case-insensitive)
    items.sort(key=lambda x: (x.ts, x.path.name.lower()), reverse=newest_first)
    return items


# ============================================================
# Worker process
# ============================================================

def strip_metadata_and_save_worker(
    src_str: str,
    dst_str: str,
    keep_icc: bool
) -> Tuple[str, str, Optional[str]]:
    """
    Worker executed in separate process.

    Returns:
      (src_name, dst_name, error_or_None)
    """
    src = Path(src_str)
    dst = Path(dst_str)

    try:
        # Verify fast-fail
        with Image.open(src) as im_verify:
            im_verify.verify()

        with Image.open(src) as im:
            # Apply EXIF orientation, then discard EXIF by not re-saving it
            im = ImageOps.exif_transpose(im)
            im.load()

            # Brand-new clean image containing only pixel data
            clean = Image.new(im.mode, im.size)
            clean.putdata(list(im.getdata()))

            save_kwargs = {}

            # Optional ICC profile retention (still strips EXIF/XMP/IPTC/etc.)
            if keep_icc and "icc_profile" in im.info:
                save_kwargs["icc_profile"] = im.info["icc_profile"]

            dst.parent.mkdir(parents=True, exist_ok=True)

            ext = dst.suffix.lower()
            if ext in [".jpg", ".jpeg"]:
                save_kwargs.setdefault("quality", 95)
                save_kwargs.setdefault("optimize", True)
                save_kwargs.setdefault("progressive", True)
                clean.save(dst, **save_kwargs)
            elif ext == ".webp":
                save_kwargs.setdefault("quality", 95)
                clean.save(dst, **save_kwargs)
            else:
                clean.save(dst, **save_kwargs)

        return (src.name, dst.name, None)

    except Exception as e:
        return (src.name, dst.name, str(e))


# ============================================================
# Main
# ============================================================

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Strip metadata and rename images (multicore + progress bar)."
    )
    parser.add_argument("input_dir", type=str, help="Folder containing images.")
    parser.add_argument("--output-dir", type=str, default=None)
    parser.add_argument("--newest-first", action="store_true")
    parser.add_argument("--in-place", action="store_true")
    parser.add_argument("--keep-icc", action="store_true")
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--quiet", action="store_true", help="Hide per-file OK lines.")

    args = parser.parse_args()

    input_dir = Path(args.input_dir).expanduser().resolve()
    if not input_dir.is_dir():
        print(f"ERROR: Not a directory: {input_dir}", file=sys.stderr)
        return 2

    if args.output_dir is None:
        output_dir = input_dir / "cleaned_out"
    else:
        output_dir = Path(args.output_dir).expanduser().resolve()

    images = collect_images(input_dir, newest_first=args.newest_first)
    if not images:
        print("No images found.")
        return 0

    staging_dir: Optional[Path] = None
    final_output_dir = output_dir

    if args.in_place:
        staging_dir = input_dir / ".__tmp_clean_stage__"
        final_output_dir = staging_dir
        if staging_dir.exists():
            print(f"ERROR: staging dir exists: {staging_dir}", file=sys.stderr)
            return 3

    # Deterministic rename plan (ordering is now fixed by timestamp logic above)
    plan: list[Tuple[Path, Path]] = []
    for idx, item in enumerate(images):
        dst_name = f"image{idx}{item.path.suffix.lower()}"
        plan.append((item.path, final_output_dir / dst_name))

    # Print plan (so you can confirm ordering before processing)
    for src, dst in plan:
        print(f"{src.name}  ->  {dst.name}")

    if args.dry_run:
        print("\nDry run only.")
        return 0

    final_output_dir.mkdir(parents=True, exist_ok=True)

    total = len(plan)
    failed = 0

    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        futures = [
            ex.submit(strip_metadata_and_save_worker, str(src), str(dst), bool(args.keep_icc))
            for (src, dst) in plan
        ]

        with tqdm(total=total, desc="Processing", unit="img") as pbar:
            for fut in as_completed(futures):
                src_name, dst_name, err = fut.result()
                pbar.update(1)

                if err is None:
                    if not args.quiet:
                        tqdm.write(f"OK     {src_name} -> {dst_name}")
                else:
                    failed += 1
                    tqdm.write(f"FAILED {src_name} -> {dst_name} :: {err}")

    if args.in_place:
        if failed > 0:
            print(
                f"\nERROR: {failed} files failed. In-place aborted.\n"
                f"Cleaned files remain in: {final_output_dir}",
                file=sys.stderr,
            )
            return 5

        backup_dir = input_dir / "originals_backup"
        if backup_dir.exists():
            print(f"ERROR: backup dir exists: {backup_dir}", file=sys.stderr)
            return 4

        print(f"\nBacking up originals to: {backup_dir}")
        backup_dir.mkdir(parents=True, exist_ok=True)

        for src, _dst in plan:
            shutil.move(str(src), str(backup_dir / src.name))

        for _src, dst in plan:
            shutil.move(str(dst), str(input_dir / dst.name))

        shutil.rmtree(staging_dir, ignore_errors=True)

        print("\nIn-place complete.")
        print(f"Originals saved in: {backup_dir}")
        return 0

    print(f"\nDone. Output folder: {final_output_dir}")
    if failed:
        print(f"{failed} file(s) failed.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
