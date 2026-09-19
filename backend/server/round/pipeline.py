"""Round lifecycle: recording -> judging -> verdict -> dub.

Grading runs FIRST and locally: face and body are measured from keypoints
(server/grading/), so even with every external service down there is a real
face score, a real body score and therefore a real verdict. The multimodal
model only scores the voice, and the judges' wording comes after the vote.

Two phases, so the show starts before the slowest call returns:
  1. face + body: graded (<0.5s), written, voiced -> `partial_ready` (~4s).
     The browser starts the reveal with those two judges.
  2. voice: side-by-side + OMNI (~8s, started in parallel with phase 1),
     then the voice judge's line -> `verdict_ready`. By the time the first two
     judges have spoken, the third is usually ready.
Face and body votes can't change in phase 2 -- it only ever sets the voice.
The dub runs in parallel too; it isn't needed until after the verdict.

Every stage that calls out has a fallback: OMNI down -> voice from the take's
loudness envelope, OpenAI down -> canned lines, ElevenLabs down -> bubbles only.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Awaitable, Callable
from pathlib import Path

from server.compare import omni
from server.compare.fallback import neutral_report
from server.config import get_settings
from server.grading import grade
from server.grading import voice as local_voice
from server.judges.personas import Persona, load_personas
from server.judges.writer import fallback_lines, write_lines
from server.media import composite, ffmpeg, keypoints
from server.rules.votes import apply_measurements, tally
from server.scene import ScenePack, load_pack, reference_keypoints, scene_dir
from server.schemas import (
    CategoryScore,
    ComparisonReport,
    JudgeLine,
    JudgeResult,
    JudgeStub,
    KeypointTimeline,
    RoundEvent,
    RoundResult,
)
from server.store import db
from server.voice import speech

log = logging.getLogger(__name__)

Publish = Callable[[RoundEvent], Awaitable[None]]

JUDGE_WRITER_TIMEOUT_S = 12.0
# Server-side player extraction samples less densely than the browser: it runs
# after the take, inside the wait, so it has to be quick (R5.8).
FALLBACK_KEYPOINT_FPS = 10.0
SPEECH_TIMEOUT_S = 10.0


def round_dir(round_id: str) -> Path:
    path = get_settings().data_path / "rounds" / round_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def round_media_url(round_id: str, name: str) -> str:
    """Served by server/main.py's /round-media mount over DATA_DIR/rounds."""
    return f"/round-media/{round_id}/{name}"


def reference_video(pack: ScenePack) -> Path:
    """The isolated character if prep got that far, else the plain trimmed clip."""
    folder = scene_dir(pack.scene_id)
    for name in ("isolated.mp4", "trimmed.mp4"):
        if (folder / name).exists():
            return folder / name
    raise FileNotFoundError(f"Scene '{pack.scene_id}' has no reference video -- run Scene Prep")


async def _grade(take: Path, pack: ScenePack, player: KeypointTimeline | None) -> ComparisonReport:
    """Face and body, measured. Browser keypoints if they came, else extract from the take."""
    reference = reference_keypoints(pack.scene_id)
    if reference is None:
        log.warning("Scene '%s' has no keypoints.json -- run prep.keyframes", pack.scene_id)
        return neutral_report("this scene has not been prepped for grading")
    if player is None or not player.samples:
        log.info("No browser keypoints; extracting from the take server-side")
        player = await asyncio.to_thread(keypoints.extract, take, FALLBACK_KEYPOINT_FPS)
    return grade(reference, player, [m.t for m in pack.key_moments])


def _merge_notes(graded: list, heard: list) -> list:
    """Graded moment notes, with the model's qualitative notes appended at the same beat."""
    merged = []
    for note in graded:
        near = min(heard, key=lambda h: abs(h.t - note.t), default=None)
        if near is not None and abs(near.t - note.t) <= 1.0:
            note = note.model_copy(update={
                "matched": "; ".join(x for x in (note.matched, near.matched) if x),
                "missed": "; ".join(x for x in (note.missed, near.missed) if x),
            })
        merged.append(note)
    return merged or heard


