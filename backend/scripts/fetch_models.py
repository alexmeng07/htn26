"""Download the keypoint models LARPsim grades with.

Two consumers, one set of files:
  * prep and the server fallback path load them through MediaPipe's Python API
  * the browser loads the SAME files over /assets during a take

Serving them from our own origin (rather than a CDN) is what lets grading work
with the Wi-Fi off, which invariant I6 requires.

Versions are pinned. `latest` is only used if a pinned path 404s, and the script
says loudly when that happens, because a silent model swap would quietly break
the Python/browser parity that comparison depends on (requirement R6.4).

    uv run python -m scripts.fetch_models
    uv run python -m scripts.fetch_models --force
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import httpx
import typer

# Repo root: assets/ is shared with the frontend and lives above backend/.
ROOT = Path(__file__).resolve().parents[2]
MODELS_DIR = ROOT / "assets" / "models"

BASE = "https://storage.googleapis.com/mediapipe-models"

# (filename, model path, pinned version)
MODELS = [
    ("pose_landmarker_full.task", "pose_landmarker/pose_landmarker_full/float16", "1"),
    ("face_landmarker.task", "face_landmarker/face_landmarker/float16", "1"),
]

app = typer.Typer(add_completion=False)


def _url(model_path: str, version: str, filename: str) -> str:
    return f"{BASE}/{model_path}/{version}/{filename}"


def _download(url: str, dst: Path) -> int:
    with httpx.stream("GET", url, follow_redirects=True, timeout=120.0) as response:
        response.raise_for_status()
        dst.parent.mkdir(parents=True, exist_ok=True)
        written = 0
        with dst.open("wb") as handle:
            for chunk in response.iter_bytes(chunk_size=65536):
                handle.write(chunk)
                written += len(chunk)
    return written


@app.command()
def main(force: bool = typer.Option(False, "--force", help="Re-download even if present")) -> None:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    for filename, model_path, version in MODELS:
        dst = MODELS_DIR / filename

        if dst.exists() and not force:
            typer.echo(f"{filename}: already present ({dst.stat().st_size / 1e6:.1f} MB)")
            continue

        pinned = _url(model_path, version, filename)
        try:
            size = _download(pinned, dst)
            used = f"pinned v{version}"
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 404:
                raise
            typer.secho(
                f"{filename}: pinned v{version} returned 404, falling back to `latest`. "
                "Re-pin this version -- an unpinned model can silently break "
                "Python/browser parity.",
                fg="yellow",
            )
            size = _download(_url(model_path, "latest", filename), dst)
            used = "latest (UNPINNED)"

        digest = hashlib.sha256(dst.read_bytes()).hexdigest()[:16]
        typer.secho(
            f"{filename}: {size / 1e6:.1f} MB from {used}, sha256:{digest}",
            fg="green",
        )

    typer.echo(f"\nModels in {MODELS_DIR}")


if __name__ == "__main__":
    app()
