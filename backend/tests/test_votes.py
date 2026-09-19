"""The vote is plain code, so it is fully testable: same scores, same result."""

from server.rules.votes import GOLDEN_BUZZER_SCORE, tally, threshold_for
from server.scene import ScenePack
from server.schemas import CategoryScore, ComparisonReport


def pack(face: int = 70, body: int = 60, voice: int = 70) -> ScenePack:
    return ScenePack(
        scene_id="t",
        movie_title="T",
        character_name="C",
        actor_name="A",
        clip_file="x.mp4",
        start="00:00:00",
        end="00:00:20",
        briefing="b",
        tip="t",
        title_line="l",
        thresholds={"face": face, "body": body, "voice": voice},
    )


def report(face: int, body: int, voice: int) -> ComparisonReport:
    return ComparisonReport(
        face=CategoryScore(score=face, reason="f"),
        body=CategoryScore(score=body, reason="b"),
        voice=CategoryScore(score=voice, reason="v"),
    )


def test_all_three_above_threshold_passes():
    verdict = tally(report(80, 70, 75), pack())
    assert verdict.passed
    assert [v.vote for v in verdict.votes] == ["YES", "YES", "YES"]


def test_one_below_threshold_fails():
    verdict = tally(report(80, 59, 75), pack())
    assert not verdict.passed
    assert next(v for v in verdict.votes if v.category == "body").vote == "NO"


def test_score_exactly_at_threshold_is_a_yes():
    verdict = tally(report(70, 60, 70), pack())
    assert verdict.passed


def test_thresholds_come_from_the_scene_not_the_code():
    """A scene with a lower body threshold passes a take the strict scene fails."""
    take = report(80, 55, 75)
    assert not tally(take, pack(body=60)).passed
    assert tally(take, pack(body=50)).passed


def test_golden_buzzer_needs_every_category_very_high():
    high = GOLDEN_BUZZER_SCORE
    assert tally(report(high, high, high), pack()).golden_buzzer
    assert not tally(report(high, high - 1, high), pack()).golden_buzzer


def test_combined_score_is_the_mean():
    assert tally(report(90, 60, 75), pack()).combined == 75


def test_threshold_falls_back_to_the_global_default():
    bare = pack()
    bare.thresholds.face = 0
    assert threshold_for(bare, "face") == 70
