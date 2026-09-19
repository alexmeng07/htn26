"""Step 4 -- combine config + prep outputs + reference sheet into the scene pack.

Writes scenes/<scene_id>/pack.json and mirrors it to MongoDB. MongoDB being
unreachable is a warning, not a failure: pack.json is what the game reads
(R4.12). Nothing scored depends on segmentation, so a pack without an isolated
video is still a complete, gradeable pack (I9).

Also DESIGNS the replay's dub voice from the pack's `dub_voice_style` text --
never cloned from the actor or anyone -- once, keeping the ID across re-runs.

    uv run python -m prep.build_pack --scene <scene_id>
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import typer

from server.config import get_settings
from server.scene import KeyMoment, ScenePack, load_config, load_pack, save_pack, scene_dir
from server.store import db
from server.voice import speech

app = typer.Typer(add_completion=False)


def _design_dub_voice(style: str) -> str:
    """A designed voice for the replay, or "" (the replay keeps the player's own voice)."""
    if not style or not get_settings().elevenlabs_api_key or get_settings().force_fallback:
        return ""
    try:
        voice_id = speech.design_dub_voice(style)
        typer.echo(f"  dub voice designed from '{style}': {voice_id}")
        return voice_id
    except Exception as exc:  # noqa: BLE001 - the dub is a P2 extra; the pack still builds
        typer.secho(f"  !! dub voice design failed, replay keeps the player's voice: {exc}",
                    fg="yellow")
        return ""


@app.command()
def main(scene: str = typer.Option(..., "--scene")) -> None:
    folder = scene_dir(scene)
    if not (folder / "keypoints.json").exists():
        raise typer.BadParameter(f"Run `prep.keyframes --scene {scene}` first")

    # Start from the raw config so a stale pack.json never carries old fields over,
    # then let load_pack's auto-detection fill in whatever media prep produced.
    # The one thing worth keeping is a dub voice already designed (and paid for).
    old = folder / "pack.json"
    dub_voice_id = ""
    if old.exists():
        dub_voice_id = ScenePack.model_validate_json(old.read_text(encoding="utf-8")).dub_voice_id
    old.unlink(missing_ok=True)
    detected = load_pack(scene)
    km_path = folder / "key_moments.json"
    moments = [KeyMoment(**m) for m in json.loads(km_path.read_text(encoding="utf-8"))] \
        if km_path.exists() else []

    pack = ScenePack(**{
        **load_config(scene).model_dump(),
        **detected.model_dump(
            include={"isolated_video", "cue_audio", "masks_dir", "overlay", "duration_s"}
        ),
        "key_moments": moments,
        "dub_voice_id": dub_voice_id or _design_dub_voice(load_config(scene).dub_voice_style),
        "prepared_at": datetime.now(UTC).isoformat(timespec="seconds"),
    })
    path = save_pack(pack)
    typer.echo(f"pack -> {path}  ({len(moments)} key moments, {pack.duration_s:.1f}s)")
    if not pack.isolated_video:
        typer.echo("  no isolated video: the replay uses the plain clip (grading is unaffected)")
    if db.save_pack(pack.model_dump(mode="json")):
        typer.echo("  mirrored to MongoDB")
    else:
        typer.secho("  !! MongoDB unreachable -- pack.json written locally only", fg="yellow")


if __name__ == "__main__":
    app()
