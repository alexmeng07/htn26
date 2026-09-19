"""ffmpeg helpers: trim, side-by-side, downscale, audio extraction.

The side-by-side build is the key trick: OMNI takes text plus ONE video per
request, so the character (left) and the player (right) are merged into a single
frame-synced video carrying the player's microphone audio.
"""

from __future__ import annotations

import re
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


def side_by_side(
    left: Path, right: Path, dst: Path, height: int = 360, fps: int = 10
) -> Path:
    """Character left, player right, frame-synced, with the PLAYER's audio only.

    Sized for OMNI, not for people: 360p at 10 fps is a third of the bytes of
    480p/24 and measured ~35% faster (7.1s vs 10.8s) with the same voice score.
    The watchable replay is the composite in media/composite.py.
    """
    dst.parent.mkdir(parents=True, exist_ok=True)
    run([
        "-i", str(left), "-i", str(right),
        "-filter_complex",
        f"[0:v]scale=-2:{height},fps={fps}[l];[1:v]scale=-2:{height},fps={fps}[r];"
        "[l][r]hstack=inputs=2[v]",
        "-map", "[v]", "-map", "1:a?",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "28", "-c:a", "aac", "-b:a", "64k",
        "-shortest",
        str(dst),
    ])
    return dst


def extract_audio(src: Path, dst: Path) -> Path:
    dst.parent.mkdir(parents=True, exist_ok=True)
    run(["-i", str(src), "-vn", "-ac", "1", "-ar", "16000", str(dst)])
    return dst


def video_size(src: Path) -> tuple[int, int]:
    """(width, height) in pixels. Used to validate prompts against the clip."""
    out = subprocess.run(
        [get_settings().ffprobe_bin, "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "csv=p=0:s=x", str(src)],
        check=True, capture_output=True, text=True,
    )
    width, height = out.stdout.strip().split("x")
    return int(width), int(height)


def duration_s(src: Path) -> float:
    out = subprocess.run(
        [get_settings().ffprobe_bin, "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(src)],
        check=True, capture_output=True, text=True,
    )
    return float(out.stdout.strip())


def mean_volume_db(src: Path) -> float | None:
    """Mean loudness of the audio track in dBFS, or None if there is no audio.

    Silence is measured here, not asked of OMNI: given a silent video the model
    will happily describe speech that was never there.
    """
    out = subprocess.run(
        [get_settings().ffmpeg_bin, "-hide_banner", "-nostats", "-i", str(src),
         "-map", "0:a:0?", "-af", "volumedetect", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    match = re.search(r"mean_volume:\s*(-?[\d.]+|-inf) dB", out.stderr)
    if not match:
        return None
    return float("-inf") if match.group(1) == "-inf" else float(match.group(1))


def audio_levels(src: Path, hop_s: float = 0.05, rate: int = 16000) -> list[float]:
    """Loudness envelope: one dBFS value per `hop_s` of audio. Empty if no audio.

    Feeds the local voice estimate (server/grading/voice.py) when the
    multimodal model is unavailable.
    """
    import numpy as np

    out = subprocess.run(
        [get_settings().ffmpeg_bin, "-loglevel", "error", "-i", str(src), "-map", "0:a:0?",
         "-ac", "1", "-ar", str(rate), "-f", "s16le", "-"],
        capture_output=True,
    )
    samples = np.frombuffer(out.stdout, dtype=np.int16).astype(np.float64) / 32768.0
    hop = int(rate * hop_s)
    frames = len(samples) // hop
    if not frames:
        return []
    rms = np.sqrt(np.mean(samples[: frames * hop].reshape(frames, hop) ** 2, axis=1))
    return [float(v) for v in np.round(20 * np.log10(np.maximum(rms, 1e-6)), 2)]


def replace_audio(video: Path, audio: Path, dst: Path) -> Path:
    """Keep the video stream, swap in a new soundtrack (the dub)."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    run([
        "-i", str(video), "-i", str(audio),
        "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-shortest",
        str(dst),
    ])
    return dst
