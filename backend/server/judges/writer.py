"""OpenAI writes all three judges' reactions in ONE structured-output call.

The vote is already decided in code and handed to the model; its only job is to
write a reaction that matches it.

Codex builds this module and its tests -- log what it did in docs/codex-log.md.
"""

from __future__ import annotations

import json
from functools import lru_cache

from openai import OpenAI

from server.config import get_settings
from server.judges.personas import Persona
from server.scene import ScenePack
from server.schemas import ComparisonReport, JudgeLine, JudgeLines, MomentNote, Verdict

STYLE_RULES = """\
- Funny and specific.
- Roast the ACTING, never the person's looks.
- PG-13.
- Reference at least one concrete moment with its timestamp.
- The reaction must match the vote you were given. Never contradict it.
- Under about two sentences for the spoken line.
"""


class JudgeWriterError(RuntimeError):
    """The model's lines could not be trusted. The caller uses fallback_lines."""


def _moment(label: str, m: MomentNote | None) -> str:
    if m is None:
        return f"{label}: (none noted)"
    detail = "; ".join(x for x in (m.matched and f"matched {m.matched}",
                                   m.missed and f"missed {m.missed}") if x)
    return f"{label}: {m.t:.1f}s -- {detail or 'no detail'}"


def build_prompt(
    personas: list[Persona],
    verdict: Verdict,
    report: ComparisonReport,
    pack: ScenePack,
    *,
    overall: bool = True,
) -> str:
    """Assemble personas + scores + already-decided votes + moments.

    `personas` may be part of the panel: face and body are written first, while
    the voice is still being scored. `overall=False` leaves out pass/fail, which
    isn't decided until every vote is in.
    """
    votes = {v.judge_id: v for v in verdict.votes}
    judges = []
    for p in personas:
        vote = votes[p.judge_id]
        entry = report.score(p.category)
        judges.append(
            f'- judge_id "{p.judge_id}", {p.name}, judges {p.category.upper()}.\n'
            f"  Persona: {p.persona}\n"
            f"  Score {vote.score}/100 (needed {vote.threshold}). Reason: {entry.reason}\n"
            f"  VOTE: {vote.vote}"
        )
    flags = []
    if report.player_not_visible:
        flags.append("The player left the frame -- roast them for abandoning the scene.")
    if report.player_silent:
        flags.append("The player made no sound -- the voice judge should notice.")
    moments = "\n".join(
        f"- {m.t:.1f}s: matched {m.matched or '-'}; missed {m.missed or '-'}"
        for m in report.moments
    )
    return (
        f'A player just performed {pack.character_name} from "{pack.movie_title}" '
        f"on a talent-show stage. The judges react, in this order.\n\n"
        + "\n".join(judges)
        + (
            f"\n\nOverall: {'PASSED' if verdict.passed else 'FAILED'}"
            + (" with a GOLDEN BUZZER" if verdict.golden_buzzer else "")
            if overall
            else "\n\nThe other votes are still coming: don't predict the overall result."
        )
        + f"\n{_moment('Best moment', report.best_moment)}"
        + f"\n{_moment('Worst moment', report.worst_moment)}"
        + (f"\nMoment notes:\n{moments}" if moments else "")
        + ("\n" + "\n".join(flags) if flags else "")
        + "\n\nWrite one line per judge, in character.\n"
        + "spoken: read aloud. bubble: a slightly longer speech bubble. "
        + "tip: one concrete coaching tip for a retry.\n\n"
        + f"Style rules:\n{STYLE_RULES}"
    )


@lru_cache
def _client() -> OpenAI:
    s = get_settings()
    if not s.openai_api_key:
        raise JudgeWriterError("OPENAI_API_KEY is not set")
    # No retries: the SDK's backoff honours retry-after and can eat the whole
    # deliberation window, and a failure already has canned lines to fall back on.
    return OpenAI(api_key=s.openai_api_key, timeout=8, max_retries=0)


def _in_judge_order(lines: JudgeLines, personas: list[Persona]) -> JudgeLines:
    """Exactly one line per judge, in persona order, or the reply is rejected."""
    by_id = {line.judge_id: line for line in lines.lines}
    missing = [p.judge_id for p in personas if not by_id.get(p.judge_id)]
    if missing or len(lines.lines) != len(personas):
        raise JudgeWriterError(f"judge lines don't match the panel (missing: {missing})")
    return JudgeLines(lines=[by_id[p.judge_id] for p in personas])


def write_lines(
    personas: list[Persona],
    verdict: Verdict,
    report: ComparisonReport,
    pack: ScenePack,
    *,
    overall: bool = True,
) -> JudgeLines:
    """One OpenAI call with structured output -> validated JudgeLines."""
    response = _client().responses.parse(
        model=get_settings().openai_model_judges,
        instructions=(
            "You write reactions for original talent-show judges. "
            "The votes are final and were decided before you were asked."
        ),
        input=build_prompt(personas, verdict, report, pack, overall=overall),
        text_format=JudgeLines,
    )
    if response.output_parsed is None:
        raise JudgeWriterError("OpenAI returned no parsed lines")
    return _in_judge_order(response.output_parsed, personas)


@lru_cache
def _fallback_bank() -> dict:
    path = get_settings().assets_path / "fallback" / "lines.json"
    return json.loads(path.read_text(encoding="utf-8"))


def fallback_lines(verdict: Verdict, personas: list[Persona]) -> JudgeLines:
    """Pre-written lines by vote, from assets/fallback/. Used when OpenAI is down.

    Picked by score rather than at random, so the same performance still gets
    the same reaction.
    """
    bank = _fallback_bank()
    votes = {v.judge_id: v for v in verdict.votes}
    lines = []
    for p in personas:
        vote = votes[p.judge_id]
        options = bank[p.category][vote.vote]
        pick = options[vote.score % len(options)]
        lines.append(JudgeLine(judge_id=p.judge_id, **pick))
    return JudgeLines(lines=lines)
