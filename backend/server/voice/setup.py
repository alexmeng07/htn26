"""One-time ElevenLabs setup: design the three judge voices and cache the SFX.

    uv run python -m server.voice.setup

Judge voices are DESIGNED from each judge.json's voice_description -- never
cloned. New voice IDs are written into .env for any VOICE_JUDGE_* still empty.
"""

from __future__ import annotations

import re

import typer

from server.config import get_settings
from server.judges.personas import load_personas
from server.voice.speech import design_voice, ensure_sfx_cache


def _set_env(name: str, value: str) -> None:
    env = get_settings().root / ".env"
    text = env.read_text(encoding="utf-8") if env.exists() else ""
    line = f"{name}={value}"
    pattern = re.compile(rf"^{re.escape(name)}=.*$", re.MULTILINE)
    text = pattern.sub(line, text) if pattern.search(text) else text.rstrip("\n") + f"\n{line}\n"
    env.write_text(text, encoding="utf-8")


def main(redesign: bool = typer.Option(False, help="Replace voices already in .env")) -> None:
    settings = get_settings()
    for persona in load_personas():
        field = persona.voice_id_env.lower()
        if getattr(settings, field, "") and not redesign:
            typer.echo(f"{persona.voice_id_env}: already set, skipping")
            continue
        if not persona.voice_description:
            raise typer.BadParameter(f"{persona.judge_id}/judge.json has no voice_description")
        voice_id = design_voice(f"SceneStealer judge: {persona.name}", persona.voice_description)
        _set_env(persona.voice_id_env, voice_id)
        typer.secho(f"{persona.voice_id_env}={voice_id}", fg="green")

    for name, path in ensure_sfx_cache().items():
        typer.echo(f"sfx {name}: {path}")


if __name__ == "__main__":
    typer.run(main)
