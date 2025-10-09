#!/usr/bin/env python3
"""
img2img.py
----------
Multithreaded Image Format Converter with Compression, Progress Display, and
Optional Output Directory Selection.

Description:
------------
This Python script allows you to convert a batch of images (either from a folder
or from within a ZIP archive) into a desired output format (PNG, JPEG, GIF, WebP).
It supports adjustable compression levels (0–9), multithreading for faster
processing, a live progress bar, and an optional user-specified output folder.

Author: Adam Vadala-Roth
Date: 2025-10-09

Usage Examples:
---------------
# Convert a folder of images to PNG with compression level 6
python img2img.py /path/to/folder -p -c 6

# Convert a ZIP of images to JPEG with compression level 3
python img2img.py /path/to/images.zip -jp -c 3

# Convert a folder to WebP using 8 threads, saving results to a custom output directory
python img2img.py ./my_images -we -t 8 -o ./converted
"""

# ============================
# Standard Library Imports
# ============================

import os
import sys
import argparse  # For parsing command-line arguments
import tempfile  # For creating temporary directories (used for ZIP extraction)
import zipfile  # For handling ZIP archives
from pathlib import Path  # For convenient filesystem path operations
from concurrent.futures import ThreadPoolExecutor, as_completed  # For multithreading
import multiprocessing  # To detect the number of CPU cores
from tqdm import tqdm  # For showing progress bars

# ============================
# Third-Party Library Imports
# ============================

# Pillow (PIL) is used for all image operations such as reading and saving.
# If not installed, install it using:
#     pip install pillow
from PIL import Image


# ============================
# Helper Functions
# ============================


def extract_zip(zip_path):
    """
    Extract a ZIP archive containing images into a temporary directory.

    Parameters:
    -----------
    zip_path : str or Path
        The path to the .zip file containing images.

    Returns:
    --------
    temp_dir : str
        Path to the temporary directory where the ZIP contents were extracted.

    Notes:
    ------
    - This function uses tempfile.mkdtemp() to create a unique folder.
    - The folder is automatically placed in the system's temporary directory.
    - The extracted folder is used as the working directory for conversions.
    """
    temp_dir = tempfile.mkdtemp(prefix="img2img_")
    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(temp_dir)
    return temp_dir


def convert_image(input_path, output_dir, fmt, compression_level):
    """
    Convert a single image file into the target format with optional compression.

    Parameters:
    -----------
    input_path : str or Path
        Path to the source image file to convert.
    output_dir : str or Path
        Directory where the converted image should be saved.
    fmt : str
        Target format to convert to (e.g. "PNG", "JPEG", "GIF", "WEBP").
    compression_level : int
        Compression level (0–9) where 0 = least compression (highest quality)
        and 9 = most compression (lowest quality).

    Returns:
    --------
    result_message : str
        String describing the result, either "[OK] filename" or "[ERROR] filename: reason".

    Notes:
    ------
    - Automatically skips non-image files if they cannot be opened.
    - Converts all images to RGB color mode for format consistency.
    - Each image is saved with format-specific compression parameters.
    """
    try:
        with Image.open(input_path) as img:
            base_name = Path(input_path).stem
            output_path = os.path.join(output_dir, f"{base_name}.{fmt.lower()}")
            save_kwargs = {}

            # Adjust compression/quality parameters depending on format
            if fmt == "JPEG":
                quality = max(1, 95 - compression_level * 10)
                save_kwargs = {"quality": quality, "optimize": True}
            elif fmt == "PNG":
                save_kwargs = {"compress_level": compression_level}
            elif fmt == "WEBP":
                quality = max(1, 95 - compression_level * 10)
                save_kwargs = {"quality": quality}
            elif fmt == "GIF":
                save_kwargs = {"optimize": True}

            # Convert to RGB to avoid errors (e.g. saving RGBA as JPEG)
            img.convert("RGB").save(output_path, fmt, **save_kwargs)
            return f"[OK] {os.path.basename(input_path)}"

    except Exception as e:
        return f"[ERROR] {os.path.basename(input_path)}: {e}"


