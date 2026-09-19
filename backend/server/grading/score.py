"""Align two keypoint timelines and aggregate them into a ComparisonReport.

Alignment: the clip and the recorder start on the same tick (R5.1), so time t in
the take is time t in the reference. Only jitter and reaction lag need
absorbing: each reference sample is scored against the BEST player sample
within +-WINDOW_S of it. No time-warping, no drift correction.

Output is the existing ComparisonReport, so this path and the multimodal voice
path stay interchangeable (I7). Voice is left for the caller to fill.
"""

from __future__ import annotations

import bisect
from dataclasses import dataclass, field

from server.grading import face, pose
from server.schemas import CategoryScore, ComparisonReport, KeypointTimeline, MomentNote

# Reaction-lag tolerance either side of a reference sample (default 0.25s, tune in 6.7).
WINDOW_S = 0.25
# Samples near a key moment count this much more (default 3, tune in 6.7).
KEY_MOMENT_WEIGHT = 3.0
# Below this share of player samples with a person in them -> not visible (default 0.6).
VISIBLE_SHARE = 0.6
# Body score when the reference never shows enough body to measure anything.
UNMEASURABLE_BODY = 65
# Without key moments, best/worst are picked from buckets this long.
BUCKET_S = 1.0
# A measure must be visible in at least this share of the reference's detected
# frames to count at all (default 0.5, tune in 6.7). An elbow flickering in at the
# edge of a close-up is framing noise, not something the actor does.
STABLE_SCOPE_SHARE = 0.5


@dataclass
class _Prepared:
    t: float
    measures: pose.Measured
    face: dict[str, float]


@dataclass
class _Frame:
    """One reference sample, graded against its best-matching player sample."""

    t: float
    body: float | None = None
    face: float | None = None
    body_err: dict[str, float] = field(default_factory=dict)
    face_err: dict[str, float] = field(default_factory=dict)


def _prepare(timeline: KeypointTimeline, *, mirrored: bool = False) -> list[_Prepared]:
    out = []
    for s in sorted(timeline.samples, key=lambda s: s.t):
        s = pose.mirror(s) if mirrored else s
        out.append(_Prepared(s.t, pose.measure(s.pose, timeline.aspect), s.face))
    return out


def _stable_scope(ref: list[_Prepared]) -> list[_Prepared]:
    """Drop measures the reference only shows now and then (R6.7 still holds: the
    scope comes from the reference alone, it just ignores flicker at the frame edge)."""
    posed = [r for r in ref if r.measures]
    if not posed:
        return ref
    counts: dict[str, int] = {}
    for r in posed:
        for name in r.measures:
            counts[name] = counts.get(name, 0) + 1
    keep = {n for n, c in counts.items() if c / len(posed) >= STABLE_SCOPE_SHARE}
    return [_Prepared(r.t, {n: v for n, v in r.measures.items() if n in keep}, r.face)
            for r in ref]


def _window(player: list[_Prepared], times: list[float], t: float) -> list[_Prepared]:
    lo = bisect.bisect_left(times, t - WINDOW_S - 1e-9)
    hi = bisect.bisect_right(times, t + WINDOW_S + 1e-9)
    return player[lo:hi]


def _grade_frames(ref: list[_Prepared], player: list[_Prepared]) -> list[_Frame]:
    times = [p.t for p in player]
    frames = []
    for r in ref:
        if not r.measures and not r.face:
            continue  # the character is not on screen: excluded, never a zero (R6.8)
        frame = _Frame(r.t)
        nearby = _window(player, times, r.t)

        if r.measures:
            frame.body, frame.body_err = 0.0, {n: pose.MAX_ERROR for n in r.measures}
            for p in nearby:
                errors = pose.frame_errors(r.measures, p.measures)
                score = pose.frame_score(r.measures, errors)
                if score > frame.body:
                    frame.body, frame.body_err = score, errors

        if r.face:
            frame.face = 0.0
            frame.face_err = {
                n: v for n, v in r.face.items() if face.weight(n) and v >= face.ACTIVE
            }
            for p in nearby:
                if not p.face:
                    continue
                errors = face.frame_errors(r.face, p.face)
                score = face.frame_score(errors)
                if score > frame.face:
                    frame.face, frame.face_err = score, errors
        frames.append(frame)
    return frames


def _weight(t: float, moments: list[float]) -> float:
    return KEY_MOMENT_WEIGHT if any(abs(t - m) <= WINDOW_S for m in moments) else 1.0


def _mean(frames: list[_Frame], attr: str, moments: list[float]) -> float | None:
    pairs = [(getattr(f, attr), _weight(f.t, moments))
             for f in frames if getattr(f, attr) is not None]
    total = sum(w for _, w in pairs)
    return sum(v * w for v, w in pairs) / total if total else None


