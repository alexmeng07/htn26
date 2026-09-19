"""OMNI client: the only model here that watches and listens in one pass.

Used twice:
  1. Scene Prep -- write the reference sheet for the target character (cached).
  2. Live round -- score the player's VOICE against the reference sheet, and add
     qualitative notes. Face and body are measured geometrically elsewhere
     (server/grading/); whatever this model says about them is never a score.

All scene-specific wording is interpolated from the scene pack; nothing about
any particular movie or character is written in this file.
"""

from __future__ import annotations

import base64
import json
import re
from pathlib import Path

from openai import APIError, OpenAI
from pydantic import ValidationError

from server.config import get_settings
from server.scene import ScenePack
from server.schemas import ComparisonReport

COMPARE_INSTRUCTIONS = """\
Left is the reference actor playing {character_name} in "{movie_title}".
Right is the player performing the same moment. The audio is the player's.

Reference sheet for each key moment:
{reference_sheet}

Your job is the VOICE. The voice judge scores {voice_rubric}.
Give voice a 0-100 score with a one-sentence reason. Face and body are measured
separately by tracking; fill those fields with your honest impression, but spend
your attention on how the player sounds. For each moment, note in a few words
what the player matched and missed, and give the best and worst moment with
timestamps in seconds.
Be fair: this is a fun game, and "logical" matters more than "exact".
Flag it if the player was not visible or was silent.
Never quote, transcribe or repeat any words that are spoken: describe HOW
things are said (pace, pitch, breath, emotion), never WHAT is said.
Respond with JSON only, matching this schema:
{schema}
"""

VOICE_RUBRIC = {
    "emotional": (
        "emotional vocal delivery (breaks, laughs, sobs, breaths at the right "
        "moments), not line accuracy"
    ),
    "lines": "line delivery: the timing and intonation of the lines",
}


class OmniError(RuntimeError):
    """OMNI could not produce a usable report. The caller falls back."""


def build_prompt(pack: ScenePack) -> str:
    """Fill the instruction template from the scene pack."""
    sheet = "\n".join(
        f"- {m.t:.1f}s {m.label}: face={m.face} | body={m.body} | voice={m.voice}"
        for m in pack.key_moments
    ) or "(no reference sheet yet -- judge directly against the left side)"
    return COMPARE_INSTRUCTIONS.format(
        character_name=pack.character_name,
        movie_title=pack.movie_title,
        reference_sheet=sheet,
        voice_rubric=VOICE_RUBRIC.get(pack.voice_mode, VOICE_RUBRIC["emotional"]),
        schema=json.dumps(ComparisonReport.model_json_schema()),
    )


def _client() -> OpenAI:
    s = get_settings()
    if not (s.omni_base_url and s.omni_api_key):
        raise OmniError("OMNI is not configured (OMNI_BASE_URL / OMNI_API_KEY)")
    return OpenAI(base_url=s.omni_base_url, api_key=s.omni_api_key, timeout=s.omni_timeout_s)


def model_name(*, dev_model: bool | None = None) -> str:
    """The flash model unless told otherwise: the plus model is for the demo only."""
    s = get_settings()
    use_dev = s.omni_use_dev_model if dev_model is None else dev_model
    return (s.omni_model_dev if use_dev else s.omni_model) or s.omni_model or s.omni_model_dev


def ask(video: Path, prompt: str, *, dev_model: bool | None = None) -> str:
    """One video + one text prompt -> the model's full text reply.

    Qwen-Omni over the OpenAI-compatible API only answers when streamed, and
    takes the video inline as a base64 data URI.
    """
    data_uri = "data:video/mp4;base64," + base64.b64encode(video.read_bytes()).decode()
    try:
        stream = _client().chat.completions.create(
            model=model_name(dev_model=dev_model),
            messages=[{
                "role": "user",
                "content": [
                    {"type": "video_url", "video_url": {"url": data_uri}},
                    {"type": "text", "text": prompt},
                ],
            }],
            modalities=["text"],
            stream=True,
        )
        parts = [
            chunk.choices[0].delta.content
            for chunk in stream
            if chunk.choices and chunk.choices[0].delta.content
        ]
    except APIError as exc:
        raise OmniError(f"OMNI request failed: {exc}") from exc
    return "".join(parts)


# A phrase in straight or curly quotes: a line of dialogue the model repeated.
_QUOTED = re.compile(
    r"""\s*(?:"[^"]*"|'[^']{2,}'|\u201c[^\u201d]*\u201d|\u2018[^\u2019]{2,}\u2019)"""
)


def _unquote(text: str) -> str:
    """The prompt says never quote dialogue; this makes sure. Film lines can be
    anything, and this text reaches the judges' prompt and the screen."""
    return re.sub(r"\s{2,}", " ", _QUOTED.sub("", text)).strip(" ,;:-")


def _scrub(report: ComparisonReport) -> ComparisonReport:
    for entry in (report.face, report.body, report.voice):
        entry.reason = _unquote(entry.reason)
    for m in [*report.moments, report.best_moment, report.worst_moment]:
        if m is not None:
            m.matched, m.missed = _unquote(m.matched), _unquote(m.missed)
    return report


def parse_report(text: str) -> ComparisonReport:
    """Pull the JSON object out of the reply (models like to wrap it in fences)."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("no JSON object in OMNI reply")
    return _scrub(ComparisonReport.model_validate_json(match.group(0)))


def compare(
    video: Path, pack: ScenePack, *, dev_model: bool | None = None
) -> ComparisonReport:
    """Send the side-by-side video to OMNI and validate the reply.

    Malformed JSON gets one retry. Anything else -- timeout, refusal, a second
    bad reply -- raises OmniError so the round falls back instead of dying.
    """
    prompt = build_prompt(pack)
    last_error: Exception | None = None
    for _ in range(2):
        text = ask(video, prompt, dev_model=dev_model)
        try:
            return parse_report(text)
        except (ValueError, ValidationError) as exc:
            last_error = exc
    raise OmniError(f"OMNI reply was not a valid report twice: {last_error}")
