"""Draw placeholder judge sprites until the real art lands.

Writes the four-state contract from assets/judges/README.md -- idle, talking,
yes, no; transparent PNG; one 512x512 canvas -- for every judge folder that has
a judge.json. Existing PNGs are left alone unless --force, so dropping real art
in over these needs no code change (R12.4).

    uv run python -m scripts.make_placeholder_sprites
"""

from __future__ import annotations

import json
from pathlib import Path

import typer
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
JUDGES_DIR = ROOT / "assets" / "judges"
SIZE = 512
SS = 2  # supersample, then downscale: cheap anti-aliasing

# One look per judge id. Anything unknown gets the first palette.
LOOKS = {
    "face": {"skin": (236, 196, 170), "coat": (106, 76, 147), "hair": (70, 60, 70),
             "prop": "glasses"},
    "body": {"skin": (201, 150, 110), "coat": (232, 118, 44), "hair": (40, 30, 25),
             "prop": "headband"},
    "voice": {"skin": (240, 205, 180), "coat": (32, 140, 140), "hair": (150, 60, 90),
              "prop": "tiara"},
}
YES, NO = (60, 190, 110), (220, 60, 60)
INK = (30, 24, 30)

STATES = ("idle", "talking", "yes", "no")


def _s(*v: float) -> list[float]:
    return [x * SS for x in v]


def draw(look: dict, state: str) -> Image.Image:
    img = Image.new("RGBA", (SIZE * SS, SIZE * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    skin, coat, hair = look["skin"], look["coat"], look["hair"]

    # Shoulders and neck.
    d.rounded_rectangle(_s(96, 360, 416, 560), radius=120 * SS, fill=coat)
    d.rectangle(_s(226, 300, 286, 380), fill=skin)
    # Head, hair.
    d.ellipse(_s(146, 96, 366, 336), fill=skin)
    d.chord(_s(140, 80, 372, 250), 180, 360, fill=hair)

    # Eyes and brows: brows drop for NO, lift for YES.
    brow = {"yes": 8, "no": -8}.get(state, 0)
    for cx in (216, 296):
        d.ellipse(_s(cx - 12, 196, cx + 12, 222), fill=INK)
        tilt = brow if cx == 216 else -brow
        d.line(_s(cx - 22, 182 + tilt, cx + 22, 182 - tilt), fill=INK, width=7 * SS)

    # Mouth carries the state.
    if state == "talking":
        d.ellipse(_s(228, 262, 284, 306), fill=(120, 30, 40))
    elif state == "yes":
        d.arc(_s(206, 236, 306, 300), 20, 160, fill=INK, width=8 * SS)
    elif state == "no":
        d.arc(_s(214, 272, 298, 322), 200, 340, fill=INK, width=8 * SS)
    else:
        d.line(_s(230, 282, 282, 282), fill=INK, width=7 * SS)

    # A prop so the three read as three people at a glance.
    prop = look["prop"]
    if prop == "glasses":
        for cx in (216, 296):
            d.ellipse(_s(cx - 28, 184, cx + 28, 234), outline=INK, width=6 * SS)
        d.line(_s(244, 208, 268, 208), fill=INK, width=6 * SS)
    elif prop == "headband":
        d.rectangle(_s(146, 140, 366, 166), fill=(230, 40, 60))
    elif prop == "tiara":
        d.polygon(_s(196, 118, 216, 70, 236, 110, 256, 56, 276, 110, 296, 70, 316, 118),
                  fill=(240, 200, 60))

    # Verdict badge.
    if state in ("yes", "no"):
        colour = YES if state == "yes" else NO
        d.ellipse(_s(372, 36, 492, 156), fill=colour)
        if state == "yes":
            d.line(_s(398, 98, 424, 124, 468, 70), fill="white", width=14 * SS, joint="curve")
        else:
            d.line(_s(404, 68, 460, 124), fill="white", width=14 * SS)
            d.line(_s(460, 68, 404, 124), fill="white", width=14 * SS)

    return img.resize((SIZE, SIZE), Image.LANCZOS)


app = typer.Typer(add_completion=False)


@app.command()
def main(force: bool = typer.Option(False, "--force", help="Overwrite existing PNGs")) -> None:
    for folder in sorted(p for p in JUDGES_DIR.iterdir() if (p / "judge.json").exists()):
        judge_id = json.loads((folder / "judge.json").read_text(encoding="utf-8"))["judge_id"]
        look = LOOKS.get(judge_id, next(iter(LOOKS.values())))
        for state in STATES:
            dst = folder / f"{state}.png"
            if dst.exists() and not force:
                typer.echo(f"{dst.relative_to(ROOT)}: exists, kept")
                continue
            draw(look, state).save(dst)
            typer.echo(f"{dst.relative_to(ROOT)}: placeholder written")


if __name__ == "__main__":
    app()
