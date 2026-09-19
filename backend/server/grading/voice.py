"""Local voice estimate, for when the multimodal model is slow, down or forced off.

Compares loudness envelopes: does the player speak when the character speaks,
about as much, with about as much light and shade? Crude next to a model that
listens, but deterministic, network-free, and different for every take -- a
fixed fallback number would make every offline round identical (R15.2).
"""

from __future__ import annotations

import statistics

from server.schemas import CategoryScore

# Envelope hop, seconds. Levels arrive as one dBFS value per hop.
HOP_S = 0.05
# Quieter than this is silence regardless (matches rules/votes.SILENCE_DB).
SILENCE_DB = -45.0
# Voiced means within this many dB of the take's own loud end (default 25).
DYNAMIC_RANGE_DB = 25.0
# Timing tolerance, same idea as grading.score.WINDOW_S.
WINDOW_S = 0.25
# Share of the score from timing, amount of speech, and dynamics.
W_TIMING, W_AMOUNT, W_DYNAMICS = 0.6, 0.2, 0.2


def voiced(levels: list[float]) -> list[bool]:
    """Per-hop voice activity, relative to the recording's own loud end."""
    finite = sorted(v for v in levels if v > float("-inf"))
    if not finite:
        return [False] * len(levels)
    loud = finite[int(0.95 * (len(finite) - 1))]
    floor = max(SILENCE_DB, loud - DYNAMIC_RANGE_DB)
    return [v > floor for v in levels]


def _near(flags: list[bool], i: int, reach: int) -> bool:
    return any(flags[max(0, i - reach): i + reach + 1])


def estimate(reference_db: list[float], player_db: list[float]) -> CategoryScore:
    ref, ply = voiced(reference_db), voiced(player_db)
    n = min(len(ref), len(ply))
    if not n or not any(ply[:n]):
        return CategoryScore(score=0, reason="No voice picked up on the take.")
    ref, ply = ref[:n], ply[:n]
    reach = round(WINDOW_S / HOP_S)

    spoken = [i for i in range(n) if ref[i]]
    quiet = [i for i in range(n) if not ref[i]]
    hit = sum(_near(ply, i, reach) for i in spoken) / len(spoken) if spoken else 1.0
    hush = sum(not ply[i] for i in quiet) / len(quiet) if quiet else 1.0
    timing = (hit + hush) / 2

    ref_share, ply_share = sum(ref) / n, sum(ply) / n
    amount = 1.0 - min(1.0, abs(ref_share - ply_share) / max(ref_share, 0.2))

    ref_spread = _spread(reference_db[:n], ref)
    ply_spread = _spread(player_db[:n], ply)
    dynamics = 1.0 - min(1.0, abs(ref_spread - ply_spread) / max(ref_spread, 3.0))

    score = round(100 * (W_TIMING * timing + W_AMOUNT * amount + W_DYNAMICS * dynamics))
    return CategoryScore(
        score=max(0, min(100, score)),
        reason=(f"Measured from loudness alone: spoke on {hit:.0%} of the character's beats, "
                f"held back on {hush:.0%} of the pauses."),
    )


def _spread(levels: list[float], flags: list[bool]) -> float:
    loud = [v for v, f in zip(levels, flags, strict=True) if f]
    return statistics.pstdev(loud) if len(loud) > 1 else 0.0