def _local_voice(take: Path, pack: ScenePack) -> CategoryScore:
    """Voice from loudness envelopes alone: no network, still different every take."""
    reference = scene_dir(pack.scene_id) / "trimmed.mp4"
    ref_levels = ffmpeg.audio_levels(reference) if reference.exists() else []
    return local_voice.estimate(ref_levels, ffmpeg.audio_levels(take))


async def _voice(
    sbs: Path, take: Path, pack: ScenePack, graded: ComparisonReport
) -> tuple[ComparisonReport, bool]:
    """OMNI sets ONLY the voice score and adds colour to the notes (I3, R7.9).

    Face and body stay exactly as measured; if OMNI is forced off, slow or
    failing, the voice comes from the local envelope estimate instead.
    """
    settings = get_settings()
    try:
        if settings.force_fallback:
            raise RuntimeError("forced fallback")
        heard = await asyncio.wait_for(
            asyncio.to_thread(omni.compare, sbs, pack), timeout=settings.omni_timeout_s
        )
        return graded.model_copy(update={
            "voice": heard.voice,
            "moments": _merge_notes(graded.moments, heard.moments),
            "player_silent": heard.player_silent,
        }), False
    except Exception as exc:  # noqa: BLE001 - any OMNI failure means the local estimate
        log.warning("OMNI voice failed, using the local estimate: %r", exc)
        estimate = await asyncio.to_thread(_local_voice, take, pack)
        return graded.model_copy(update={"voice": estimate}), True


async def _lines(
    personas: list[Persona], verdict, report, pack, *, overall: bool = True
) -> tuple[list[JudgeLine], bool]:
    if not personas:
        return [], False
    if get_settings().force_fallback:
        return fallback_lines(verdict, personas).lines, True
    try:
        lines = await asyncio.wait_for(
            asyncio.to_thread(
                lambda: write_lines(personas, verdict, report, pack, overall=overall)
            ),
            timeout=JUDGE_WRITER_TIMEOUT_S,
        )
        return lines.lines, False
    except Exception as exc:  # noqa: BLE001 - any writer failure means canned lines
        log.warning("Judge writer failed, using fallback lines: %r", exc)
        return fallback_lines(verdict, personas).lines, True


