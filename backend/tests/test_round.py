"""Offline tests for the live-round pieces around the models: parsing, scrubbing,
fallbacks and the leaderboard. No network calls."""

import json

import pytest

from server.compare.omni import parse_report
from server.judges.personas import load_personas
from server.judges.writer import JudgeWriterError, _in_judge_order, build_prompt, fallback_lines
from server.rules.votes import tally
from server.schemas import CategoryScore, ComparisonReport, JudgeLine, JudgeLines, RoundResult
from tests.test_votes import pack


def report(face=80, body=50, voice=75):
    return ComparisonReport(
        face=CategoryScore(score=face, reason="f"),
        body=CategoryScore(score=body, reason="b"),
        voice=CategoryScore(score=voice, reason="v"),
    )


def test_parse_report_strips_fences_and_quoted_dialogue():
    body = report().model_dump()
    body["best_moment"] = {"t": 2.5, "matched": "Angry look while saying 'some line here'"}
    body["voice"]["reason"] = 'Nailed the pause before "another line" landed'
    parsed = parse_report("```json\n" + json.dumps(body) + "\n```")
    assert parsed.best_moment.matched == "Angry look while saying"
    assert parsed.voice.reason == "Nailed the pause before landed"


def test_parse_report_rejects_non_json():
    with pytest.raises(ValueError):
        parse_report("I could not see the video.")


def test_personas_are_in_stage_order():
    assert [p.category for p in load_personas()] == ["face", "body", "voice"]


def test_judge_prompt_carries_each_decided_vote():
    personas = load_personas()
    verdict = tally(report(), pack())
    prompt = build_prompt(personas, verdict, report(), pack())
    for p in personas:
        assert p.name in prompt
    assert prompt.count("VOTE: NO") == 1 and prompt.count("VOTE: YES") == 2


def test_judge_lines_must_cover_the_whole_panel():
    personas = load_personas()
    line = JudgeLine(judge_id="face", spoken="s", bubble="b", tip="t")
    with pytest.raises(JudgeWriterError):
        _in_judge_order(JudgeLines(lines=[line]), personas)
    shuffled = [line.model_copy(update={"judge_id": p.judge_id}) for p in reversed(personas)]
    ordered = _in_judge_order(JudgeLines(lines=shuffled), personas)
    assert [x.judge_id for x in ordered.lines] == [p.judge_id for p in personas]


def test_fallback_lines_are_deterministic():
    personas = load_personas()
    verdict = tally(report(), pack())
    first = fallback_lines(verdict, personas)
    assert first == fallback_lines(verdict, personas)
    assert [x.judge_id for x in first.lines] == [p.judge_id for p in personas]


def test_local_leaderboard_keeps_best_per_nickname(tmp_path, monkeypatch):
    from server.store import db

    monkeypatch.setattr(db, "_local_dir", lambda: tmp_path)
    for rid, nick, combined in [("a", "ann", 60), ("b", "ann", 80), ("c", "bob", 70)]:
        r = RoundResult(round_id=rid, nickname=nick, scene_id="s", combined=combined)
        (tmp_path / f"{rid}.json").write_text(r.model_dump_json(), encoding="utf-8")
    top = db._top_local(10, None)
    assert [(e.nickname, e.combined) for e in top] == [("ann", 80), ("bob", 70)]


def test_reference_sheet_matches_notes_whatever_the_timestamp_format():
    from prep.annotate_reference import merge
    from server.scene import KeyMoment

    moments = [KeyMoment(t=0.87), KeyMoment(t=3.27), KeyMoment(t=9.0)]
    notes = [{"t": "0.9s", "face": "brows up", "body": "still", "voice": "firm"},
             {"t": 3.27, "face": "smirk", "body": "leans", "voice": "quick"}]
    merged = merge(moments, notes)
    assert [m.face for m in merged] == ["brows up", "smirk", ""]  # 9.0 has no note within 1s


# ------------------------------------------------ two-phase round (early reveal)
def _run_round_offline(tmp_path, monkeypatch, *, voice_fails=False):
    """run_round with the slow and external parts stubbed; returns events and snapshots."""
    import asyncio

    from server.config import get_settings
    from server.round import pipeline

    settings = get_settings()
    monkeypatch.setattr(settings, "force_fallback", True)  # canned lines, no speech
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    monkeypatch.setattr(pipeline, "load_pack", lambda: pack(face=70, body=60, voice=70))
    monkeypatch.setattr(pipeline, "reference_video", lambda _pack: tmp_path / "ref.mp4")

    async def graded(*_):
        return report(face=81, body=55, voice=0)

    async def heard(_sbs, _take, _pack, base):
        await asyncio.sleep(0.05)  # the voice lands after the face+body reveal
        if voice_fails:
            raise RuntimeError("OMNI exploded")
        return base.model_copy(update={"voice": CategoryScore(score=88, reason="v")}), False

    monkeypatch.setattr(pipeline, "_grade", graded)
    monkeypatch.setattr(pipeline, "_voice", heard)
    monkeypatch.setattr(pipeline, "_local_voice", lambda *_: CategoryScore(score=42, reason="est"))
    monkeypatch.setattr(pipeline.ffmpeg, "side_by_side", lambda *a: tmp_path / "sbs.mp4")
    monkeypatch.setattr(pipeline.ffmpeg, "mean_volume_db", lambda *_: -20.0)
    monkeypatch.setattr(pipeline.db, "save_result", lambda *_: None)

    async def no_dub(*_):
        return "/round-media/x/replay.mp4"

    monkeypatch.setattr(pipeline, "_dub", no_dub)

    events, snapshots = [], []

    async def publish(event):
        events.append(event.event)

    def remember(result):
        snapshots.append((len(events), result.model_copy(deep=True)))

    final = asyncio.run(
        pipeline.run_round("r1", tmp_path / "take.webm", "tester", publish, remember)
    )
    return events, snapshots, final


def test_face_and_body_are_revealed_before_the_voice(tmp_path, monkeypatch):
    events, snapshots, final = _run_round_offline(tmp_path, monkeypatch)
    assert events == ["judging", "partial_ready", "verdict_ready", "dub_ready"]

    published_at, partial = snapshots[0]
    assert published_at == 1  # remembered BEFORE partial_ready went out
    assert not partial.complete
    assert [j.category for j in partial.judges] == ["face", "body"]
    assert [p.category for p in partial.pending] == ["voice"]

    assert final.complete and not final.pending
    assert [j.category for j in final.judges] == ["face", "body", "voice"]
    assert final.voice == 88
    # Phase 2 can't move a face or body vote: what was revealed early stands.
    for early, late in zip(partial.judges, final.judges, strict=False):
        assert (early.vote, early.score, early.spoken) == (late.vote, late.score, late.spoken)


def test_a_crashed_voice_phase_still_ends_in_a_full_verdict(tmp_path, monkeypatch):
    events, _, final = _run_round_offline(tmp_path, monkeypatch, voice_fails=True)
    assert events[-2:] == ["verdict_ready", "dub_ready"]
    assert final.complete and len(final.judges) == 3
    assert final.voice == 42 and final.fallback_used
