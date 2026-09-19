"""Pass/fail rules. Plain code on purpose.

If a model decided YES/NO, the same performance could pass one time and fail the
next. Code applies the threshold; the model only writes a reaction that matches
the vote it was handed.
"""

from __future__ import annotations

from server.config import get_settings
from server.scene import ScenePack
from server.schemas import Category, CategoryScore, ComparisonReport, JudgeVote, Verdict

GOLDEN_BUZZER_SCORE = 90

# Quieter than this (mean dBFS over the take) counts as not speaking at all.
SILENCE_DB = -45.0
SILENT_VOICE_CAP = 10

# judge_id -> category. Judge display names and personas live in
# assets/judges/<judge_id>/judge.json, not here.
JUDGE_CATEGORIES: dict[str, Category] = {
    "face": "face",
    "body": "body",
    "voice": "voice",
}


def threshold_for(pack: ScenePack, category: Category) -> int:
    """Scene pack wins; DEFAULT_THRESHOLD only fills gaps."""
    value = getattr(pack.thresholds, category, None)
    return value if value else get_settings().default_threshold


def apply_measurements(report: ComparisonReport, mean_volume_db: float | None) -> ComparisonReport:
    """Overrule the model on facts code can measure itself.

    OMNI will describe speech in a silent video, so silence is measured from the
    take's audio track and caps the voice score.
    """
    if mean_volume_db is not None and mean_volume_db >= SILENCE_DB:
        return report
    voice = CategoryScore(
        score=min(report.voice.score, SILENT_VOICE_CAP),
        reason="No voice was picked up on the take.",
    )
    return report.model_copy(update={"voice": voice, "player_silent": True})


def tally(report: ComparisonReport, pack: ScenePack) -> Verdict:
    votes: list[JudgeVote] = []
    for judge_id, category in JUDGE_CATEGORIES.items():
        entry = report.score(category)
        threshold = threshold_for(pack, category)
        votes.append(
            JudgeVote(
                judge_id=judge_id,
                category=category,
                score=entry.score,
                threshold=threshold,
                vote="YES" if entry.score >= threshold else "NO",
            )
        )

    scores = [v.score for v in votes]
    return Verdict(
        votes=votes,
        passed=all(v.vote == "YES" for v in votes),
        golden_buzzer=all(s >= GOLDEN_BUZZER_SCORE for s in scores),
        combined=round(sum(scores) / len(scores)),
    )
