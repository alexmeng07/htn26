"""OMNI client: the only model here that watches and listens in one pass.

Used twice:
  1. Scene Prep -- write the reference sheet for the target character (cached).
  2. Live round -- compare character vs player on face, body and voice.

All scene-specific wording is interpolated from the scene pack; nothing about
any particular movie or character is written in this file.
"""

from __future__ import annotations

from pathlib import Path

from server.config import get_settings
from server.scene import ScenePack
from server.schemas import ComparisonReport

COMPARE_INSTRUCTIONS = """\
Left is the reference actor playing {character_name} in "{movie_title}".
Right is the player performing the same moment. The audio is the player's.

Reference sheet for each key moment:
{reference_sheet}

For each moment, compare the player to the reference on face, body and voice.
The voice judge scores {voice_rubric}.
Give each category a 0-100 score with a one-sentence reason, and note the
player's best and worst moment with timestamps.
Be fair: this is a fun game, and "logical" matters more than "exact".
Flag it if the player was not visible or was silent.
Respond with JSON only, matching this schema:
{schema}
"""

VOICE_RUBRIC = {
    "emotional": (
        "emotional vocal delivery (breaks, laughs, sobs, breaths at the right "
        "moments), not line accuracy"
    ),
    "lines": "line delivery: the words, timing and intonation",
}


def build_prompt(pack: ScenePack) -> str:
    """Fill the instruction template from the scene pack."""
    sheet = "\n".join(
        f"- {m.t:.1f}s {m.label}: face={m.face} | body={m.body} | voice={m.voice}"
        for m in pack.key_moments
    ) or "(no key moments yet -- run Scene Prep)"
    return COMPARE_INSTRUCTIONS.format(
        character_name=pack.character_name,
        movie_title=pack.movie_title,
        reference_sheet=sheet,
        voice_rubric=VOICE_RUBRIC.get(pack.voice_mode, VOICE_RUBRIC["emotional"]),
        schema=ComparisonReport.model_json_schema(),
    )


def compare(video: Path, pack: ScenePack, *, dev_model: bool = False) -> ComparisonReport:
    """Send the side-by-side video to OMNI and validate the reply.

    Lane C: call the yibuapi OpenAI-compatible endpoint, validate against
    ComparisonReport, retry once on malformed JSON, and raise TimeoutError past
    ~8s so server/compare/fallback.py can take over.
    """
    get_settings()  # keeps the import meaningful until the call is wired up
    raise NotImplementedError("Lane C: OMNI client not implemented yet")
