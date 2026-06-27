#!/usr/bin/env python3
"""
zip_each_folder.py

Multithreaded folder-to-zip batch archiver.

This script scans one target directory, ignores loose files, finds every
immediate child folder, and creates one .zip archive per folder.

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

Loose files such as notes.txt and image.png are ignored.

Main features:

    - Ignores loose files in the target directory.
    - Zips each immediate folder into its own archive.
    - Runs multiple folder zips at the same time.
    - Shows terminal progress bars.
    - Skips existing zip files unless --overwrite is used.
    - Preserves empty directories.
    - Keeps each folder as the top-level directory inside its zip.
"""

import argparse
import os
import sys
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

try:
    from tqdm import tqdm
except ImportError:
    print("[ERROR] Missing dependency: tqdm", file=sys.stderr)
    print("Install it with:", file=sys.stderr)
    print("    python -m pip install tqdm", file=sys.stderr)
    sys.exit(1)


# This lock prevents multiple worker threads from writing to the terminal
# at exactly the same time.
#
# Without this lock, status messages from several threads could overlap and
# make the terminal output ugly.
print_lock = Lock()


def safe_print(message):
    """
    Print a message without corrupting tqdm progress bars.

    tqdm.write() is designed to print normal text while progress bars are
    active. It moves the bars out of the way, prints the message, and redraws
    the bars cleanly.
    """

    with print_lock:
        tqdm.write(message)


def collect_files_and_empty_dirs(folder_path):
    """
    Scan one folder and return everything that needs to go into its zip.

    Parameters
    ----------
    folder_path:
        The folder that will eventually become a .zip archive.

    Returns
    -------
    files_to_zip:
        List of real file paths that should be added to the zip archive.

    empty_dirs_to_zip:
        List of empty directory paths that should be explicitly preserved.

    Why this exists
    ---------------
    The zipfile module automatically stores files, but it does not always
    preserve empty folders unless we manually add them.

    This function walks the whole folder before zipping so we know:

        - how many files exist
        - which empty directories exist
        - how much total work the progress bar should track
    """

    files_to_zip = []
    empty_dirs_to_zip = []

    for current_root, dir_names, file_names in os.walk(folder_path):

        # If a directory has no child directories and no files, it is empty.
        #
        # Empty directories need special handling because normal zip creation
        # mostly stores files, not empty folders.
        if not dir_names and not file_names:
            empty_dirs_to_zip.append(current_root)

        # Store the full path for every file found inside this folder.
        for file_name in file_names:
            full_file_path = os.path.join(current_root, file_name)
            files_to_zip.append(full_file_path)

    return files_to_zip, empty_dirs_to_zip


def zip_folder(folder_path, zip_path, overwrite, file_progress_bar):
    """
    Zip one folder into one .zip archive.

    This function is designed to run inside a worker thread.

    Parameters
    ----------
    folder_path:
        Real folder on disk that should be archived.

    zip_path:
        Destination .zip file path.

    overwrite:
        If False, existing zip files are skipped.
        If True, existing zip files are replaced.

    file_progress_bar:
        Shared tqdm progress bar tracking total files zipped across all
        worker threads.

    Returns
    -------
    result:
        Dictionary describing what happened.

    Archive behavior
    ----------------
    The folder itself is included as the top-level item inside the zip.

    Example:

        ProjectA/
        ├── file1.txt
        └── subfolder/
            └── file2.txt

    Becomes:

        ProjectA/file1.txt
        ProjectA/subfolder/file2.txt

    This prevents messy extraction where files explode directly into the
    extraction directory.
    """

    folder_name = os.path.basename(folder_path)
    zip_name = os.path.basename(zip_path)

    # Skip safely if the zip already exists and overwrite mode is disabled.
    if os.path.exists(zip_path) and not overwrite:
        return {
            "folder": folder_name,
            "zip": zip_name,
            "status": "skipped",
            "message": f"[SKIP] {zip_name} already exists. Use --overwrite to replace it.",
            "files_zipped": 0,
        }

    try:
        files_to_zip, empty_dirs_to_zip = collect_files_and_empty_dirs(folder_path)

        # Open the destination archive in write mode.
        #
        # ZIP_DEFLATED gives normal compressed zip files.
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zip_file:

            # Preserve empty directories first.
            for empty_dir_path in empty_dirs_to_zip:

                # Store path relative to the parent of the folder being zipped.
                #
                # Example:
                #
                #   folder_path:
                #       /home/adam/archive/ProjectA
                #
                #   empty_dir_path:
                #       /home/adam/archive/ProjectA/empty_folder
                #
                #   archive_dir_name:
                #       ProjectA/empty_folder
                #
                archive_dir_name = os.path.relpath(
                    empty_dir_path,
                    os.path.dirname(folder_path)
                )

                # The trailing slash marks this zip entry as a directory.
                zip_file.writestr(archive_dir_name + "/", "")

            # Add every file to the archive.
            for real_file_path in files_to_zip:

                # Store path relative to the parent of the folder being zipped
                # so the folder itself appears in the archive.
                archive_file_name = os.path.relpath(
                    real_file_path,
                    os.path.dirname(folder_path)
                )

                zip_file.write(real_file_path, archive_file_name)

                # Update the shared progress bar by one file.
                #
                # tqdm is thread-safe for update() in normal use, so this works
                # cleanly with multiple zipping threads.
                file_progress_bar.update(1)

        return {
            "folder": folder_name,
            "zip": zip_name,
            "status": "zipped",
            "message": f"[DONE] {folder_name} -> {zip_name}",
            "files_zipped": len(files_to_zip),
        }

    except Exception as error:
        return {
            "folder": folder_name,
            "zip": zip_name,
            "status": "error",
            "message": f"[ERROR] Failed to zip {folder_name}: {error}",
            "files_zipped": 0,
        }


