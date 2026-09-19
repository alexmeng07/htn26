"""Step 2 -- isolate the target character with SAM 2 on Baseten.

A human marks the target character in the FIRST frame (a box or a click);
SAM 2 follows them through the whole clip. Frames where it finds nothing are
cutaways: they're skipped when scoring, and the UI shows "(hold your reaction)".

    uv run python -m prep.isolate_client --scene <scene_id> --pick
    uv run python -m prep.isolate_client --scene <scene_id>

Escape hatch: if the Baseten deployment stalls, point --endpoint at the same
Truss running anywhere else (Colab, a teammate's box) so the demo isn't blocked.
Keep pushing the Baseten version for the prize.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

import httpx
import typer

from server.config import get_settings
from server.media.ffmpeg import run as ffmpeg_run
from server.scene import load_config, scene_dir

app = typer.Typer(add_completion=False)

# A 20-40s clip propagates in ~1-3 min. Baseten's sync ceiling is 20 min, so
# this stays an ordinary request/response call -- no async or webhooks.
TIMEOUT_S = 1200.0


def first_frame(trimmed: Path, dst: Path) -> Path:
    """Write frame 0 so a human can read the character's coordinates off it."""
    ffmpeg_run(["-i", str(trimmed), "-vframes", "1", str(dst)])
    return dst


@app.command()
def main(
    scene: str = typer.Option(..., "--scene"),
    pick: bool = typer.Option(False, "--pick", help="Export frame 1 to mark the character on"),
    endpoint: str = typer.Option("", "--endpoint", help="Override SAM2_ENDPOINT_URL"),
    background: str = typer.Option("dark", "--background", help="dark | blur"),
) -> None:
    settings = get_settings()
    cfg = load_config(scene)
    folder = scene_dir(scene)
    trimmed = folder / "trimmed.mp4"
    if not trimmed.exists():
        raise typer.BadParameter(f"Run `prep.trim --scene {scene}` first ({trimmed} missing)")

    if pick:
        frame = first_frame(trimmed, folder / "first_frame.png")
        typer.echo(
            f"Wrote {frame}\n"
            "Open it, read the target character's bounding box in pixels, and put it in\n"
            f"  scenes/{scene}/scene.yaml  ->  character_select.box: [x1, y1, x2, y2]"
        )
        raise typer.Exit()

    select = cfg.character_select
    if not select.box and not select.point:
        raise typer.BadParameter(
            f"scenes/{scene}/scene.yaml has no character_select. Run with --pick first."
        )

    url = endpoint or settings.sam2_endpoint_url
    if not url:
        raise typer.BadParameter("SAM2_ENDPOINT_URL is not set (or pass --endpoint)")
    if not settings.baseten_api_key and "baseten.co" in url:
        raise typer.BadParameter("BASETEN_API_KEY is not set")

    payload: dict = {
        "video_b64": base64.b64encode(trimmed.read_bytes()).decode(),
        "background": background,
        "mask_format": "rle",
    }
    payload["box" if select.box else "point"] = select.box or select.point

    size_mb = len(payload["video_b64"]) / 1_000_000
    if size_mb > 95:
        raise typer.BadParameter(
            f"Clip is {size_mb:.0f}MB base64; Baseten caps a request body at 100MB. "
            "Re-trim shorter or at a lower resolution."
        )
    typer.echo(f"Uploading {size_mb:.1f}MB to SAM 2 (up to {TIMEOUT_S / 60:.0f} min)...")

    response = httpx.post(
        url,
        headers={"Authorization": f"Bearer {settings.baseten_api_key}"},
        json=payload,
        timeout=TIMEOUT_S,
    )
    response.raise_for_status()
    result = response.json()

    isolated = folder / "isolated.mp4"
    isolated.write_bytes(base64.b64decode(result["isolated_b64"]))

    masks_dir = folder / "masks"
    masks_dir.mkdir(exist_ok=True)
    (masks_dir / "masks.json").write_text(
        json.dumps(
            {
                "format": result.get("mask_format", "rle"),
                "fps": result["fps"],
                "size": result["size"],
                "visible": result["visible"],
                "masks": result["masks"],
            }
        ),
        encoding="utf-8",
    )

    visible = result["visible"]
    cutaways = len(visible) - sum(visible)
    typer.secho(f"isolated -> {isolated}", fg="green")
    typer.echo(
        f"{result['frame_count']} frames at {result['fps']:.1f}fps, "
        f"{cutaways} cutaway frame(s) the scorer will skip"
    )


if __name__ == "__main__":
    app()
