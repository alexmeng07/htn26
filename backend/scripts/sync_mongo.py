"""Push everything saved locally while MongoDB was unreachable up to Atlas.

Rounds and scene packs are always written to local JSON first, so nothing is
lost during an outage -- but the leaderboard reads Atlas once it is back, so
run this after connectivity returns. Idempotent: every write is an upsert.

    uv run python -m scripts.sync_mongo
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
    client = db.client()
    if client is None:
        raise typer.BadParameter("MONGODB_URI is not set")
    client.admin.command("ping")  # fail loudly here rather than per document

    rounds = sorted((settings.data_path / "rounds").glob("*.json"))
    for path in rounds:
        db.save_result(RoundResult.model_validate_json(path.read_text(encoding="utf-8")))
    typer.echo(f"rounds: {len(rounds)} upserted")

    packs = sorted(settings.scenes_path.glob("*/pack.json"))
    for path in packs:
        pack = ScenePack.model_validate_json(path.read_text(encoding="utf-8"))
        if not db.save_pack(pack.model_dump(mode="json")):
            raise typer.Exit(1)
    typer.echo(f"scene packs: {len(packs)} upserted")
    typer.echo(f"leaderboard now: {[(e.nickname, e.combined) for e in db.top(limit=5)]}")


if __name__ == "__main__":
    app()
