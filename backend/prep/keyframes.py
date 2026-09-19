"""Step 2 -- reference keypoints, then the key moments picked from them.

Runs the same MediaPipe models the browser runs on the player, over the trimmed
clip (cropped to the character_select box so the landmarkers stay on the right
person). Key moments are the biggest swings in posture and expression.

Artifacts, each cached (re-running skips whichever exists unless --force, R4.2):
  keypoints.json    the grading timeline, normalised to the character crop
  overlay.json      the same frames as full-frame points, for drawing the
                    character's skeleton during the take (never scored)
  key_moments.json  the picked moments

    uv run python -m prep.keyframes --scene <scene_id>
"""

from __future__ import annotations

import json

import typer

from server.grading import moments
from server.media.keypoints import extract_with_overlay
from server.scene import KeyMoment, load_config, scene_dir
from server.schemas import KeypointTimeline

app = typer.Typer(add_completion=False)

# Reference sampling rate. The browser samples the player at about the same.
REFERENCE_FPS = 15.0


@app.command()
def main(
    scene: str = typer.Option(..., "--scene"),
    count: int = typer.Option(8, "--count", min=6, max=10),
    force: bool = typer.Option(False, "--force", help="Re-extract and re-pick"),
) -> None:
    cfg = load_config(scene)
    folder = scene_dir(scene)
    trimmed = folder / "trimmed.mp4"
    if not trimmed.exists():
        raise typer.BadParameter(f"Run `prep.trim --scene {scene}` first ({trimmed} missing)")

    kp_path, ov_path = folder / "keypoints.json", folder / "overlay.json"
    if kp_path.exists() and ov_path.exists() and not force:
        timeline = KeypointTimeline.model_validate_json(kp_path.read_text(encoding="utf-8"))
        typer.echo(f"keypoints: cached ({len(timeline.samples)} samples)")
    else:
        timeline, overlay = extract_with_overlay(
            trimmed, fps=REFERENCE_FPS, crop=cfg.character_select.box
        )
        kp_path.write_text(timeline.model_dump_json(), encoding="utf-8")
        ov_path.write_text(json.dumps(overlay, separators=(",", ":")), encoding="utf-8")
        typer.echo(f"keypoints -> {kp_path}")
        typer.echo(f"overlay   -> {ov_path}")

    seen = sum(1 for s in timeline.samples if s.pose or s.face)
    typer.echo(f"  character detected in {seen}/{len(timeline.samples)} frames")
    if not seen:
        raise typer.BadParameter(
            "No person detected anywhere in the clip -- check character_select.box"
        )

    km_path = folder / "key_moments.json"
    if km_path.exists() and not force:
        typer.echo("key moments: cached")
        return
    picked = moments.select(timeline, count)
    if len(picked) < moments.MIN_MOMENTS:
        typer.secho(
            f"!! only {len(picked)} distinct moments fit in this clip (wanted {count})",
            fg="yellow",
        )
    km = [KeyMoment(t=t, label=label).model_dump() for t, label in picked]
    km_path.write_text(json.dumps(km, indent=2), encoding="utf-8")
    for m in km:
        typer.echo(f"  {m['t']:5.2f}s  {m['label']}")
    typer.echo(f"key moments -> {km_path}")


if __name__ == "__main__":
    app()
