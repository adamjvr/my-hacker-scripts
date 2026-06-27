#!/usr/bin/env python3
"""
zip_each_folder.py

Zip every folder in a target directory into its own .zip archive.

This script is meant for a simple workflow:

    - Look inside one directory.
    - Ignore all loose files in that directory.
    - Find every immediate folder.
    - Create one .zip file for each folder.

Example:

    Before:

        my_stuff/
        ├── ProjectA/
        ├── ProjectB/
        ├── ProjectC/
        ├── notes.txt
        └── image.png

    Command:

        python zip_each_folder.py my_stuff

    After:

        my_stuff/
        ├── ProjectA/
        ├── ProjectA.zip
        ├── ProjectB/
        ├── ProjectB.zip
        ├── ProjectC/
        ├── ProjectC.zip
        ├── notes.txt
        └── image.png

The loose files notes.txt and image.png are ignored.

Only Python standard library modules are used.
No pip installs required.
"""

import argparse
import os
import sys
import zipfile


def zip_folder(folder_path, zip_path, overwrite=False):
    """
    Create a zip file from a single folder.

    folder_path:
        The folder that should be zipped.

    zip_path:
        The final .zip archive path.

    overwrite:
        If False, skip the zip if it already exists.
        If True, replace the existing zip.

    Important archive behavior:

        The folder itself is included inside the zip.

        So this:

            ProjectA/
            ├── file1.txt
            └── subfolder/
                └── file2.txt

        Becomes this inside ProjectA.zip:

            ProjectA/file1.txt
            ProjectA/subfolder/file2.txt

        This is better than dumping file1.txt directly into the root
        of the zip archive.
    """

    # If the archive already exists and overwrite mode is not enabled,
    # skip this folder instead of destroying an existing archive.
    if os.path.exists(zip_path) and not overwrite:
        print(f"[SKIP] {os.path.basename(zip_path)} already exists. Use --overwrite to replace it.")
        return

    print(f"[ZIP ] {os.path.basename(folder_path)} -> {os.path.basename(zip_path)}")

    # Open the zip file in write mode.
    #
    # ZIP_DEFLATED means normal compressed zip output.
    # This is the standard compression mode people expect from .zip files.
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zip_file:

        # Walk through the folder recursively.
        #
        # os.walk gives us:
        #
        #   current_root:
        #       The folder currently being inspected.
        #
        #   dir_names:
        #       Subdirectories inside current_root.
        #
        #   file_names:
        #       Files inside current_root.
        #
        for current_root, dir_names, file_names in os.walk(folder_path):

            # First, preserve empty directories.
            #
            # Zip files do not always store empty folders automatically,
            # because normally only files are written.
            #
            # If a directory has no subdirectories and no files, we manually
            # add a directory entry ending in "/".
            if not dir_names and not file_names:
                archive_dir_name = os.path.relpath(current_root, os.path.dirname(folder_path))
                zip_file.writestr(archive_dir_name + "/", "")

            # Now add every file in the current folder.
            for file_name in file_names:

                # Full path to the real file on disk.
                real_file_path = os.path.join(current_root, file_name)

                # Path that will be stored inside the zip.
                #
                # This is relative to the parent of folder_path so the folder
                # name itself appears inside the archive.
                #
                # Example:
                #
                #   real_file_path:
                #       /home/adam/stuff/ProjectA/file.txt
                #
                #   archive_file_name:
                #       ProjectA/file.txt
                #
                archive_file_name = os.path.relpath(
                    real_file_path,
                    os.path.dirname(folder_path)
                )

                # Add the file to the zip archive.
                zip_file.write(real_file_path, archive_file_name)


def main():
    """
    Main command-line entry point.
    """

    parser = argparse.ArgumentParser(
        description="Zip every immediate folder into its own .zip file and ignore loose files."
    )

    parser.add_argument(
        "directory",
        nargs="?",
        default=".",
        help="Directory containing folders to zip. Defaults to the current directory."
    )

    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Directory where zip files should be written. Defaults to the target directory."
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing zip files instead of skipping them."
    )

    args = parser.parse_args()

    # Convert the target directory into an absolute path.
    #
    # expanduser allows paths like:
    #
    #   ~/Downloads
    #
    # abspath normalizes it into a full filesystem path.
    target_dir = os.path.abspath(os.path.expanduser(args.directory))

    # Make sure the target exists.
    if not os.path.exists(target_dir):
        print(f"[ERROR] Directory does not exist: {target_dir}", file=sys.stderr)
        return 1

    # Make sure the target is actually a directory.
    if not os.path.isdir(target_dir):
        print(f"[ERROR] Not a directory: {target_dir}", file=sys.stderr)
        return 1

    # Decide where to put the zip files.
    #
    # If the user gave --output, use that folder.
    # Otherwise, put the zip files in the same folder being scanned.
    if args.output:
        output_dir = os.path.abspath(os.path.expanduser(args.output))
    else:
        output_dir = target_dir

    # Create the output directory if needed.
    os.makedirs(output_dir, exist_ok=True)

    # Find only the immediate folders inside target_dir.
    #
    # This intentionally ignores loose files.
    folders_to_zip = []

    for item_name in os.listdir(target_dir):

        # Full path to this item.
        item_path = os.path.join(target_dir, item_name)

        # Ignore loose files.
        #
        # This means things like .txt, .jpg, .zip, .pdf, etc.
        # sitting directly in target_dir will not be touched.
        if not os.path.isdir(item_path):
            continue

        # Avoid trying to zip the output folder if the output folder is
        # located inside the target directory.
        #
        # Example:
        #
        #   python zip_each_folder.py ./stuff -o ./stuff/zips
        #
        # In that case, ./stuff/zips should not become zips.zip.
        if os.path.abspath(item_path) == os.path.abspath(output_dir):
            continue

        folders_to_zip.append(item_path)

    # Sort folders alphabetically so the output order is predictable.
    folders_to_zip.sort()

    # If no folders were found, exit cleanly.
    if not folders_to_zip:
        print("[INFO] No folders found. Loose files were ignored.")
        return 0

    # Create one zip archive per folder.
    for folder_path in folders_to_zip:

        # The zip filename is the folder name plus .zip.
        #
        # Example:
        #
        #   ProjectA/
        #
        # becomes:
        #
        #   ProjectA.zip
        folder_name = os.path.basename(folder_path)
        zip_file_name = folder_name + ".zip"
        zip_path = os.path.join(output_dir, zip_file_name)

        zip_folder(folder_path, zip_path, overwrite=args.overwrite)

    print("[DONE] Folder zipping complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
