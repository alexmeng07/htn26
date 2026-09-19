"""Facial expression from blendshape coefficients, never from landmark positions.

Landmark positions encode face SHAPE: a different jaw would score badly while
making the identical expression. MediaPipe's 52 blendshapes name expressions
directly (brow raise, jaw open, mouth press) and are person-invariant (R6.3).

Only channels active on at least one of the two faces are compared. Most
coefficients sit near zero most of the time, and averaging those in would make
any two faces look alike.
"""

from __future__ import annotations

import re

# Mean coefficient error that maps to a score of 0 (default 0.5, tune in 6.7).
MAX_ERROR = 0.5
# A channel below this on both faces is resting and says nothing (default 0.1, tune in 6.7).
ACTIVE = 0.1

# Expressive channels at full weight; blinks and glances are timing noise, not
# acting (defaults, tune in 6.7). Anything unlisted -- cheeks, nose -- sits between.
WEIGHTS = [("brow", 1.0), ("eyeSquint", 1.0), ("jaw", 1.0), ("mouth", 1.0),
           ("eyeBlink", 0.1), ("eyeLook", 0.1)]
DEFAULT_WEIGHT = 0.5


def weight(channel: str) -> float:
    if channel == "_neutral":
        return 0.0
    for prefix, w in WEIGHTS:
        if channel.startswith(prefix):
            return w
    return DEFAULT_WEIGHT


def label(channel: str) -> str:
    """`browInnerUp` -> `brow inner up`."""
    return re.sub(r"(?<!^)(?=[A-Z])", " ", channel).lower()


def frame_errors(ref: dict[str, float], player: dict[str, float]) -> dict[str, float]:
    """Absolute error per active channel. A player with no face detected gets none."""
    return {
        name: abs(value - player.get(name, 0.0))
        for name, value in ref.items()
        if weight(name) > 0 and max(value, player.get(name, 0.0)) >= ACTIVE
    }


def frame_score(errors: dict[str, float]) -> float:
    """Weighted mean error, mapped linearly onto 0..100. Both at rest is a match."""
    total = sum(weight(name) for name in errors)
    if not total:
        return 100.0
    error = sum(err * weight(name) for name, err in errors.items()) / total
    return max(0.0, min(100.0, 100.0 * (1.0 - error / MAX_ERROR)))
