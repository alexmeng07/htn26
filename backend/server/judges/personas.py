"""Judge personas, loaded from assets/judges/<judge_id>/judge.json.

Three ORIGINAL characters matching the sprite set. Never impersonate a real
talent-show judge by name or voice.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from server.config import get_settings
from server.schemas import Category


class Persona(BaseModel):
    judge_id: str
    name: str
    category: Category
    voice_id_env: str  # e.g. VOICE_JUDGE_FACE -- the ID itself stays in .env
    persona: str  # one line, fed to the OpenAI prompt


def load_personas() -> list[Persona]:
    root: Path = get_settings().assets_path / "judges"
    personas = []
    for meta in sorted(root.glob("*/judge.json")):
        personas.append(Persona(**json.loads(meta.read_text(encoding="utf-8"))))
    if not personas:
        raise FileNotFoundError(f"No judge.json files under {root}")
    return personas
