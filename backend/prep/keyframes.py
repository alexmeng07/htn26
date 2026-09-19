"""Step 3 -- pick 6-10 key moments where expression or posture clearly changes.

Simplest reliable approach: sample a frame every few seconds, then let OMNI (or
a human) confirm which are meaningful. Store each moment's timestamp.

    uv run python -m prep.keyframes --scene <scene_id>
"""

from __future__ import annotations

import typer

app = typer.Typer(add_completion=False)


@app.command()
def main(
    scene: str = typer.Option(..., "--scene"),
    count: int = typer.Option(8, "--count", min=6, max=10),
) -> None:
    """Lane A: sample frames from isolated.mp4, keep the `count` most distinct."""
    raise NotImplementedError("Lane A: keyframe picker not implemented yet")


if __name__ == "__main__":
    app()