def get_all_images(folder):
    """
    Recursively find all supported image files in a given directory.

    Parameters:
    -----------
    folder : str or Path
        Path to directory where image files will be searched.

    Returns:
    --------
    image_files : list
        A list of full file paths to image files.

    Notes:
    ------
    - Searches all subdirectories recursively.
    - Only files with known image extensions are included.
    """
    exts = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".webp")
    return [
        os.path.join(dp, f)
        for dp, _, files in os.walk(folder)
        for f in files
        if f.lower().endswith(exts)
    ]


# ============================
# Main Function
# ============================


def main():
    """
    Main program entry point.

    Handles:
    - Parsing command-line arguments
    - Validating user input
    - Extracting ZIP archives (if provided)
    - Spawning multiple threads for image conversion
    - Displaying progress and summary statistics
    """

    # ---------------------------
    # Argument Parsing
    # ---------------------------
    parser = argparse.ArgumentParser(
        description="Convert images in bulk to another format with optional compression."
    )

    parser.add_argument("path", help="Path to a folder or ZIP file containing images.")
    parser.add_argument(
        "-c",
        "--compression",
        type=int,
        default=5,
        help="Compression level (0–9). Default=5.",
    )
    parser.add_argument("-p", action="store_true", help="Convert to PNG format.")
    parser.add_argument("-jp", action="store_true", help="Convert to JPEG format.")
    parser.add_argument("-g", action="store_true", help="Convert to GIF format.")
    parser.add_argument("-we", action="store_true", help="Convert to WebP format.")
    parser.add_argument(
        "-t",
        "--threads",
        type=int,
        default=multiprocessing.cpu_count(),
        help="Number of threads to use. Default = number of CPU cores.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default=None,
        help="Optional custom output directory. Default: auto-named next to input folder.",
    )

    args = parser.parse_args()

    # ---------------------------
    # Determine Format
    # ---------------------------
    format_map = {"p": "PNG", "jp": "JPEG", "g": "GIF", "we": "WEBP"}
    selected_format = None
    for key, fmt in format_map.items():
        if getattr(args, key):
            selected_format = fmt
            break

    if not selected_format:
        print("Error: You must specify a target format (-p, -jp, -g, or -we).")
        sys.exit(1)

    # ---------------------------
    # Validate Compression Level
    # ---------------------------
    if not (0 <= args.compression <= 9):
        print("Error: Compression must be between 0 and 9.")
        sys.exit(1)

    # ---------------------------
    # Validate and Prepare Input
    # ---------------------------
    input_path = Path(args.path)
    if not input_path.exists():
        print(f"Error: Path not found: {input_path}")
        sys.exit(1)

    if zipfile.is_zipfile(input_path):
        print(f"Extracting ZIP archive: {input_path}")
        working_dir = extract_zip(input_path)
    elif input_path.is_dir():
        working_dir = input_path
    else:
        print("Error: Path must be a folder or a ZIP archive.")
        sys.exit(1)

    # ---------------------------
    # Prepare Output Directory
    # ---------------------------
    if args.output:
        output_dir = Path(args.output)
    else:
        output_dir = Path(f"{working_dir}_converted_{selected_format.lower()}")

    os.makedirs(output_dir, exist_ok=True)

    # ---------------------------
    # Gather Image Files
    # ---------------------------
    images = get_all_images(working_dir)
    if not images:
        print("No images found to convert.")
        sys.exit(0)

    print(
        f"Converting {len(images)} images to {selected_format} using {args.threads} threads..."
    )
    print(f"Output directory: {output_dir}\n")

    # ---------------------------
    # Multithreaded Conversion
    # ---------------------------
    results = []
    with ThreadPoolExecutor(max_workers=args.threads) as executor:
        futures = {
            executor.submit(
                convert_image, img, output_dir, selected_format, args.compression
            ): img
            for img in images
        }

        for future in tqdm(
            as_completed(futures), total=len(futures), desc="Converting", unit="img"
        ):
            results.append(future.result())

    # ---------------------------
    # Print Conversion Summary
    # ---------------------------
    success_count = sum(1 for r in results if r.startswith("[OK]"))
    fail_count = len(results) - success_count

    print("\n--- Conversion Summary ---")
    for r in results:
        print(r)

    print(f"\n✅ Done! {success_count} succeeded, {fail_count} failed.")
    print(f"Output folder: {output_dir}\n")


# ============================
# Script Entry Point
# ============================

if __name__ == "__main__":
    main()
