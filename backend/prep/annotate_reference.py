"""Step 3 -- write the reference sheet with OMNI (ONE call per scene, cached).

Sends the trimmed clip WITH its audio once and asks, for each key moment: the
face, the body and the voice. The live round never hears the character (the
side-by-side carries the player's microphone only), so this prose is the voice
judge's only picture of the target delivery -- and it is what lets every judge
quote specifics.

Cached in key_moments.json: re-running skips the call unless --force (R4.10).
A failed call writes nothing and exits cleanly; the sheet costs flavour, not a
round (R4.9).

    uv run python -m prep.annotate_reference --scene <scene_id>
"""

from __future__ import annotations

import json
import re

import typer

from server.compare import omni
from server.scene import KeyMoment, load_config, scene_dir

app = typer.Typer(add_completion=False)

PROMPT = """\
This clip shows {character_name} in "{movie_title}". Focus only on {character_name}'s
own face, body and vocal sounds; ignore anyone else on the soundtrack.

For each timestamp below, describe what {character_name} is doing at that moment:
{moments}

For each one give:
- face: the expression and its intensity
- body: posture, head position, hands
- voice: how it sounds -- pace, pitch, volume, breath, emotion

Never quote, transcribe or repeat any words that are spoken: describe HOW things
are said, never WHAT is said. Keep each field under 20 words.
Respond with JSON only:
{{"moments": [{{"t": 1.5, "face": "...", "body": "...", "voice": "..."}}]}}
"""


def _parse(text: str) -> list[dict]:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("no JSON object in OMNI reply")
    return json.loads(match.group(0))["moments"]


def _t(note: dict) -> float:
    """The note's timestamp. Models write "3.27", 3.27 or "3.27s" interchangeably."""
    match = re.search(r"-?\d+(?:\.\d+)?", str(note.get("t", "")))
    return float(match.group(0)) if match else -99.0


def merge(moments: list[KeyMoment], notes: list[dict]) -> list[KeyMoment]:
    """Attach each note to the key moment it describes (nearest, within a second)."""
    for m in moments:
        near = min(notes, key=lambda n: abs(_t(n) - m.t), default=None)
        if near is None or abs(_t(near) - m.t) > 1.0:
            continue
        m.face, m.body, m.voice = (
            omni._unquote(str(near.get(k, ""))) for k in ("face", "body", "voice")
        )
    return moments


@app.command()
def main(
    scene: str = typer.Option(..., "--scene"),
    force: bool = typer.Option(False, "--force", help="Call OMNI again even if cached"),
) -> None:
    cfg = load_config(scene)
    folder = scene_dir(scene)
    km_path = folder / "key_moments.json"
    if not km_path.exists():
        raise typer.BadParameter(f"Run `prep.keyframes --scene {scene}` first")
    moments = [KeyMoment(**m) for m in json.loads(km_path.read_text(encoding="utf-8"))]
    if any(m.face or m.body or m.voice for m in moments) and not force:
        typer.echo("reference sheet: cached")
        return

    prompt = PROMPT.format(
        character_name=cfg.character_name,
        movie_title=cfg.movie_title,
        moments="\n".join(f"- {m.t:.2f}s ({m.label})" for m in moments),
    )
    try:
        notes = _parse(omni.ask(folder / "trimmed.mp4", prompt))
    except Exception as exc:  # noqa: BLE001 - the sheet is flavour; prep carries on
        typer.secho(f"!! reference sheet skipped, OMNI failed: {exc}", fg="yellow")
        return

    moments = merge(moments, notes)
    if not any(m.face or m.body or m.voice for m in moments):
        typer.secho("!! OMNI replied but no note matched a key moment; sheet left empty",
                    fg="yellow")
        return
    km_path.write_text(json.dumps([m.model_dump() for m in moments], indent=2), encoding="utf-8")
    for m in moments:
        typer.echo(f"  {m.t:5.2f}s face: {m.face}\n         voice: {m.voice}")
    typer.echo(f"reference sheet -> {km_path}")


if __name__ == "__main__":
    app()