async def _speak(round_id: str, persona: Persona, line: JudgeLine) -> str | None:
    """One judge's audio URL, or None -- the speech bubble still shows."""
    voice_id = getattr(get_settings(), persona.voice_id_env.lower(), "")
    if not voice_id or get_settings().force_fallback:
        return None
    name = f"judge_{persona.judge_id}.mp3"
    try:
        await asyncio.wait_for(
            asyncio.to_thread(speech.speak, line, voice_id, round_dir(round_id) / name),
            timeout=SPEECH_TIMEOUT_S,
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("Voice for %s failed: %r", persona.judge_id, exc)
        return None
    return round_media_url(round_id, name)


async def _composite(round_id: str, take: Path, sbs: Path, pack: ScenePack) -> Path:
    """The player composited into the scene where SAM 2 masks exist, else the side-by-side.

    Cosmetic only (I9): a failure here costs the overlay, never the verdict.
    """
    folder = scene_dir(pack.scene_id)
    masks, clip = folder / "masks" / "masks.json", folder / "trimmed.mp4"
    if not (masks.exists() and clip.exists()):
        return sbs
    try:
        return await asyncio.to_thread(
            composite.replay, clip, masks, take, round_dir(round_id) / "replay.mp4"
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("Overlay replay failed, using the side-by-side: %r", exc)
        return sbs


async def _dub(round_id: str, take: Path, sbs: Path, pack: ScenePack) -> str:
    """The replay -- the player inside the scene -- with their voice run through
    the dub voice designed from the pack's dub_voice_style.

    Without a designed dub voice (or if ElevenLabs fails) the replay keeps the
    player's own audio -- it is still worth watching.
    """
    folder = round_dir(round_id)
    video = await _composite(round_id, take, sbs, pack)
    if not pack.dub_voice_id or get_settings().force_fallback:
        return round_media_url(round_id, video.name)
    try:
        audio = await asyncio.to_thread(ffmpeg.extract_audio, take, folder / "take.wav")
        dubbed = await asyncio.to_thread(speech.dub, audio, pack.dub_voice_id, folder / "dub.mp3")
        await asyncio.to_thread(ffmpeg.replace_audio, video, dubbed, folder / "dub.mp4")
        return round_media_url(round_id, "dub.mp4")
    except Exception as exc:  # noqa: BLE001
        log.warning("Dub failed, replaying the original take: %r", exc)
        return round_media_url(round_id, video.name)


def _waveforms(take: Path, pack: ScenePack, dst: Path) -> Path | None:
    """Original-clip vs microphone loudness, for the replay's waveform comparison.

    The player's side is the RAW take, not the dub: the point is to see how the
    player's own delivery lined up with the character's. Voiced flags use the
    same measure as the local voice estimate, so the picture and that score agree.
    """
    clip = scene_dir(pack.scene_id) / "trimmed.mp4"
    if not clip.exists():
        return None
    original, player = ffmpeg.audio_levels(clip), ffmpeg.audio_levels(take)
    if not original or not player:
        return None
    dst.write_text(json.dumps({
        "hop_s": local_voice.HOP_S,
        "original": {"db": original, "voiced": local_voice.voiced(original)},
        "player": {"db": player, "voiced": local_voice.voiced(player)},
    }, separators=(",", ":")), encoding="utf-8")
    return dst


def _judge_results(
    personas: list[Persona], verdict, lines: list[JudgeLine], urls: list[str | None]
) -> list[JudgeResult]:
    votes = {v.judge_id: v for v in verdict.votes}
    return [
        JudgeResult(
            judge_id=p.judge_id,
            name=p.name,
            category=p.category,
            vote=votes[p.judge_id].vote,
            score=votes[p.judge_id].score,
            spoken=line.spoken,
            bubble=line.bubble,
            tip=line.tip,
            audio_url=url,
        )
        for p, line, url in zip(personas, lines, urls, strict=True)
    ]


async def run_round(
    round_id: str,
    take: Path,
    nickname: str,
    publish: Publish,
    remember: Callable[[RoundResult], None],
    attempt: int = 1,
    player_keypoints: KeypointTimeline | None = None,
) -> RoundResult:
    """Glue the lanes together, emitting SSE events as each stage lands.

    `remember` stores the result where GET /rounds/{id} can see it; it is called
    before verdict_ready goes out, so the browser never fetches too early.
    """
    settings = get_settings()
    pack = load_pack()
    folder = round_dir(round_id)
    await publish(RoundEvent(event="judging", round_id=round_id))
    started = last = time.monotonic()

    def lap(stage: str) -> None:
        nonlocal last
        now = time.monotonic()
        log.info("round %s: %-12s %5.1fs (total %.1fs)", round_id, stage, now - last, now - started)
        last = now

    graded = await _grade(take, pack, player_keypoints)
    lap("grading")

    personas = load_personas()
    first = [p for p in personas if p.category != "voice"]
    later = [p for p in personas if p.category == "voice"]
    dub_task: asyncio.Task[str] | None = None

    async def voice_phase() -> tuple[ComparisonReport, bool]:
        """Side-by-side -> OMNI voice (or the local estimate), with the dub kicked off."""
        nonlocal dub_task
        try:
            sbs = await asyncio.to_thread(
                ffmpeg.side_by_side, reference_video(pack), take, folder / "side_by_side.mp4"
            )
        except Exception as exc:  # noqa: BLE001 - no side-by-side: no OMNI, no replay
            log.warning("Side-by-side failed, voice from the local estimate: %r", exc)
            estimate = await asyncio.to_thread(_local_voice, take, pack)
            return graded.model_copy(update={"voice": estimate}), True
        dub_task = asyncio.create_task(_dub(round_id, take, sbs, pack))
        (report, fell_back), loudness = await asyncio.gather(
            _voice(sbs, take, pack, graded), asyncio.to_thread(ffmpeg.mean_volume_db, take)
        )
        return apply_measurements(report, loudness), fell_back

    voice_task = asyncio.create_task(voice_phase())

    # Phase 1: face and body are already decided -- say so while the voice is scored.
    early = tally(graded, pack)  # its voice vote is a placeholder and is never shown
    early_lines, early_fallback = await _lines(first, early, graded, pack, overall=False)
    early_urls = await asyncio.gather(
        *(_speak(round_id, p, line) for p, line in zip(first, early_lines, strict=True))
    )
    early_judges = _judge_results(first, early, early_lines, early_urls)
    remember(RoundResult(
        round_id=round_id, nickname=nickname, attempt=attempt, scene_id=pack.scene_id,
        face=graded.face.score, body=graded.body.score,
        judges=early_judges,
        best_moment=graded.best_moment, worst_moment=graded.worst_moment,
        fallback_used=early_fallback,
        complete=False,
        pending=[JudgeStub(judge_id=p.judge_id, name=p.name, category=p.category)
                 for p in later],
    ))
    await publish(RoundEvent(event="partial_ready", round_id=round_id))
    lap("face+body")

    # Phase 2: the voice, then the voice judge's line.
    try:
        report, score_fallback = await voice_task
    except Exception as exc:  # noqa: BLE001 - the round must still end in a verdict
        log.warning("Voice phase failed, using the local estimate: %r", exc)
        estimate = await asyncio.to_thread(_local_voice, take, pack)
        report, score_fallback = graded.model_copy(update={"voice": estimate}), True
    verdict = tally(report, pack)
    lap("voice + tally")
    late_lines, late_fallback = await _lines(later, verdict, report, pack)
    late_urls = await asyncio.gather(
        *(_speak(round_id, p, line) for p, line in zip(later, late_lines, strict=True))
    )
    lap("voice judge")

    result = RoundResult(
        round_id=round_id,
        nickname=nickname,
        attempt=attempt,
        scene_id=pack.scene_id,
        face=report.face.score,
        body=report.body.score,
        voice=report.voice.score,
        combined=verdict.combined,
        judges=early_judges + _judge_results(later, verdict, late_lines, late_urls),
        best_moment=report.best_moment,
        worst_moment=report.worst_moment,
        passed=verdict.passed,
        golden_buzzer=verdict.golden_buzzer,
        fallback_used=early_fallback or score_fallback or late_fallback,
    )
    remember(result)
    await publish(RoundEvent(event="verdict_ready", round_id=round_id))
    await asyncio.to_thread(db.save_result, result)  # after: never delays the verdict

    try:
        waves = await asyncio.to_thread(_waveforms, take, pack, folder / "waveforms.json")
        if waves:
            result.waveforms = round_media_url(round_id, waves.name)
    except Exception as exc:  # noqa: BLE001 - a missing waveform never costs the replay
        log.warning("Waveforms failed: %r", exc)
    result.dub_url = await dub_task if dub_task else None
    skeleton = composite.overlay_path(folder / "replay.mp4")
    if result.dub_url and skeleton.exists():  # only written when the overlay replay was built
        result.replay_overlay = round_media_url(round_id, skeleton.name)
    lap("dub")
    remember(result)
    await asyncio.to_thread(db.save_result, result)
    await publish(RoundEvent(event="dub_ready", round_id=round_id, detail=result.dub_url))

    if settings.delete_takes_after_scoring:
        for leftover in (take, folder / "take.wav"):
            leftover.unlink(missing_ok=True)
    return result
