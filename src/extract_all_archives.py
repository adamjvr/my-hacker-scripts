#!/usr/bin/env python3
"""
extract_all_archives.py

Recursively extract archive files into clean folders.

This is the inverse of zip_each_folder.py energy: instead of packing each folder,
this opens up a mess of downloaded ZIP/TAR/7Z/RAR files and puts each one into
its own destination folder so you can actually inspect the contents.

Dependency policy:
    - Built-in formats use the Python standard library:
        .zip, .tar, .tar.gz, .tgz, .tar.bz2, .tbz2, .tar.xz, .txz, .gz, .bz2, .xz
    - .7z needs the external 7z command from p7zip-full.
    - .rar needs unrar or 7z.
    - If a needed command is missing, the script tries to install it at runtime
      using apt-get on Debian/Ubuntu/Pop!_OS style systems.

Yes, runtime installs are a little aggressive. That is intentional here because
this script collection is supposed to be useful when you just run the damn tool.
Use --no-auto-install if you want it to fail instead of trying to bootstrap deps.

Examples:
    python extract_all_archives.py ./downloads
    python extract_all_archives.py ./downloads --recursive
    python extract_all_archives.py ./downloads -o ./extracted --delete-original
    python extract_all_archives.py ./downloads --dry-run
"""

from __future__ import annotations

import argparse
import bz2
import gzip
import lzma
import os
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path


ARCHIVE_SUFFIXES = (
    ".zip", ".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tbz2", ".tar.xz", ".txz",
    ".gz", ".bz2", ".xz", ".7z", ".rar",
)


def run_command(command: list[str]) -> bool:
    """Run a command and return True on success.

    We keep this wrapper tiny because dependency bootstrapping is supposed to be
    boring. The script prints the command so the user can see exactly what it is
    trying to do instead of silently invoking package-manager wizardry.
    """

    print("Dependency bootstrap:", " ".join(command))
    try:
        subprocess.check_call(command)
        return True
    except (OSError, subprocess.CalledProcessError):
        return False


def apt_install(package: str, no_auto_install: bool) -> bool:
    """Try to install an apt package.

    This targets the user's normal Linux environment: Ubuntu/Pop!_OS/Debian-ish.
    If apt-get is not available, or if sudo is unavailable, we fail cleanly and
    tell the user what to install manually.
    """

    if no_auto_install:
        return False
    if not shutil.which("apt-get"):
        return False

    if os.geteuid() == 0:
        return run_command(["apt-get", "update"]) and run_command(["apt-get", "install", "-y", package])

    if shutil.which("sudo"):
        # sudo may ask for a password if run interactively. That is fine for a
        # local utility script. In non-interactive runs it will just fail and the
        # error message below will tell the user what to do.
        return run_command(["sudo", "apt-get", "update"]) and run_command(["sudo", "apt-get", "install", "-y", package])

    return False


def ensure_command(binary: str, apt_package: str, no_auto_install: bool) -> None:
    """Ensure an external command exists, trying apt install if needed."""

    if shutil.which(binary):
        return

    print(f"Missing dependency: {binary}")
    if apt_install(apt_package, no_auto_install=no_auto_install) and shutil.which(binary):
        return

    raise SystemExit(
        f"ERROR: Required command '{binary}' is missing. Install it manually with:\n"
        f"  sudo apt install {apt_package}"
    )


def archive_kind(path: Path) -> str | None:
    """Return a normalized archive kind string or None."""

    name = path.name.lower()
    for suffix in ARCHIVE_SUFFIXES:
        if name.endswith(suffix):
            return suffix.lstrip(".")
    return None


def output_folder_for(archive: Path, output_root: Path | None, input_root: Path | None) -> Path:
    """Compute where one archive should be extracted."""

    archive_name = archive.name
    lower = archive_name.lower()

    for suffix in [".tar.gz", ".tar.bz2", ".tar.xz", ".tgz", ".tbz2", ".txz", ".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar"]:
        if lower.endswith(suffix):
            archive_name = archive_name[: -len(suffix)]
            break

    if output_root is None:
        return archive.with_name(archive_name)

    if input_root is not None:
        try:
            relative_parent = archive.parent.relative_to(input_root)
            return output_root / relative_parent / archive_name
        except ValueError:
            pass

    return output_root / archive_name


def safe_target(base: Path, candidate: Path) -> bool:
    """Prevent archive path traversal.

    Archives can contain entries like ../../evil.sh. That is not extraction, that
    is a filesystem shank. For zip/tar handled in Python, we validate paths so
    files stay inside the intended output folder.
    """

    try:
        candidate.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False


