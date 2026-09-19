"""OpenAI writes all three judges' reactions in ONE structured-output call.

The vote is already decided in code and handed to the model; its only job is to
write a reaction that matches it.

Codex builds this module and its tests -- log what it did in docs/codex-log.md.
"""

from __future__ import annotations

from server.judges.personas import Persona
from server.scene import ScenePack
from server.schemas import ComparisonReport, JudgeLines, Verdict

STYLE_RULES = """\
- Funny and specific.
- Roast the ACTING, never the person's looks.
- PG-13.
- Reference at least one concrete moment with its timestamp.
- The reaction must match the vote you were given. Never contradict it.
- Under about two sentences for the spoken line.
"""


def build_prompt(
    personas: list[Persona], verdict: Verdict, report: ComparisonReport, pack: ScenePack
) -> str:
    """Lane D: assemble personas + scores + already-decided votes + moments."""
    raise NotImplementedError("Lane D: judge prompt not implemented yet")


def write_lines(
    personas: list[Persona], verdict: Verdict, report: ComparisonReport, pack: ScenePack
) -> JudgeLines:
    """Lane D: one OpenAI call with structured output -> validated JudgeLines."""
    raise NotImplementedError("Lane D: judge writer not implemented yet")


def fallback_lines(verdict: Verdict, personas: list[Persona]) -> JudgeLines:
    """Pre-written lines by score band, from assets/fallback/. Used when OpenAI is down."""
    raise NotImplementedError("Lane D: fallback lines not implemented yet")
