"""ffmpeg helpers: trim, side-by-side, downscale, audio extraction.

The side-by-side build is the key trick: OMNI takes text plus ONE video per
request, so the character (left) and the player (right) are merged into a single
frame-synced video carrying the player's microphone audio.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from server.config import get_settings


def run(args: list[str]) -> None:
    settings = get_settings()
    subprocess.run([settings.ffmpeg_bin, "-y", "-loglevel", "error", *args], check=True)


def trim(src: Path, dst: Path, start: str, end: str, height: int = 720, fps: int = 24) -> Path:
    """Cut the chosen continuous shot and normalise resolution / frame rate."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    run([
        "-ss", start, "-to", end, "-i", str(src),
        "-vf", f"scale=-2:{height},fps={fps}",
        "-c:v", "libx264", "-preset", "veryfast", "-c:a", "aac",
        str(dst),
    ])
    return dst


def side_by_side(left: Path, right: Path, dst: Path, height: int = 480) -> Path:
    """Character left, player right, frame-synced, with the PLAYER's audio only."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    run([
        "-i", str(left), "-i", str(right),
        "-filter_complex",
        f"[0:v]scale=-2:{height}[l];[1:v]scale=-2:{height}[r];[l][r]hstack=inputs=2[v]",
        "-map", "[v]", "-map", "1:a?",
        "-c:v", "libx264", "-preset", "veryfast", "-c:a", "aac", "-shortest",
        str(dst),
    ])
    return dst


def extract_audio(src: Path, dst: Path) -> Path:
    dst.parent.mkdir(parents=True, exist_ok=True)
    run(["-i", str(src), "-vn", "-ac", "1", "-ar", "16000", str(dst)])
    return dst


def duration_s(src: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(src)],
        check=True, capture_output=True, text=True,
    )
    return float(out.stdout.strip())
