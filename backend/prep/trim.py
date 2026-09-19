"""Step 1 -- trim the chosen continuous shot and normalise it.

    uv run python -m prep.trim --scene <scene_id>
"""

from __future__ import annotations

from pathlib import Path

import typer

from server.config import get_settings
from server.media.ffmpeg import trim
from server.scene import load_config, scene_dir

app = typer.Typer(add_completion=False)

VIDEO_SUFFIXES = {".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi"}


def resolve_clip(clip_file: str) -> Path:
    """The configured clip, or the ONE video beside where it should be.

    Clips arrive under whatever name the person copying them chose. Substituting
    is fine as long as it is loud; picking between several is not, so that fails
    with the candidates listed (R4.4, R4.5).
    """
    expected = get_settings().root / clip_file
    if expected.exists():
        return expected
    folder = expected.parent
    videos = sorted(p for p in folder.glob("*") if p.suffix.lower() in VIDEO_SUFFIXES) \
        if folder.is_dir() else []
    if len(videos) == 1:
        typer.secho(
            f"!! {expected.name} not found -- using {videos[0].name}, the only video in {folder}",
            fg="yellow", bold=True,
        )
        return videos[0]
    found = ", ".join(p.name for p in videos) or "no video files"
    raise typer.BadParameter(
        f"Clip not found: {expected}\n   In {folder}: {found}\n"
        "   Copy the clip there, or point clip_file in scene.yaml at it."
    )


@app.command()
def main(scene: str = typer.Option(..., "--scene", help="scene_id under scenes/")) -> None:
    cfg = load_config(scene)
    src = resolve_clip(cfg.clip_file)
    dst = scene_dir(scene) / "trimmed.mp4"
    trim(src, dst, cfg.start, cfg.end)
    typer.echo(f"trimmed -> {dst}")


if __name__ == "__main__":
    app()
