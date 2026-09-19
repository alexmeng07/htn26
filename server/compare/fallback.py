"""Backup scorer for when OMNI is slow (>~8s) or down.

Scores from in-browser MediaPipe face/pose data plus loudness and voice-activity
checks, compared against the scene pack's reference. Rough, but the judges still
run and the demo never dies.
"""

from __future__ import annotations

from server.scene import ScenePack
from server.schemas import CategoryScore, ComparisonReport


def score_from_client_signals(signals: dict, pack: ScenePack) -> ComparisonReport:
    """Lane C: turn MediaPipe landmarks + audio levels into rough 0-100 scores."""
    raise NotImplementedError("Lane C: fallback scorer not implemented yet")


def neutral_report(reason: str = "fallback") -> ComparisonReport:
    """Last resort: mid-band scores so the show goes on."""
    mid = CategoryScore(score=65, reason=reason)
    return ComparisonReport(face=mid, body=mid, voice=mid)
