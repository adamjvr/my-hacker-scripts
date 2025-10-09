#!/usr/bin/env python3
"""
img2img.py
----------
Multithreaded Image Format Converter with Compression and Progress Display.

Description:
------------
This Python script allows you to convert a batch of images (either from a folder
or from within a ZIP archive) into a desired output format (PNG, JPEG, GIF, WebP).
It supports adjustable compression levels (0–9), multithreading for faster
processing, and a live progress bar.

Author: Adam Vadala-Roth
Date: 2025-10-09

Usage Examples:
---------------
# Convert a folder of images to PNG with compression level 6
python img2img.py /path/to/folder -p -c 6

# Convert a ZIP of images to JPEG with compression level 3
python img2img.py /path/to/images.zip -jp -c 3

# Convert a folder to WebP using 8 threads
python img2img.py ./my_images -we -t 8
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
# If not installed, install with: pip install pillow
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
    - The folder is automatically placed in the system's temp directory.
    - The function assumes the ZIP archive contains image files.
    """
    temp_dir = tempfile.mkdtemp(prefix="img2img_")  # Create temp folder
    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(temp_dir)  # Extract contents
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
        # Open the image file using Pillow (PIL)
        with Image.open(input_path) as img:
            # Extract base filename (without extension)
            base_name = Path(input_path).stem

            # Construct the new output path for the converted image
            output_path = os.path.join(output_dir, f"{base_name}.{fmt.lower()}")

            # Dictionary that will hold the format-specific save parameters
            save_kwargs = {}

            # Handle compression/quality parameters based on selected format
            if fmt == "JPEG":
                # JPEG uses "quality" parameter from 1 to 95 (higher = better quality)
                # Compression level 0 → quality 95; Compression level 9 → quality 5
                quality = max(1, 95 - compression_level * 10)
                save_kwargs = {"quality": quality, "optimize": True}

            elif fmt == "PNG":
                # PNG uses a compression level from 0 (none) to 9 (maximum)
                save_kwargs = {"compress_level": compression_level}

            elif fmt == "WEBP":
                # WebP uses quality similar to JPEG
                quality = max(1, 95 - compression_level * 10)
                save_kwargs = {"quality": quality}

            elif fmt == "GIF":
                # GIF doesn’t use numeric compression but can be optimized
                save_kwargs = {"optimize": True}

            # Convert the image to RGB color mode to ensure compatibility with all formats
            img.convert("RGB").save(output_path, fmt, **save_kwargs)

            # Return a success message
            return f"[OK] {os.path.basename(input_path)}"

    except Exception as e:
        # Catch and return any exception that occurred during conversion
        return f"[ERROR] {os.path.basename(input_path)}: {e}"


def get_all_images(folder):
    """
    Recursively list all supported image files in a directory.

    Parameters:
    -----------
    folder : str or Path
        Directory to scan for image files.

    Returns:
    --------
    image_files : list
        List of full paths to all supported images found in the directory.

    Notes:
    ------
    - Searches recursively (includes subfolders).
    - Only files with known image extensions are included.
    """
    # Define supported extensions
    exts = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".webp")

    # Walk through directory tree and collect valid image file paths
    return [
        os.path.join(dp, f)
        for dp, _, files in os.walk(folder)
        for f in files
        if f.lower().endswith(exts)
    ]


# ============================
# Main Program Entry Point
# ============================


def main():
    """
    Main function that parses command-line arguments, validates input,
    sets up multithreading, and executes the image conversion pipeline.
    """

    # ---------------------------
    # Argument Parser Setup
    # ---------------------------

    parser = argparse.ArgumentParser(
        description="Convert images in bulk to another format with optional compression."
    )

    # Required positional argument: path to folder or ZIP file
    parser.add_argument(
        "path", help="Path to a folder of images or a ZIP file containing images."
    )

    # Optional arguments:
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
        help="Number of threads to use (default = number of CPU cores).",
    )

    # Parse command-line arguments into the 'args' object
    args = parser.parse_args()

    # ---------------------------
    # Determine Target Format
    # ---------------------------

    # Map argument flags to their corresponding image formats
    format_map = {"p": "PNG", "jp": "JPEG", "g": "GIF", "we": "WEBP"}

    # Check which format flag was used and store the result
    selected_format = None
    for key, fmt in format_map.items():
        if getattr(args, key):
            selected_format = fmt
            break

    # If no format flag was provided, print error and exit
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
    # Validate Input Path
    # ---------------------------

    input_path = Path(args.path)

    # If input path doesn’t exist, abort
    if not input_path.exists():
        print(f"Error: Path not found: {input_path}")
        sys.exit(1)

    # If path is a ZIP file, extract it first
    if zipfile.is_zipfile(input_path):
        print(f"Extracting ZIP archive: {input_path}")
        working_dir = extract_zip(input_path)

    # If it’s a directory, use it directly
    elif input_path.is_dir():
        working_dir = input_path

    # Otherwise, reject it as an invalid input
    else:
        print("Error: Path must be a folder or a ZIP archive.")
        sys.exit(1)

    # ---------------------------
    # Prepare Output Directory
    # ---------------------------

    # Create an output folder based on the input name and target format
    output_dir = Path(f"{working_dir}_converted_{selected_format.lower()}")
    os.makedirs(output_dir, exist_ok=True)  # Ensure directory exists

    # ---------------------------
    # Collect Image Files
    # ---------------------------

    images = get_all_images(working_dir)

    if not images:
        print("No images found to convert.")
        sys.exit(0)

    # Display summary before conversion
    print(
        f"Converting {len(images)} images to {selected_format} using {args.threads} threads...\n"
    )

    # ---------------------------
    # Multithreaded Conversion
    # ---------------------------

    results = []

    # ThreadPoolExecutor allows parallel conversion of multiple images.
    # Each thread handles one image at a time.
    with ThreadPoolExecutor(max_workers=args.threads) as executor:
        # Submit each conversion task to the thread pool
        futures = {
            executor.submit(
                convert_image, img, output_dir, selected_format, args.compression
            ): img
            for img in images
        }

        # Use tqdm to display progress bar as each image completes
        for future in tqdm(
            as_completed(futures), total=len(futures), desc="Converting", unit="img"
        ):
            result = future.result()  # Retrieve the result string from each thread
            results.append(result)

    # ---------------------------
    # Post-Processing and Summary
    # ---------------------------

    # Count success and failure results for summary
    success_count = sum(1 for r in results if r.startswith("[OK]"))
    fail_count = len(results) - success_count

    # Print summary of all results
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
