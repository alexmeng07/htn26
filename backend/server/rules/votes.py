"""Pass/fail rules. Plain code on purpose.

If a model decided YES/NO, the same performance could pass one time and fail the
next. Code applies the threshold; the model only writes a reaction that matches
the vote it was handed.
"""

from __future__ import annotations

from server.config import get_settings
from server.scene import ScenePack
from server.schemas import Category, ComparisonReport, JudgeVote, Verdict

GOLDEN_BUZZER_SCORE = 90

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