def _gaps(frames: list[_Frame]) -> dict[str, float]:
    """Mean normalised error per measure/channel, both categories on one 0..1 scale."""
    sums: dict[str, list[float]] = {}
    for f in frames:
        for name, err in f.body_err.items():
            sums.setdefault(pose.LABELS[name], []).append(err / pose.MAX_ERROR)
        for name, err in f.face_err.items():
            sums.setdefault(face.label(name), []).append(min(err / face.MAX_ERROR, 1.0))
    return {name: sum(v) / len(v) for name, v in sums.items()}


def _category_gaps(frames: list[_Frame], attr: str) -> dict[str, float]:
    keep = [_Frame(f.t, body_err=f.body_err) if attr == "body" else _Frame(f.t, face_err=f.face_err)
            for f in frames]
    return _gaps(keep)


def _extremes(gaps: dict[str, float]) -> tuple[str, str]:
    ordered = sorted(gaps.items(), key=lambda kv: (kv[1], kv[0]))
    return ordered[0][0], ordered[-1][0]


def _moment_notes(frames: list[_Frame], moments: list[float]) -> list[tuple[float, MomentNote]]:
    """(score, note) per key moment -- or per BUCKET_S slice when there are none."""
    if moments:
        groups = [(m, [f for f in frames if abs(f.t - m) <= WINDOW_S]) for m in moments]
    else:
        buckets: dict[int, list[_Frame]] = {}
        for f in frames:
            buckets.setdefault(int(f.t // BUCKET_S), []).append(f)
        groups = [(fs[len(fs) // 2].t, fs) for _, fs in sorted(buckets.items())]

    notes = []
    for t, group in groups:
        scores = [s for f in group for s in (f.body, f.face) if s is not None]
        if not scores:
            continue
        gaps = _gaps(group)
        if gaps:
            best, worst = _extremes(gaps)
            note = MomentNote(
                t=round(t, 2), matched=f"{best} on the mark", missed=f"{worst} was off"
            )
        else:
            note = MomentNote(t=round(t, 2))
        notes.append((sum(scores) / len(scores), note))
    return notes


def _total(frames: list[_Frame], attr: str) -> float:
    return sum(getattr(f, attr) or 0.0 for f in frames)


def grade(
    reference: KeypointTimeline,
    player: KeypointTimeline,
    key_moments: list[float] | None = None,
) -> ComparisonReport:
    """Face and body scores for one take. Deterministic: same input, same report."""
    moments = sorted(key_moments or [])
    ref = _stable_scope(_prepare(reference))

    # The live preview is mirrored, so players tend to copy the mirror image.
    # Try both orientations per category and keep the better: fair either way.
    as_is = _grade_frames(ref, _prepare(player))
    flipped = _grade_frames(ref, _prepare(player, mirrored=True))
    body_frames = max(as_is, flipped, key=lambda fs: _total(fs, "body"))
    face_frames = max(as_is, flipped, key=lambda fs: _total(fs, "face"))
    frames = [_Frame(b.t, b.body, f.face, b.body_err, f.face_err)
              for b, f in zip(body_frames, face_frames, strict=True)]

    scope = sorted({n for r in ref for n in r.measures})
    body_mean, face_mean = _mean(frames, "body", moments), _mean(frames, "face", moments)
    graded = sum(1 for f in frames if f.body is not None)

    if body_mean is None:
        body = CategoryScore(score=UNMEASURABLE_BODY,
                             reason="The scene never shows enough of the body to measure.")
    else:
        best, worst = _extremes(_category_gaps(frames, "body"))
        body = CategoryScore(
            score=round(body_mean),
            reason=f"{len(scope)} posture measures over {graded} frames; "
                   f"closest on {best}, furthest on {worst}.",
        )

    if face_mean is None:
        face_score = CategoryScore(score=0, reason="The character's face was never tracked.")
    else:
        gaps = _category_gaps(frames, "face")
        if gaps:
            best, worst = _extremes(gaps)
            detail = f"closest on {best}, furthest on {worst}"
        else:
            detail = "both faces stayed at rest"
        face_score = CategoryScore(
            score=round(face_mean),
            reason=f"Expression tracked over {sum(f.face is not None for f in frames)} frames; "
                   f"{detail}.",
        )

    notes = _moment_notes(frames, moments)
    ranked = sorted(notes, key=lambda sn: (sn[0], sn[1].t))
    detected = sum(1 for s in player.samples if s.pose or s.face)
    visible = bool(player.samples) and detected / len(player.samples) >= VISIBLE_SHARE

    return ComparisonReport(
        face=face_score,
        body=body,
        voice=CategoryScore(score=0, reason="Voice is scored separately."),
        moments=[n for _, n in notes],
        best_moment=ranked[-1][1] if ranked else None,
        worst_moment=ranked[0][1] if ranked else None,
        player_not_visible=not visible,
        body_measures=len(scope),
    )
