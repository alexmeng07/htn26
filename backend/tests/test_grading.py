"""Grading is a pure function over two keypoint timelines, tested with no media.

Every timeline here is built by hand from a stick figure, so the tests need no
video file, no camera, no credentials and no network (R3.4, D1 tier 2).
"""

from __future__ import annotations

import math
import time

from server.grading import grade, moments, pose, voice
from server.grading.score import WINDOW_S
from server.schemas import KeypointSample, KeypointTimeline, PoseLandmark

ASPECT = 16 / 9
FPS = 15.0

# A stick figure in body units: y points down, the person's LEFT is image +x.
_CANON = {
    0: (0.0, -1.6), 1: (0.05, -1.68), 2: (0.08, -1.68), 3: (0.11, -1.68),
    4: (-0.05, -1.68), 5: (-0.08, -1.68), 6: (-0.11, -1.68), 7: (0.18, -1.62),
    8: (-0.18, -1.62), 9: (0.05, -1.5), 10: (-0.05, -1.5), 11: (0.4, -1.2),
    12: (-0.4, -1.2), 13: (0.5, -0.7), 14: (-0.5, -0.7), 15: (0.55, -0.25),
    16: (-0.55, -0.25), 17: (0.57, -0.2), 18: (-0.57, -0.2), 19: (0.56, -0.18),
    20: (-0.56, -0.18), 21: (0.54, -0.22), 22: (-0.54, -0.22), 23: (0.2, 0.0),
    24: (-0.2, 0.0), 25: (0.22, 0.6), 26: (-0.22, 0.6), 27: (0.22, 1.2),
    28: (-0.22, 1.2), 29: (0.2, 1.25), 30: (-0.2, 1.25), 31: (0.3, 1.28), 32: (-0.3, 1.28),
}
HEAD = range(0, 11)
LEFT_ARM = (13, 15, 17, 19, 21)
UPPER = range(0, 23)
HEAD_AND_SHOULDERS = set(range(0, 13))


def _rotate(p, centre, degrees):
    a = math.radians(degrees)
    x, y = p[0] - centre[0], p[1] - centre[1]
    return (centre[0] + x * math.cos(a) - y * math.sin(a),
            centre[1] + x * math.sin(a) + y * math.cos(a))


def figure(head_tilt=0.0, arm_raise=0.0, lean=0.0, *, cx=0.5, cy=0.7, scale=0.2,
           visible=None) -> list[PoseLandmark]:
    """33 landmarks for a posed stick figure centred on (cx, cy), height ~3*scale."""
    pts = dict(_CANON)
    for i in HEAD:
        pts[i] = _rotate(pts[i], (0.0, -1.2), head_tilt)
    for i in LEFT_ARM:
        pts[i] = _rotate(pts[i], pts[11], -arm_raise)
    for i in UPPER:
        pts[i] = _rotate(pts[i], (0.0, 0.0), lean)
    return [
        PoseLandmark(x=cx + pts[i][0] * scale / ASPECT, y=cy + pts[i][1] * scale, z=0.0,
                     visibility=0.99 if visible is None or i in visible else 0.05)
        for i in range(33)
    ]


def timeline(poses, faces=None, *, dt=1 / FPS, offset=0.0) -> KeypointTimeline:
    faces = faces or [{}] * len(poses)
    return KeypointTimeline(fps=1 / dt, aspect=ASPECT, samples=[
        KeypointSample(t=round(offset + i * dt, 4), pose=p, face=f)
        for i, (p, f) in enumerate(zip(poses, faces, strict=True))
    ])


def performance(n=150, **kw) -> list[list[PoseLandmark]]:
    """A 10 s performance: head sways, left arm rises and falls."""
    return [figure(head_tilt=20 * math.sin(i / 12), arm_raise=60 * (1 - math.cos(i / 20)), **kw)
            for i in range(n)]


SMILE = {"mouthSmileLeft": 0.8, "mouthSmileRight": 0.7, "cheekSquintLeft": 0.4, "_neutral": 0.1}
FROWN = {"browDownLeft": 0.7, "browDownRight": 0.7, "mouthFrownLeft": 0.6, "mouthPressLeft": 0.5}


