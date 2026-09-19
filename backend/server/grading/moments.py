"""Pick the scene's key moments from the reference keypoints.

The largest changes in posture angles and blendshape coefficients are exactly
where the performance turns, which is better than pixel scene-detection (that
fires on cuts and lighting). Moments are spread out so one busy second can't
take them all (R4.7); a short clip gets fewer rather than evenly spaced filler
(R4.8).
"""

from __future__ import annotations

from server.grading import face, pose
from server.grading.score import STABLE_SCOPE_SHARE
from server.schemas import KeypointTimeline

# Change is measured against the sample this far back (default 0.5s).
LOOKBACK_S = 0.5
MIN_MOMENTS, MAX_MOMENTS = 6, 10
# Moments sit at least this far apart (default 0.8s).
MIN_GAP_S = 0.8


def _features(timeline: KeypointTimeline) -> list[tuple[float, dict[str, float]]]:
    """Each detected sample as normalised features, labelled for the judges.

    Pose measures the clip only shows now and then are left out, as in grading:
    a limb flickering in at the frame edge is not a turn in the performance.
    """
    samples = sorted(timeline.samples, key=lambda s: s.t)
    measured = [pose.measure(s.pose, timeline.aspect) for s in samples]
    posed = [m for m in measured if m]
    stable = {n for n in pose.LABELS
              if posed and sum(n in m for m in posed) / len(posed) >= STABLE_SCOPE_SHARE}
    out = []
    for s, m in zip(samples, measured, strict=True):
        feats = {pose.LABELS[n]: v / pose.MAX_ERROR for n, (v, _) in m.items() if n in stable}
        feats.update({face.label(n): v * face.weight(n) / face.MAX_ERROR
                      for n, v in s.face.items() if face.weight(n)})
        if feats:
            out.append((s.t, feats))
    return out


def select(timeline: KeypointTimeline, count: int = 8) -> list[tuple[float, str]]:
    """Up to `count` (t, label) moments, strongest change first, returned in time order."""
    count = max(MIN_MOMENTS, min(MAX_MOMENTS, count))
    feats = _features(timeline)
    candidates: list[tuple[float, float, str]] = []  # (change, t, label)
    j = 0
    for t, now in feats:
        while j < len(feats) and feats[j][0] <= t - LOOKBACK_S:
            j += 1
        if j == 0:
            continue
        _, before = feats[j - 1]
        shared = now.keys() & before.keys()
        if not shared:
            continue
        deltas = {k: now[k] - before[k] for k in shared}
        biggest = max(sorted(deltas), key=lambda k: abs(deltas[k]))
        change = sum(abs(d) for d in deltas.values())
        direction = "rises" if deltas[biggest] > 0 else "drops"
        candidates.append((change, t, f"{biggest} {direction}"))

    chosen: list[tuple[float, str]] = []
    for _, t, label in sorted(candidates, key=lambda c: (-c[0], c[1])):
        if all(abs(t - c) >= MIN_GAP_S for c, _ in chosen):
            chosen.append((round(t, 2), label))
            if len(chosen) == count:
                break
    return sorted(chosen)
