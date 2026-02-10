#!/usr/bin/env python3
"""
x265_encode.py

Advanced H.265 / HEVC encoding wrapper for ffmpeg.

DEFAULTS (unchanged):
- CRF: 23
- Preset: medium
- Pixel format: yuv420p
- Container: mkv
- Encoder: software libx265

OPTIONAL FEATURES:
- MP4 output
- Subtitle handling (container-aware)
- 10-bit HEVC
- Hardware encoding (VAAPI / NVENC / AMF)
- Batch directory encoding
- Progress bar + ETA (ffprobe-based)
"""

import argparse
import subprocess
import sys
import re
from pathlib import Path
from typing import Optional


# -------------------------------------------------
# Progress parsing
# -------------------------------------------------

TIME_RE = re.compile(r"time=(\d+):(\d+):(\d+)\.(\d+)")


def parse_timecode(h: str, m: str, s: str) -> float:
    """Convert HH:MM:SS to seconds"""
    return int(h) * 3600 + int(m) * 60 + int(s)


def show_progress(stderr_line: str, total_duration: Optional[float]):
    """Render progress bar from ffmpeg stderr"""
    if total_duration is None:
        return

    match = TIME_RE.search(stderr_line)
    if not match:
        return

    elapsed = parse_timecode(*match.groups()[:3])
    pct = min((elapsed / total_duration) * 100, 100.0)

    bar_len = 40
    filled = int(bar_len * pct / 100)
    bar = "#" * filled + "." * (bar_len - filled)

    print(
        f"\r[ENCODE] [{bar}] {pct:5.1f}%",
        end="",
        flush=True,
    )


# -------------------------------------------------
# Duration probing
# -------------------------------------------------

def get_video_duration(input_path: Path) -> Optional[float]:
    """
    Use ffprobe to get total video duration in seconds.
    Returns None if duration cannot be determined.
    """
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(input_path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return float(result.stdout.strip())
    except Exception:
        return None


# -------------------------------------------------
# ffmpeg command builder
# -------------------------------------------------

def build_ffmpeg_command(
    input_path: Path,
    output_path: Path,
    crf: int,
    preset: str,
    container: str,
    audio_copy: bool,
    include_subs: bool,
    hevc10: bool,
    hw: Optional[str],
):
    cmd = ["ffmpeg", "-y", "-i", str(input_path)]

    # -----------------------------
    # Video encoder
    # -----------------------------
    if hw == "vaapi":
        cmd += [
            "-vaapi_device", "/dev/dri/renderD128",
            "-vf", "format=nv12,hwupload",
            "-c:v", "hevc_vaapi",
            "-qp", str(crf),
        ]
    elif hw == "nvenc":
        cmd += [
            "-c:v", "hevc_nvenc",
            "-preset", "p5",
            "-cq", str(crf),
        ]
    elif hw == "amf":
        cmd += [
            "-c:v", "hevc_amf",
            "-quality", "quality",
            "-qp_i", str(crf),
        ]
    else:
        cmd += [
            "-c:v", "libx265",
            "-preset", preset,
            "-crf", str(crf),
        ]

    # Pixel format
    cmd += ["-pix_fmt", "yuv420p10le" if hevc10 else "yuv420p"]

    # Streaming friendliness
    cmd += ["-movflags", "+faststart"]

    # -----------------------------
    # Streams
    # -----------------------------
    cmd += ["-map", "0:v:0", "-map", "0:a?"]

    # Audio
    if audio_copy:
        cmd += ["-c:a", "copy"]
    else:
        cmd += ["-c:a", "aac", "-b:a", "192k"]

    # Subtitles
    if include_subs:
        if container == "mp4":
            cmd += ["-map", "0:s?", "-c:s", "mov_text"]
        else:
            cmd += ["-map", "0:s?", "-c:s", "copy"]

    cmd.append(str(output_path))
    return cmd


# -------------------------------------------------
# Encode one file
# -------------------------------------------------

def encode_file(args, input_path: Path):
    output_path = (
        Path(args.output).with_suffix(f".{args.container}")
        if args.output
        else input_path.with_name(f"{input_path.stem}_x265.{args.container}")
    )

    total_duration = get_video_duration(input_path)

    if total_duration is None:
        print("[WARN] Could not determine duration, progress disabled")

    cmd = build_ffmpeg_command(
        input_path=input_path,
        output_path=output_path,
        crf=args.crf,
        preset=args.preset,
        container=args.container,
        audio_copy=args.audio_copy,
        include_subs=args.include_subs,
        hevc10=args.hevc10,
        hw=args.hw,
    )

    print("\n[INFO] ffmpeg command:")
    print(" ".join(cmd), "\n")

    if args.dry_run:
        return

    proc = subprocess.Popen(
        cmd,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    for line in proc.stderr:
        show_progress(line, total_duration)

    proc.wait()
    print(f"\n[INFO] Finished: {output_path}")


# -------------------------------------------------
# Main
# -------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Advanced x265 encoder")

    parser.add_argument("input", help="Input video file")
    parser.add_argument("--batch-dir", help="Encode all videos in directory")
    parser.add_argument("--container", choices=["mkv", "mp4"], default="mkv")
    parser.add_argument("-c", "--crf", type=int, default=23)
    parser.add_argument("-p", "--preset", default="medium")
    parser.add_argument("--audio-copy", action="store_true")
    parser.add_argument("--include-subs", action="store_true")
    parser.add_argument("--hevc10", action="store_true")
    parser.add_argument("--hw", choices=["vaapi", "nvenc", "amf"])
    parser.add_argument("--output")
    parser.add_argument("--dry-run", action="store_true")

    args = parser.parse_args()

    if args.batch_dir:
        for video in Path(args.batch_dir).iterdir():
            if video.suffix.lower() in {".mp4", ".mkv", ".mov", ".avi"}:
                encode_file(args, video)
    else:
        encode_file(args, Path(args.input))


if __name__ == "__main__":
    main()