def extract_zip(archive: Path, destination: Path) -> None:
    with zipfile.ZipFile(archive) as zf:
        for member in zf.infolist():
            target = destination / member.filename
            if not safe_target(destination, target):
                raise RuntimeError(f"Unsafe zip member path blocked: {member.filename}")
        zf.extractall(destination)


def extract_tar(archive: Path, destination: Path) -> None:
    with tarfile.open(archive) as tf:
        for member in tf.getmembers():
            target = destination / member.name
            if not safe_target(destination, target):
                raise RuntimeError(f"Unsafe tar member path blocked: {member.name}")
        tf.extractall(destination)


def extract_single_compressed(archive: Path, destination: Path, opener) -> None:
    """Extract .gz/.bz2/.xz single-file compression.

    These are not container archives like ZIP. They usually represent one
    compressed file. We write the decompressed file inside the destination folder.
    """

    output_name = archive.stem
    destination.mkdir(parents=True, exist_ok=True)
    output_file = destination / output_name

    with opener(archive, "rb") as src, output_file.open("wb") as dst:
        shutil.copyfileobj(src, dst)


def extract_external(archive: Path, destination: Path, command: str) -> None:
    """Extract using 7z or unrar."""

    destination.mkdir(parents=True, exist_ok=True)

    if command == "7z":
        subprocess.check_call(["7z", "x", str(archive), f"-o{destination}", "-y"])
    elif command == "unrar":
        subprocess.check_call(["unrar", "x", "-o+", str(archive), str(destination)])
    else:
        raise ValueError(f"Unsupported external extractor: {command}")


def extract_archive(archive: Path, destination: Path, no_auto_install: bool) -> None:
    """Extract one archive based on extension."""

    name = archive.name.lower()
    destination.mkdir(parents=True, exist_ok=True)

    if name.endswith(".zip"):
        extract_zip(archive, destination)
    elif name.endswith((".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tbz2", ".tar.xz", ".txz")):
        extract_tar(archive, destination)
    elif name.endswith(".gz"):
        extract_single_compressed(archive, destination, gzip.open)
    elif name.endswith(".bz2"):
        extract_single_compressed(archive, destination, bz2.open)
    elif name.endswith(".xz"):
        extract_single_compressed(archive, destination, lzma.open)
    elif name.endswith(".7z"):
        ensure_command("7z", "p7zip-full", no_auto_install=no_auto_install)
        extract_external(archive, destination, "7z")
    elif name.endswith(".rar"):
        if shutil.which("unrar"):
            extract_external(archive, destination, "unrar")
        else:
            # 7z can extract many rar archives. If unrar is not there, try 7z as
            # the next best hammer.
            ensure_command("7z", "p7zip-full", no_auto_install=no_auto_install)
            extract_external(archive, destination, "7z")
    else:
        raise RuntimeError(f"Unsupported archive type: {archive}")


def collect_archives(path: Path, recursive: bool) -> tuple[list[Path], Path | None]:
    """Collect archives and return the scan root if path was a folder."""

    if path.is_file():
        return ([path] if archive_kind(path) else []), None

    iterator = path.rglob("*") if recursive else path.iterdir()
    archives = [candidate for candidate in iterator if candidate.is_file() and archive_kind(candidate)]
    return sorted(archives), path


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract archive files into clean folders.")
    parser.add_argument("path", type=Path, help="Archive file or folder containing archives.")
    parser.add_argument("-o", "--output", type=Path, help="Output root. Defaults beside each archive.")
    parser.add_argument("--recursive", action="store_true", help="Search folders recursively.")
    parser.add_argument("--delete-original", action="store_true", help="Delete each archive after successful extraction.")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be extracted without doing it.")
    parser.add_argument("--no-auto-install", action="store_true", help="Do not try to install missing external dependencies.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    target = args.path.resolve()

    if not target.exists():
        print(f"ERROR: Path does not exist: {target}", file=sys.stderr)
        return 1

    output_root = args.output.resolve() if args.output else None
    input_root = target if target.is_dir() else None
    archives, scan_root = collect_archives(target, recursive=args.recursive)

    if not archives:
        print("No supported archive files found.")
        return 0

    for archive in archives:
        destination = output_folder_for(archive, output_root, scan_root or input_root)
        verb = "WOULD EXTRACT" if args.dry_run else "EXTRACT"
        print(f"{verb}: {archive} -> {destination}")

        if args.dry_run:
            continue

        try:
            extract_archive(archive, destination, no_auto_install=args.no_auto_install)
            if args.delete_original:
                archive.unlink()
                print(f"DELETE ORIGINAL: {archive}")
        except Exception as exc:
            print(f"ERROR extracting {archive}: {exc}", file=sys.stderr)

    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