# ------------------------------------------------------------------- pose
def test_identical_scores_100():
    ref = timeline(performance())
    report = grade(ref, ref)
    assert report.body.score == 100
    assert not report.player_not_visible


def test_scaled_and_shifted_player_scores_like_the_original():
    ref = timeline(performance())
    far_away = timeline(performance(cx=0.3, cy=0.5, scale=0.08))
    assert grade(ref, far_away).body.score == grade(ref, ref).body.score


def test_mirror_image_scores_like_the_original():
    ref = timeline(performance())
    mirrored = KeypointTimeline(aspect=ASPECT, samples=[pose.mirror(s) for s in ref.samples])
    assert grade(ref, mirrored).body.score >= 99


def test_unrelated_pose_scores_low():
    # Upper body only, so unchanged legs don't dilute the difference; and no
    # left/right-symmetric difference, since grading forgives a mirror image.
    upper = set(UPPER)
    ref = timeline([figure(head_tilt=35, arm_raise=140, lean=20, visible=upper)] * 60)
    close = timeline([figure(head_tilt=30, arm_raise=130, lean=17, visible=upper)] * 60)
    other = timeline([figure(visible=upper)] * 60)
    near, far = grade(ref, close).body.score, grade(ref, other).body.score
    assert near >= 90
    assert far <= near - 15
    assert grade(ref, ref).body.score == 100


def test_small_time_shift_is_forgiven_large_is_not():
    ref = timeline(performance())
    late = timeline(performance(), offset=WINDOW_S * 0.8)
    very_late = timeline(performance(), offset=1.5)
    near, far = grade(ref, late).body.score, grade(ref, very_late).body.score
    assert near >= 95
    assert far < near


def test_close_up_reference_grades_head_and_shoulders_only():
    ref = timeline(performance(visible=HEAD_AND_SHOULDERS))
    report = grade(ref, timeline(performance(visible=HEAD_AND_SHOULDERS)))
    assert report.body_measures == 7
    assert report.body.score == 100


def test_extra_visible_parts_neither_help_nor_hurt():
    ref = timeline(performance(visible=HEAD_AND_SHOULDERS))
    partial = timeline([figure(head_tilt=10, visible=HEAD_AND_SHOULDERS)] * 150)
    whole = timeline([figure(head_tilt=10)] * 150)
    assert grade(ref, partial).body.score == grade(ref, whole).body.score


