#!/usr/bin/env python3
"""
video_audio_extract.py

Extract audio from video files using ffmpeg.

This is the "give me the WAV/FLAC/MP3 from this video folder" tool. It does not
try to be a DAW, it does not try to be clever, it just batch-rips audio tracks
with predictable filenames.

Dependency policy:
    - Requires the external ffmpeg command.
    - If ffmpeg is missing, the script tries to install it at runtime using
      apt-get on Ubuntu/Debian/Pop!_OS style systems.
    - Use --no-auto-install if you want it to fail instead.

Examples:
    python video_audio_extract.py ./clip.mov --format wav
    python video_audio_extract.py ./videos --recursive --format flac
    python video_audio_extract.py ./videos -o ./audio --format mp3 --bitrate 320k
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


VIDEO_EXTENSIONS = {
    ".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v", ".mpg", ".mpeg", ".wmv", ".flv",
}


def run_command(command: list[str]) -> bool:
    print("Dependency bootstrap:", " ".join(command))
    try:
        subprocess.check_call(command)
        return True
    except (OSError, subprocess.CalledProcessError):
        return False


def apt_install(package: str, no_auto_install: bool) -> bool:
    """Try to install an apt package for the current system."""

    if no_auto_install:
        return False
    if not shutil.which("apt-get"):
        return False
    if os.geteuid() == 0:
        return run_command(["apt-get", "update"]) and run_command(["apt-get", "install", "-y", package])
    if shutil.which("sudo"):
        return run_command(["sudo", "apt-get", "update"]) and run_command(["sudo", "apt-get", "install", "-y", package])
    return False


def ensure_ffmpeg(no_auto_install: bool) -> None:
    """Make sure ffmpeg is present before doing video work."""

    if shutil.which("ffmpeg"):
        return

    print("Missing dependency: ffmpeg")
    if apt_install("ffmpeg", no_auto_install=no_auto_install) and shutil.which("ffmpeg"):
        return

    raise SystemExit("ERROR: ffmpeg is missing. Install it manually with:\n  sudo apt install ffmpeg")


def collect_videos(path: Path, recursive: bool) -> tuple[list[Path], Path | None]:
    """Collect video files from a file or folder."""

    if path.is_file():
        return ([path] if path.suffix.lower() in VIDEO_EXTENSIONS else []), None

    iterator = path.rglob("*") if recursive else path.iterdir()
    videos = [candidate for candidate in iterator if candidate.is_file() and candidate.suffix.lower() in VIDEO_EXTENSIONS]
    return sorted(videos), path


def output_path_for(video: Path, output_root: Path | None, scan_root: Path | None, fmt: str) -> Path:
    """Compute output file path, preserving folder structure when output_root is used."""

    filename = video.with_suffix(f".{fmt}").name
    if output_root is None:
        return video.with_suffix(f".{fmt}")
    if scan_root is not None:
        try:
            relative_parent = video.parent.relative_to(scan_root)
            return output_root / relative_parent / filename
        except ValueError:
            pass
    return output_root / filename


def ffmpeg_args_for_format(fmt: str, bitrate: str) -> list[str]:
    """Return codec options for the chosen output format."""

    if fmt == "wav":
        return ["-acodec", "pcm_s16le"]
    if fmt == "flac":
        return ["-acodec", "flac"]
    if fmt == "mp3":
        return ["-codec:a", "libmp3lame", "-b:a", bitrate]
    if fmt == "aac":
        return ["-codec:a", "aac", "-b:a", bitrate]
    if fmt == "m4a":
        return ["-codec:a", "aac", "-b:a", bitrate]
    if fmt == "ogg":
        return ["-codec:a", "libvorbis", "-b:a", bitrate]
    raise ValueError(f"Unsupported format: {fmt}")


def extract_audio(video: Path, output: Path, fmt: str, bitrate: str, overwrite: bool) -> None:
    """Run ffmpeg for one video file."""

    output.parent.mkdir(parents=True, exist_ok=True)

    command = [
        "ffmpeg",
        "-y" if overwrite else "-n",
        "-i", str(video),
        "-vn",  # No video. We are ripping audio only, not transcoding the movie.
        *ffmpeg_args_for_format(fmt, bitrate),
        str(output),
    ]

    subprocess.check_call(command)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract audio from video files with ffmpeg.")
    parser.add_argument("path", type=Path, help="Video file or folder containing videos.")
    parser.add_argument("-o", "--output", type=Path, help="Output folder. Defaults beside each source video.")
    parser.add_argument("--recursive", action="store_true", help="Search input folder recursively.")
    parser.add_argument("--format", choices=["wav", "flac", "mp3", "aac", "m4a", "ogg"], default="wav", help="Output audio format.")
    parser.add_argument("--bitrate", default="320k", help="Bitrate for compressed formats like mp3/aac/ogg.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing output files.")
    parser.add_argument("--dry-run", action="store_true", help="Print planned ffmpeg work without extracting.")
    parser.add_argument("--no-auto-install", action="store_true", help="Do not try to install ffmpeg automatically.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    ensure_ffmpeg(no_auto_install=args.no_auto_install)

    target = args.path.resolve()
    if not target.exists():
        print(f"ERROR: Path does not exist: {target}", file=sys.stderr)
        return 1

    output_root = args.output.resolve() if args.output else None
    videos, scan_root = collect_videos(target, recursive=args.recursive)

    if not videos:
        print("No supported video files found.")
        return 0

    for video in videos:
        output = output_path_for(video, output_root, scan_root, args.format)
        verb = "WOULD EXTRACT" if args.dry_run else "EXTRACT"
        print(f"{verb}: {video} -> {output}")
        if args.dry_run:
            continue
        try:
            extract_audio(video, output, fmt=args.format, bitrate=args.bitrate, overwrite=args.overwrite)
        except subprocess.CalledProcessError as exc:
            print(f"ERROR ffmpeg failed for {video}: {exc}", file=sys.stderr)

    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
