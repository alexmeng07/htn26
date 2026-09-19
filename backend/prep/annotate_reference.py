"""Step 4 -- write the reference sheet with OMNI (runs ONCE per scene, cached).

Sends the isolated clip WITH its audio to OMNI once and asks, for each key
moment: the face (expression + intensity), the body (posture, head, hands) and
the voice (laugh, sob, breath, silence).

Tell OMNI the character's name and to focus on THAT character's own vocal
sounds, ignoring other voices in the soundtrack.

Caching this is also the Huawei "caching" bonus -- it barely touches the credit
budget.

    uv run python -m prep.annotate_reference --scene <scene_id>
"""

from __future__ import annotations

import typer

app = typer.Typer(add_completion=False)


@app.command()
def main(scene: str = typer.Option(..., "--scene")) -> None:
    """Lane A/C: one OMNI call -> fill KeyMoment.face/body/voice for every moment."""
    raise NotImplementedError("Lane A: OMNI reference sheet not implemented yet")


if __name__ == "__main__":
    app()