def find_folders_to_zip(target_dir, output_dir):
    """
    Find only immediate child folders inside the target directory.

    Loose files are ignored.

    This means the script only processes folders like:

        target_dir/FolderA
        target_dir/FolderB
        target_dir/FolderC

    It does not process loose files like:

        target_dir/notes.txt
        target_dir/image.png
        target_dir/old_archive.zip
    """

    folders = []

    for item_name in os.listdir(target_dir):
        item_path = os.path.join(target_dir, item_name)

        # Ignore loose files.
        if not os.path.isdir(item_path):
            continue

        # Avoid zipping the output directory if the output directory lives
        # inside the target directory.
        if os.path.abspath(item_path) == os.path.abspath(output_dir):
            continue

        folders.append(item_path)

    folders.sort()
    return folders


def count_total_files(folders):
    """
    Count total files across all folders before zipping starts.

    This gives the file progress bar an accurate total.

    Empty folders do not increase this count because they are preserved as
    directory entries, not file entries.
    """

    total_files = 0

    for folder_path in folders:
        for current_root, dir_names, file_names in os.walk(folder_path):
            total_files += len(file_names)

    return total_files


def main():
    """
    Main command-line entry point.
    """

    parser = argparse.ArgumentParser(
        description="Multithreaded zip utility that zips every immediate folder into its own archive."
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
        "-w",
        "--workers",
        type=int,
        default=4,
        help="Number of folders to zip at the same time. Defaults to 4."
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing zip files instead of skipping them."
    )

    args = parser.parse_args()

    target_dir = os.path.abspath(os.path.expanduser(args.directory))

    if not os.path.exists(target_dir):
        print(f"[ERROR] Directory does not exist: {target_dir}", file=sys.stderr)
        return 1

    if not os.path.isdir(target_dir):
        print(f"[ERROR] Not a directory: {target_dir}", file=sys.stderr)
        return 1

    if args.output:
        output_dir = os.path.abspath(os.path.expanduser(args.output))
    else:
        output_dir = target_dir

    os.makedirs(output_dir, exist_ok=True)

    if args.workers < 1:
        print("[ERROR] --workers must be 1 or higher.", file=sys.stderr)
        return 1

    folders_to_zip = find_folders_to_zip(target_dir, output_dir)

    if not folders_to_zip:
        print("[INFO] No folders found. Loose files were ignored.")
        return 0

    total_files = count_total_files(folders_to_zip)

    print(f"[INFO] Target directory: {target_dir}")
    print(f"[INFO] Output directory: {output_dir}")
    print(f"[INFO] Folders found:    {len(folders_to_zip)}")
    print(f"[INFO] Files found:      {total_files}")
    print(f"[INFO] Worker threads:   {args.workers}")
    print()

    # Folder progress tracks completed folder archives.
    folder_progress_bar = tqdm(
        total=len(folders_to_zip),
        desc="Folders zipped",
        unit="folder",
        position=0
    )

    # File progress tracks total files written into zip archives.
    file_progress_bar = tqdm(
        total=total_files,
        desc="Files archived",
        unit="file",
        position=1
    )

    results = []

    try:
        with ThreadPoolExecutor(max_workers=args.workers) as executor:

            futures = []

            for folder_path in folders_to_zip:
                folder_name = os.path.basename(folder_path)
                zip_file_name = folder_name + ".zip"
                zip_path = os.path.join(output_dir, zip_file_name)

                future = executor.submit(
                    zip_folder,
                    folder_path,
                    zip_path,
                    args.overwrite,
                    file_progress_bar
                )

                futures.append(future)

            for future in as_completed(futures):
                result = future.result()
                results.append(result)

                folder_progress_bar.update(1)

                if result["status"] == "error":
                    safe_print(result["message"])

    finally:
        folder_progress_bar.close()
        file_progress_bar.close()

    zipped_count = 0
    skipped_count = 0
    error_count = 0

    for result in results:
        if result["status"] == "zipped":
            zipped_count += 1
        elif result["status"] == "skipped":
            skipped_count += 1
        elif result["status"] == "error":
            error_count += 1

    print()
    print("[SUMMARY]")
    print(f"  Zipped:  {zipped_count}")
    print(f"  Skipped: {skipped_count}")
    print(f"  Errors:  {error_count}")

    if error_count > 0:
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
