"""Step 1 -- trim the chosen continuous shot and normalise it.

    uv run python -m prep.trim --scene <scene_id>
"""

from __future__ import annotations

import typer

from server.config import get_settings
from server.media.ffmpeg import trim
from server.scene import load_config, scene_dir

app = typer.Typer(add_completion=False)


@app.command()
def main(scene: str = typer.Option(..., "--scene", help="scene_id under scenes/")) -> None:
    cfg = load_config(scene)
    src = get_settings().root / cfg.clip_file
    if not src.exists():
        raise typer.BadParameter(f"Clip not found: {src} (copy it into assets/private/)")
    dst = scene_dir(scene) / "trimmed.mp4"
    trim(src, dst, cfg.start, cfg.end)
    typer.echo(f"trimmed -> {dst}")


if __name__ == "__main__":
    app()
