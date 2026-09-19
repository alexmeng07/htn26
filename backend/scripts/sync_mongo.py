"""Push locally mirrored rounds and scene packs to MongoDB Atlas.

Run from the repository root after connectivity returns:

    uv run --directory backend python -m scripts.sync_mongo

Writes are idempotent because rounds and packs are upserted by stable IDs.
"""

from __future__ import annotations

import typer

from server.config import get_settings
from server.scene import ScenePack
from server.schemas import RoundResult
from server.store import db

app = typer.Typer(add_completion=False)


@app.command()
def main() -> None:
    settings = get_settings()
    status = db.mongo_status(force_probe=True)
    if not status["configured"]:
        raise typer.BadParameter("MONGODB_URI is not set")
    if not status["reachable"]:
        typer.echo("MongoDB is unreachable; local data was not changed.", err=True)
        raise typer.Exit(1)

    rounds = sorted((settings.data_path / "rounds").glob("*.json"))
    confirmed_rounds = 0
    for path in rounds:
        result = RoundResult.model_validate_json(path.read_text(encoding="utf-8"))
        if not db.save_result(result):
            typer.echo(f"MongoDB write failed for round {result.round_id}.", err=True)
            raise typer.Exit(1)
        confirmed_rounds += 1
    typer.echo(f"rounds: {confirmed_rounds} upserted")

    packs = sorted(settings.scenes_path.glob("*/pack.json"))
    confirmed_packs = 0
    for path in packs:
        pack = ScenePack.model_validate_json(path.read_text(encoding="utf-8"))
        if not db.save_pack(pack.model_dump(mode="json")):
            typer.echo(f"MongoDB write failed for scene {pack.scene_id}.", err=True)
            raise typer.Exit(1)
        confirmed_packs += 1
    typer.echo(f"scene packs: {confirmed_packs} upserted")
    typer.echo(f"merged leaderboard preview entries: {len(db.top(limit=5))}")


if __name__ == "__main__":
    app()
