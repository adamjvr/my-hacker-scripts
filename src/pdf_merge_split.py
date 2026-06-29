#!/usr/bin/env python3
"""
pdf_merge_split.py

Merge, split, and extract pages from PDF files using pypdf.

This is the boring PDF utility you always end up needing: combine a bunch of
PDFs, split one monster PDF into page files, or pull out page ranges without
opening some bloated GUI app.

Dependency policy:
    - Requires pypdf.
    - If pypdf is missing, the script tries to install it at runtime with pip.
    - Use --no-auto-install if you want it to fail instead.

Examples:
    python pdf_merge_split.py merge a.pdf b.pdf c.pdf -o merged.pdf
    python pdf_merge_split.py split manual.pdf -o pages
    python pdf_merge_split.py split manual.pdf -o chunks --chunk-size 10
    python pdf_merge_split.py extract manual.pdf --pages 1-3,7,10 -o excerpt.pdf
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


def ensure_pypdf(no_auto_install: bool):
    """Import pypdf, installing it first if needed."""

    if importlib.util.find_spec("pypdf") is None:
        print("Missing Python dependency: pypdf")
        if not pip_install("pypdf", no_auto_install=no_auto_install):
            raise SystemExit("ERROR: pypdf is missing. Install it manually with:\n  python3 -m pip install --user pypdf")

    from pypdf import PdfReader, PdfWriter  # type: ignore
    return PdfReader, PdfWriter


def parse_page_ranges(text: str, page_count: int) -> list[int]:
    """Parse human page ranges into zero-based page indexes.

    User-facing pages are 1-based because humans are not PDF internals. pypdf is
    zero-based because programming. This function is the translation layer.
    """

    indexes: list[int] = []

    for part in text.split(","):
        part = part.strip()
        if not part:
            continue

        if "-" in part:
            start_text, end_text = part.split("-", 1)
            start = int(start_text)
            end = int(end_text)
            if start > end:
                raise ValueError(f"Invalid descending page range: {part}")
            indexes.extend(range(start - 1, end))
        else:
            indexes.append(int(part) - 1)

    for index in indexes:
        if index < 0 or index >= page_count:
            raise ValueError(f"Page out of range: {index + 1} (PDF has {page_count} page(s))")

    # Preserve user order but remove duplicates. Ordered dict trick without
    # importing anything extra.
    return list(dict.fromkeys(indexes))


def merge_pdfs(PdfReader, PdfWriter, inputs: list[Path], output: Path, overwrite: bool) -> None:
    """Merge PDFs into one output file."""

    if output.exists() and not overwrite:
        raise FileExistsError(f"Output exists: {output} (use --overwrite)")

    writer = PdfWriter()

    for pdf in inputs:
        reader = PdfReader(str(pdf))
        for page in reader.pages:
            writer.add_page(page)

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("wb") as handle:
        writer.write(handle)


def split_pdf(PdfReader, PdfWriter, input_pdf: Path, output_dir: Path, chunk_size: int, overwrite: bool) -> int:
    """Split a PDF into single pages or chunks."""

    reader = PdfReader(str(input_pdf))
    output_dir.mkdir(parents=True, exist_ok=True)
    written = 0

    total_pages = len(reader.pages)
    for start in range(0, total_pages, chunk_size):
        end = min(start + chunk_size, total_pages)
        writer = PdfWriter()

        for page_index in range(start, end):
            writer.add_page(reader.pages[page_index])

        if chunk_size == 1:
            output = output_dir / f"{input_pdf.stem}_page_{start + 1:04d}.pdf"
        else:
            output = output_dir / f"{input_pdf.stem}_pages_{start + 1:04d}-{end:04d}.pdf"

        if output.exists() and not overwrite:
            print(f"SKIP exists: {output}")
            continue

        with output.open("wb") as handle:
            writer.write(handle)
        written += 1

    return written


def extract_pages(PdfReader, PdfWriter, input_pdf: Path, pages: str, output: Path, overwrite: bool) -> None:
    """Extract selected pages into one new PDF."""

    if output.exists() and not overwrite:
        raise FileExistsError(f"Output exists: {output} (use --overwrite)")

    reader = PdfReader(str(input_pdf))
    indexes = parse_page_ranges(pages, page_count=len(reader.pages))
    writer = PdfWriter()

    for index in indexes:
        writer.add_page(reader.pages[index])

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("wb") as handle:
        writer.write(handle)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Merge, split, and extract PDF pages.")
    parser.add_argument("--no-auto-install", action="store_true", help="Do not try to install pypdf automatically.")

    subparsers = parser.add_subparsers(dest="command", required=True)

    merge = subparsers.add_parser("merge", help="Merge multiple PDFs into one PDF.")
    merge.add_argument("inputs", type=Path, nargs="+", help="Input PDF files in order.")
    merge.add_argument("-o", "--output", type=Path, required=True, help="Merged output PDF.")
    merge.add_argument("--overwrite", action="store_true", help="Overwrite output if it exists.")

    split = subparsers.add_parser("split", help="Split one PDF into page/chunk PDFs.")
    split.add_argument("input", type=Path, help="Input PDF.")
    split.add_argument("-o", "--output", type=Path, required=True, help="Output folder.")
    split.add_argument("--chunk-size", type=int, default=1, help="Pages per output PDF. Default 1.")
    split.add_argument("--overwrite", action="store_true", help="Overwrite output files if they exist.")

    extract = subparsers.add_parser("extract", help="Extract selected pages into one PDF.")
    extract.add_argument("input", type=Path, help="Input PDF.")
    extract.add_argument("--pages", required=True, help="Page list/ranges like 1-3,7,10.")
    extract.add_argument("-o", "--output", type=Path, required=True, help="Output PDF.")
    extract.add_argument("--overwrite", action="store_true", help="Overwrite output if it exists.")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv or sys.argv[1:])
    PdfReader, PdfWriter = ensure_pypdf(no_auto_install=args.no_auto_install)

    try:
        if args.command == "merge":
            inputs = [path.resolve() for path in args.inputs]
            for path in inputs:
                if not path.exists() or path.suffix.lower() != ".pdf":
                    raise FileNotFoundError(f"Missing PDF input: {path}")
            output = args.output.resolve()
            merge_pdfs(PdfReader, PdfWriter, inputs, output, overwrite=args.overwrite)
            print(f"Merged {len(inputs)} PDF(s) -> {output}")

        elif args.command == "split":
            input_pdf = args.input.resolve()
            if args.chunk_size < 1:
                raise ValueError("--chunk-size must be at least 1")
            if not input_pdf.exists() or input_pdf.suffix.lower() != ".pdf":
                raise FileNotFoundError(f"Missing PDF input: {input_pdf}")
            written = split_pdf(PdfReader, PdfWriter, input_pdf, args.output.resolve(), chunk_size=args.chunk_size, overwrite=args.overwrite)
            print(f"Split wrote {written} PDF file(s) -> {args.output.resolve()}")

        elif args.command == "extract":
            input_pdf = args.input.resolve()
            if not input_pdf.exists() or input_pdf.suffix.lower() != ".pdf":
                raise FileNotFoundError(f"Missing PDF input: {input_pdf}")
            output = args.output.resolve()
            extract_pages(PdfReader, PdfWriter, input_pdf, args.pages, output, overwrite=args.overwrite)
            print(f"Extracted pages {args.pages} -> {output}")

    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