def test_leaving_frame_never_beats_staying_in_it():
    ref = timeline(performance())
    off_pose = [figure(head_tilt=-25, arm_raise=10)] * 150
    stayed = grade(ref, timeline(off_pose)).body.score
    # Alternate frames still fall inside the +-250 ms window, so leave for whole seconds.
    gone = [figure(visible=set()) if (i // 15) % 2 else p for i, p in enumerate(off_pose)]
    empty = [[] if (i // 15) % 2 else p for i, p in enumerate(off_pose)]
    assert grade(ref, timeline(gone)).body.score < stayed
    assert grade(ref, timeline(empty)).body.score < stayed


def test_a_limb_that_only_flickers_into_frame_is_not_graded():
    arm = HEAD_AND_SHOULDERS | {13, 15, 17, 19, 21, 23}  # elbow chain + hip for elbow/arm
    poses = [figure(visible=arm if i % 5 == 0 else HEAD_AND_SHOULDERS) for i in range(150)]
    report = grade(timeline(poses), timeline([figure()] * 150))
    assert report.body_measures == 7
    assert "elbow" not in report.body.reason


def test_character_off_screen_frames_are_excluded_not_zero():
    poses = performance()
    with_cutaway = [[] if 50 <= i < 80 else p for i, p in enumerate(poses)]
    assert grade(timeline(with_cutaway), timeline(poses)).body.score == 100


def test_empty_inputs_do_not_crash():
    report = grade(timeline(performance()), KeypointTimeline())
    assert report.player_not_visible
    assert report.body.score == 0
    blank = grade(KeypointTimeline(), KeypointTimeline())
    assert blank.body_measures == 0


# ------------------------------------------------------------------- face
def test_same_expression_scores_100_different_scores_low():
    ref = timeline([figure()] * 30, [SMILE] * 30)
    assert grade(ref, timeline([figure()] * 30, [SMILE] * 30)).face.score == 100
    assert grade(ref, timeline([figure()] * 30, [FROWN] * 30)).face.score < 30


def test_a_blink_barely_matters():
    ref = timeline([figure()] * 30, [SMILE] * 30)
    blink = {**SMILE, "eyeBlinkLeft": 0.9, "eyeBlinkRight": 0.9}
    blinking = timeline([figure()] * 30, [blink] * 30)
    assert grade(ref, blinking).face.score >= 90


def test_no_face_on_the_player_scores_zero():
    ref = timeline([figure()] * 30, [SMILE] * 30)
    assert grade(ref, timeline([figure()] * 30)).face.score == 0


# ------------------------------------------------------ report and determinism
def test_best_and_worst_moment_follow_the_performance():
    poses = [figure(arm_raise=90)] * 150
    player = [figure(arm_raise=90) if i < 75 else figure(arm_raise=0) for i in range(150)]
    report = grade(timeline(poses), timeline(player), key_moments=[2.0, 8.0])
    assert report.best_moment.t == 2.0
    assert report.worst_moment.t == 8.0
    assert "arm" in report.worst_moment.missed


def test_same_take_same_scores_every_time_and_fast():
    ref = timeline(performance(n=156), [SMILE] * 156)
    player = timeline(performance(n=156, cx=0.4, scale=0.15), [FROWN] * 156)
    started = time.perf_counter()
    runs = {grade(ref, player, key_moments=[1.0, 4.0, 9.0]).model_dump_json() for _ in range(5)}
    elapsed = (time.perf_counter() - started) / 5
    assert len(runs) == 1
    assert elapsed < 1.0, f"grading a 10.4s take took {elapsed:.2f}s"


# ------------------------------------------------------------ key moments
def test_key_moments_land_on_the_changes():
    poses = [figure(arm_raise=0 if i < 30 else 90 if i < 75 else 20 if i < 120 else 120)
             for i in range(150)]
    picked = [t for t, _ in moments.select(timeline(poses), count=6)]
    for change in (2.0, 5.0, 8.0):
        assert any(abs(t - change) <= 0.6 for t in picked), (change, picked)
    assert all(b - a >= moments.MIN_GAP_S for a, b in zip(picked, picked[1:], strict=False))


def test_short_clip_gets_fewer_moments_not_filler():
    poses = [figure(arm_raise=i * 5) for i in range(30)]  # 2 s
    picked = moments.select(timeline(poses), count=8)
    assert 0 < len(picked) < 6


# ------------------------------------------------------------------ voice
def _envelope(pattern: str) -> list[float]:
    """'#' is speech, '.' silence, one char per 0.25 s."""
    per = round(0.25 / voice.HOP_S)
    return [(-20.0 + (i % 3)) if c == "#" else -70.0 for c in pattern for i in range(per)]


def test_voice_estimate_rewards_matching_timing():
    ref = _envelope("..####....###...####..")
    assert voice.estimate(ref, ref).score >= 90
    assert voice.estimate(ref, _envelope("##....####...###....##")).score < 60


def test_voice_estimate_silent_player_scores_zero():
    assert voice.estimate(_envelope("..####.."), [-90.0] * 40).score == 0


# ------------------------------------------------------------------ route
def test_grade_compare_route_matches_the_function():
    from fastapi.testclient import TestClient

    from server.main import app
    from server.scene import load_pack

    ref, player = timeline(performance(n=30)), timeline([figure(arm_raise=0)] * 30)
    res = TestClient(app).post("/grade/compare", json={
        "reference": ref.model_dump(), "player": player.model_dump(),
    })
    assert res.status_code == 200
    expected = grade(ref, player, [m.t for m in load_pack().key_moments])
    assert res.json()["body"]["score"] == expected.body.score
