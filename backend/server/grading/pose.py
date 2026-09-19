"""Body posture as angles, so position in frame, distance and build drop out.

Raw landmark coordinates say where someone stood and how tall they are, not
what they did. Every measure here is an angle, or a ratio turned into an angle,
between points of the same person -- translation- and scale-invariant by
construction, with no normalisation step to get wrong (R6.2).

The REFERENCE decides which measures count in a frame (R6.7): a measure is in
scope when every landmark it needs is visible in the reference. A player who
shows more of themselves gains nothing; a player who leaves frame scores the
missing measures as full misses, so stepping out of shot can never help.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from server.schemas import KeypointSample, PoseLandmark

# A landmark counts as seen above this visibility (default 0.5, tune in 6.7).
VISIBILITY_THRESHOLD = 0.5
# Mean angular error that maps to a score of 0 (default 60 degrees, tune in 6.7).
MAX_ERROR = 60.0

# MediaPipe Pose landmark indices.
NOSE, L_EYE, R_EYE, L_EAR, R_EAR = 0, 2, 5, 7, 8
L_SHOULDER, R_SHOULDER, L_ELBOW, R_ELBOW, L_WRIST, R_WRIST = 11, 12, 13, 14, 15, 16
L_HIP, R_HIP, L_KNEE, R_KNEE, L_ANKLE, R_ANKLE = 23, 24, 25, 26, 27, 28

# Left/right pairs, for mirroring a selfie-camera player onto the reference.
MIRROR_PAIRS = [(1, 4), (2, 5), (3, 6), (7, 8), (9, 10), (11, 12), (13, 14), (15, 16),
                (17, 18), (19, 20), (21, 22), (23, 24), (25, 26), (27, 28), (29, 30), (31, 32)]

Point = tuple[float, float, float]  # x, y, z in frame-height units; y points down


def _mid(a: Point, b: Point) -> Point:
    return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, (a[2] + b[2]) / 2)


def _dist2d(a: Point, b: Point) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _tilt(a: Point, b: Point) -> float:
    """Angle of the line a->b against horizontal, degrees."""
    return math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))


def _from_vertical(bottom: Point, top: Point) -> float:
    """Lean of bottom->top away from straight up, degrees (positive = toward +x)."""
    return math.degrees(math.atan2(top[0] - bottom[0], bottom[1] - top[1]))


def _joint(a: Point, b: Point, c: Point) -> float:
    """Interior angle at b, degrees, 0..180."""
    v1 = (a[0] - b[0], a[1] - b[1])
    v2 = (c[0] - b[0], c[1] - b[1])
    n1, n2 = math.hypot(*v1), math.hypot(*v2)
    if n1 == 0 or n2 == 0:
        return 0.0
    cos = (v1[0] * v2[0] + v1[1] * v2[1]) / (n1 * n2)
    return math.degrees(math.acos(max(-1.0, min(1.0, cos))))


def _ratio_angle(num: float, den: float) -> float:
    """A ratio expressed in degrees so it shares MAX_ERROR with the true angles."""
    return math.degrees(math.atan2(num, den)) if den > 0 else 0.0


def _head_yaw(p: dict[int, Point]) -> float:
    ears = _mid(p[L_EAR], p[R_EAR])
    half_span = _dist2d(p[L_EAR], p[R_EAR]) / 2
    if half_span == 0:
        return 0.0
    return math.degrees(math.asin(max(-1.0, min(1.0, (p[NOSE][0] - ears[0]) / half_span))))


def _head_pitch(p: dict[int, Point]) -> float:
    ears = _mid(p[L_EAR], p[R_EAR])
    return _ratio_angle(p[NOSE][1] - ears[1], _dist2d(p[L_EAR], p[R_EAR]))


def _shrug(p: dict[int, Point]) -> float:
    shoulders = _mid(p[L_SHOULDER], p[R_SHOULDER])
    return _ratio_angle(_dist2d(p[NOSE], shoulders), _dist2d(p[L_SHOULDER], p[R_SHOULDER]))


def _head_forward(p: dict[int, Point]) -> float:
    shoulders = _mid(p[L_SHOULDER], p[R_SHOULDER])
    return _ratio_angle(shoulders[2] - p[NOSE][2], _dist2d(p[L_SHOULDER], p[R_SHOULDER]))


@dataclass(frozen=True)
class Measure:
    name: str
    label: str  # what a judge would call it
    landmarks: tuple[int, ...]
    fn: Callable[[dict[int, Point]], float]


MEASURES: list[Measure] = [
    # Head and shoulders: what a close-up still supports.
    Measure("shoulder_roll", "shoulder tilt", (L_SHOULDER, R_SHOULDER),
            lambda p: _tilt(p[R_SHOULDER], p[L_SHOULDER])),
    Measure("head_roll", "head tilt", (L_EYE, R_EYE), lambda p: _tilt(p[R_EYE], p[L_EYE])),
    Measure("head_yaw", "head turn", (NOSE, L_EAR, R_EAR), _head_yaw),
    Measure("head_pitch", "chin up or down", (NOSE, L_EAR, R_EAR), _head_pitch),
    Measure("neck_tilt", "neck lean", (L_EAR, R_EAR, L_SHOULDER, R_SHOULDER),
            lambda p: _from_vertical(_mid(p[L_SHOULDER], p[R_SHOULDER]), _mid(p[L_EAR], p[R_EAR]))),
    Measure("shrug", "shrug", (NOSE, L_SHOULDER, R_SHOULDER), _shrug),
    Measure("head_forward", "head forward or back", (NOSE, L_SHOULDER, R_SHOULDER), _head_forward),
    # Torso and limbs: only when the reference shows them.
    Measure("torso_lean", "torso lean", (L_SHOULDER, R_SHOULDER, L_HIP, R_HIP),
            lambda p: _from_vertical(_mid(p[L_HIP], p[R_HIP]), _mid(p[L_SHOULDER], p[R_SHOULDER]))),
    Measure("elbow_l", "left elbow", (L_SHOULDER, L_ELBOW, L_WRIST),
            lambda p: _joint(p[L_SHOULDER], p[L_ELBOW], p[L_WRIST])),
    Measure("elbow_r", "right elbow", (R_SHOULDER, R_ELBOW, R_WRIST),
            lambda p: _joint(p[R_SHOULDER], p[R_ELBOW], p[R_WRIST])),
    Measure("shoulder_l", "left arm raise", (L_ELBOW, L_SHOULDER, L_HIP),
            lambda p: _joint(p[L_ELBOW], p[L_SHOULDER], p[L_HIP])),
    Measure("shoulder_r", "right arm raise", (R_ELBOW, R_SHOULDER, R_HIP),
            lambda p: _joint(p[R_ELBOW], p[R_SHOULDER], p[R_HIP])),
    Measure("hip_l", "left hip bend", (L_SHOULDER, L_HIP, L_KNEE),
            lambda p: _joint(p[L_SHOULDER], p[L_HIP], p[L_KNEE])),
    Measure("hip_r", "right hip bend", (R_SHOULDER, R_HIP, R_KNEE),
            lambda p: _joint(p[R_SHOULDER], p[R_HIP], p[R_KNEE])),
    Measure("knee_l", "left knee", (L_HIP, L_KNEE, L_ANKLE),
            lambda p: _joint(p[L_HIP], p[L_KNEE], p[L_ANKLE])),
    Measure("knee_r", "right knee", (R_HIP, R_KNEE, R_ANKLE),
            lambda p: _joint(p[R_HIP], p[R_KNEE], p[R_ANKLE])),
]
LABELS = {m.name: m.label for m in MEASURES}

# name -> (value in degrees, confidence = min visibility of its landmarks)
Measured = dict[str, tuple[float, float]]


def measure(pose: Sequence[PoseLandmark], aspect: float) -> Measured:
    """Every measure whose landmarks are all visible in this pose."""
    if len(pose) < 33:
        return {}
    points = {i: (lm.x * aspect, lm.y, lm.z * aspect) for i, lm in enumerate(pose)}
    out: Measured = {}
    for m in MEASURES:
        conf = min(pose[i].visibility for i in m.landmarks)
        if conf >= VISIBILITY_THRESHOLD:
            out[m.name] = (m.fn(points), conf)
    return out


def mirror(sample: KeypointSample) -> KeypointSample:
    """Flip a sample left-right, as if the performer faced a mirror.

    Players copy what they see, and the live preview is mirrored, so the natural
    imitation is the mirror image. Grading tries both and keeps the better.
    """
    pose = [lm.model_copy(update={"x": 1.0 - lm.x}) for lm in sample.pose]
    if pose:
        for a, b in MIRROR_PAIRS:
            pose[a], pose[b] = pose[b], pose[a]
    face = {_swap_side(k): v for k, v in sample.face.items()}
    return KeypointSample(t=sample.t, pose=pose, face=face)


def _swap_side(name: str) -> str:
    if name.endswith("Left"):
        return name[:-4] + "Right"
    if name.endswith("Right"):
        return name[:-5] + "Left"
    return name


def angle_diff(a: float, b: float) -> float:
    """Absolute difference between two angles, wrapped into 0..180."""
    d = abs(a - b) % 360.0
    return 360.0 - d if d > 180.0 else d


def frame_errors(ref: Measured, player: Measured) -> dict[str, float]:
    """Per-measure error over the reference's scope. Missing on the player = full miss."""
    return {
        name: min(angle_diff(value, player[name][0]), MAX_ERROR) if name in player else MAX_ERROR
        for name, (value, _) in ref.items()
    }


def frame_score(ref: Measured, errors: dict[str, float]) -> float:
    """Confidence-weighted mean error, mapped linearly onto 0..100."""
    total = sum(conf for _, conf in ref.values())
    if not total:
        return 0.0
    error = sum(errors[name] * conf for name, (_, conf) in ref.items()) / total
    return max(0.0, min(100.0, 100.0 * (1.0 - error / MAX_ERROR)))
