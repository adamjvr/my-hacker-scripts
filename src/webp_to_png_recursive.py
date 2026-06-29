#!/usr/bin/env python3
"""
webp_to_png_recursive.py

Convert .webp images to .png recursively using Pillow.

This is for all the stupid modern web image dumps where everything is WebP but
you need normal PNG files for editing, silkscreen work, image tooling, GitHub
assets, or just not dealing with WebP today.

Dependency policy:
    - Requires Pillow, imported as PIL.
    - If Pillow is missing, the script tries to install it at runtime with pip.
    - Use --no-auto-install if you want a hard fail instead.

Examples:
    python webp_to_png_recursive.py ./images
    python webp_to_png_recursive.py ./images -o ./png_images
    python webp_to_png_recursive.py ./images --delete-original
    python webp_to_png_recursive.py ./images --dry-run
"""

from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
from pathlib import Path


def pip_install(package: str, no_auto_install: bool) -> bool:
    """Try to install a Python package into the current user environment."""

    if no_auto_install:
        return False

    command = [sys.executable, "-m", "pip", "install", "--user", package]
    print("Dependency bootstrap:", " ".join(command))
    try:
        subprocess.check_call(command)
        return True
    except (OSError, subprocess.CalledProcessError):
        return False


def ensure_pillow(no_auto_install: bool):
    """Import Pillow, installing it if needed.

    We import inside the function because importing PIL at the top would crash
    before the script gets a chance to fix the missing dependency. Dependency
    bootstrapping has to happen before the real import. Obvious, but easy to get
    wrong if the code is written like a normal library instead of a practical CLI
    hammer.
    """

    if importlib.util.find_spec("PIL") is None:
        print("Missing Python dependency: Pillow")
        if not pip_install("Pillow", no_auto_install=no_auto_install):
            raise SystemExit("ERROR: Pillow is missing. Install it manually with:\n  python3 -m pip install --user Pillow")

    from PIL import Image  # type: ignore
    return Image


def collect_webp(path: Path) -> tuple[list[Path], Path | None]:
    """Collect .webp files from a file or directory recursively."""

    if path.is_file():
        return ([path] if path.suffix.lower() == ".webp" else []), None
    return sorted(candidate for candidate in path.rglob("*") if candidate.is_file() and candidate.suffix.lower() == ".webp"), path


def output_path_for(source: Path, output_root: Path | None, scan_root: Path | None) -> Path:
    """Compute destination PNG path."""

    filename = source.with_suffix(".png").name
    if output_root is None:
        return source.with_suffix(".png")
    if scan_root is not None:
        try:
            relative_parent = source.parent.relative_to(scan_root)
            return output_root / relative_parent / filename
        except ValueError:
            pass
    return output_root / filename


def convert_one(Image, source: Path, destination: Path, overwrite: bool) -> None:
    """Convert one WebP file into PNG."""

    if destination.exists() and not overwrite:
        print(f"SKIP exists: {destination}")
        return

    destination.parent.mkdir(parents=True, exist_ok=True)

    with Image.open(source) as image:
        # PNG supports alpha. Converting to RGBA keeps transparency instead of
        # accidentally flattening it into weird black/white backgrounds.
        if image.mode not in ("RGBA", "RGB"):
            image = image.convert("RGBA")
        image.save(destination, "PNG")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Recursively convert WebP images to PNG.")
    parser.add_argument("path", type=Path, help="WebP file or folder containing WebP images.")
    parser.add_argument("-o", "--output", type=Path, help="Output root. Defaults beside each WebP.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing PNG files.")
    parser.add_argument("--delete-original", action="store_true", help="Delete source WebP after successful conversion.")
    parser.add_argument("--dry-run", action="store_true", help="Show planned conversions without writing files.")
    parser.add_argument("--no-auto-install", action="store_true", help="Do not try to install Pillow automatically.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    Image = ensure_pillow(no_auto_install=args.no_auto_install)

    target = args.path.resolve()
    if not target.exists():
        print(f"ERROR: Path does not exist: {target}", file=sys.stderr)
        return 1

    output_root = args.output.resolve() if args.output else None
    sources, scan_root = collect_webp(target)

    if not sources:
        print("No .webp files found.")
        return 0

    for source in sources:
        destination = output_path_for(source, output_root, scan_root)
        verb = "WOULD CONVERT" if args.dry_run else "CONVERT"
        print(f"{verb}: {source} -> {destination}")
        if args.dry_run:
            continue
        try:
            convert_one(Image, source, destination, overwrite=args.overwrite)
            if args.delete_original and destination.exists():
                source.unlink()
                print(f"DELETE ORIGINAL: {source}")
        except Exception as exc:
            print(f"ERROR converting {source}: {exc}", file=sys.stderr)

    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
