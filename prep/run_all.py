"""Run all five Scene Prep steps end to end: `make prep SCENE=<scene_id>`."""

from __future__ import annotations

import subprocess
import sys

import typer

STEPS = ["prep.trim", "prep.isolate_client", "prep.keyframes",
         "prep.annotate_reference", "prep.build_pack"]

app = typer.Typer(add_completion=False)


@app.command()
def main(scene: str = typer.Option(..., "--scene")) -> None:
    for module in STEPS:
        typer.secho(f"\n=== {module} ===", fg="cyan")
        result = subprocess.run([sys.executable, "-m", module, "--scene", scene])
        if result.returncode != 0:
            raise typer.Exit(result.returncode)
    typer.secho(f"\nScene pack ready: scenes/{scene}/pack.json", fg="green")


if __name__ == "__main__":
    app()
