#!/usr/bin/env python3
"""
pdf_images_extract.py

Extract embedded images from PDF files using PyMuPDF.

This is for ripping figures, scans, schematics, weird book images, datasheet
art, reference graphics, and all the other useful stuff trapped inside PDFs.

Dependency policy:
    - Preferred path requires PyMuPDF, imported as fitz.
    - If PyMuPDF is missing, the script tries to install it at runtime with pip.
    - This script does embedded image extraction. It does not render whole pages
      unless --render-pages is passed.

Examples:
    python pdf_images_extract.py ./manual.pdf
    python pdf_images_extract.py ./pdf_folder --recursive
    python pdf_images_extract.py ./manual.pdf -o ./extracted_images
    python pdf_images_extract.py ./manual.pdf --render-pages --dpi 200
"""

from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
from pathlib import Path


def pip_install(package: str, no_auto_install: bool) -> bool:
    if no_auto_install:
        return False
    command = [sys.executable, "-m", "pip", "install", "--user", package]
    print("Dependency bootstrap:", " ".join(command))
    try:
        subprocess.check_call(command)
        return True
    except (OSError, subprocess.CalledProcessError):
        return False


def ensure_pymupdf(no_auto_install: bool):
    """Import PyMuPDF, installing it if needed."""

    if importlib.util.find_spec("fitz") is None:
        print("Missing Python dependency: PyMuPDF")
        if not pip_install("PyMuPDF", no_auto_install=no_auto_install):
            raise SystemExit("ERROR: PyMuPDF is missing. Install it manually with:\n  python3 -m pip install --user PyMuPDF")

    import fitz  # type: ignore
    return fitz


def collect_pdfs(path: Path, recursive: bool) -> tuple[list[Path], Path | None]:
    """Collect PDFs from a file or directory."""

    if path.is_file():
        return ([path] if path.suffix.lower() == ".pdf" else []), None
    iterator = path.rglob("*") if recursive else path.iterdir()
    return sorted(candidate for candidate in iterator if candidate.is_file() and candidate.suffix.lower() == ".pdf"), path


def output_folder_for(pdf: Path, output_root: Path | None, scan_root: Path | None) -> Path:
    """Return the folder images should go into for one PDF."""

    if output_root is None:
        return pdf.with_suffix("")
    if scan_root is not None:
        try:
            relative_parent = pdf.parent.relative_to(scan_root)
            return output_root / relative_parent / pdf.stem
        except ValueError:
            pass
    return output_root / pdf.stem


def extract_embedded_images(fitz, pdf: Path, destination: Path, overwrite: bool) -> int:
    """Extract embedded image objects from a PDF."""

    destination.mkdir(parents=True, exist_ok=True)
    document = fitz.open(pdf)
    count = 0

    for page_index in range(len(document)):
        page = document[page_index]
        images = page.get_images(full=True)

        for image_index, image_info in enumerate(images, start=1):
            xref = image_info[0]
            image_data = document.extract_image(xref)
            extension = image_data.get("ext", "png")
            image_bytes = image_data["image"]
            output = destination / f"{pdf.stem}_page_{page_index + 1:04d}_image_{image_index:03d}.{extension}"

            if output.exists() and not overwrite:
                print(f"SKIP exists: {output}")
                continue

            output.write_bytes(image_bytes)
            count += 1

    document.close()
    return count


def render_pages(fitz, pdf: Path, destination: Path, dpi: int, overwrite: bool) -> int:
    """Render each PDF page to a PNG image.

    This is different from embedded extraction. Rendering is basically taking a
    picture of each page. It is heavier, but useful for scanned PDFs or pages
    where the "image" is actually vector/text content.
    """

    destination.mkdir(parents=True, exist_ok=True)
    document = fitz.open(pdf)
    zoom = dpi / 72.0
    matrix = fitz.Matrix(zoom, zoom)
    count = 0

    for page_index in range(len(document)):
        output = destination / f"{pdf.stem}_page_{page_index + 1:04d}.png"
        if output.exists() and not overwrite:
            print(f"SKIP exists: {output}")
            continue
        page = document[page_index]
        pixmap = page.get_pixmap(matrix=matrix, alpha=False)
        pixmap.save(output)
        count += 1

    document.close()
    return count


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract embedded images from PDFs.")
    parser.add_argument("path", type=Path, help="PDF file or folder containing PDFs.")
    parser.add_argument("-o", "--output", type=Path, help="Output root. Defaults beside each PDF.")
    parser.add_argument("--recursive", action="store_true", help="Search folders recursively.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing extracted images.")
    parser.add_argument("--render-pages", action="store_true", help="Render full pages to PNG instead of only extracting embedded images.")
    parser.add_argument("--dpi", type=int, default=200, help="DPI used with --render-pages.")
    parser.add_argument("--dry-run", action="store_true", help="Show planned work without extracting.")
    parser.add_argument("--no-auto-install", action="store_true", help="Do not try to install PyMuPDF automatically.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    fitz = ensure_pymupdf(no_auto_install=args.no_auto_install)

    target = args.path.resolve()
    if not target.exists():
        print(f"ERROR: Path does not exist: {target}", file=sys.stderr)
        return 1

    output_root = args.output.resolve() if args.output else None
    pdfs, scan_root = collect_pdfs(target, recursive=args.recursive)

    if not pdfs:
        print("No PDF files found.")
        return 0

    total = 0
    for pdf in pdfs:
        destination = output_folder_for(pdf, output_root, scan_root)
        mode = "render pages" if args.render_pages else "extract embedded images"
        verb = "WOULD" if args.dry_run else "DO"
        print(f"{verb} {mode}: {pdf} -> {destination}")
        if args.dry_run:
            continue
        try:
            if args.render_pages:
                count = render_pages(fitz, pdf, destination, dpi=args.dpi, overwrite=args.overwrite)
            else:
                count = extract_embedded_images(fitz, pdf, destination, overwrite=args.overwrite)
            total += count
            print(f"  wrote {count} file(s)")
        except Exception as exc:
            print(f"ERROR processing {pdf}: {exc}", file=sys.stderr)

    print(f"\nDone. Wrote {total} image file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
