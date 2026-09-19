"""Step 5 -- combine config + prep outputs + reference sheet into the scene pack.

Writes scenes/<scene_id>/pack.json and mirrors it to MongoDB. Also designs the
dub voice from the scene pack's `dub_voice_style` description and stores its
voice ID in the pack (never in .env, and never cloned from a real person).

    uv run python -m prep.build_pack --scene <scene_id>
"""

from __future__ import annotations

import typer

app = typer.Typer(add_completion=False)


@app.command()
def main(scene: str = typer.Option(..., "--scene")) -> None:
    """Lane A: assemble ScenePack, save_pack(), upsert to MongoDB."""
    raise NotImplementedError("Lane A: pack builder not implemented yet")


if __name__ == "__main__":
    app()
