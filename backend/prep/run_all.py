"""Run Scene Prep end to end: `make prep SCENE=<scene_id>`.

Order matters: everything grading needs comes first; segmentation (SAM 2 on
Baseten) is last and optional, because only the replay overlay uses it (I9).
A dead Baseten endpoint therefore never blocks a gradeable scene.

Each step skips itself when its artifact already exists, so a late failure
never re-runs an expensive earlier step (R4.2).
"""

from __future__ import annotations

import subprocess
import sys

import typer

from server.scene import scene_dir

# (module, artifact that means "already done" or None, required)
STEPS = [
    ("prep.trim", "trimmed.mp4", True),
    ("prep.keyframes", None, True),  # caches keypoints.json + key_moments.json itself
    ("prep.annotate_reference", None, True),  # caches in key_moments.json; never fails prep
    ("prep.isolate_client", "isolated.mp4", False),
    ("prep.build_pack", None, True),
]

app = typer.Typer(add_completion=False)


@app.command()
def main(scene: str = typer.Option(..., "--scene")) -> None:
    folder = scene_dir(scene)
    for module, artifact, required in STEPS:
        typer.secho(f"\n=== {module} ===", fg="cyan")
        if artifact and (folder / artifact).exists():
            typer.echo(f"skipped: {artifact} exists")
            continue
        result = subprocess.run([sys.executable, "-m", module, "--scene", scene])
        if result.returncode != 0:
            if required:
                raise typer.Exit(result.returncode)
            typer.secho(f"{module} failed -- optional, continuing without it", fg="yellow")
    typer.secho(f"\nScene pack ready: scenes/{scene}/pack.json", fg="green")


if __name__ == "__main__":
    app()
