"""Every JSON shape in the system, defined once (Pydantic v2).

AI replies are validated against these before anything downstream touches them.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

Category = Literal["face", "body", "voice"]
Vote = Literal["YES", "NO"]


# ---------------------------------------------------------------- OMNI output
class CategoryScore(BaseModel):
    score: int = Field(ge=0, le=100)
    reason: str


class MomentNote(BaseModel):
    t: float
    matched: str = ""
    missed: str = ""


class ComparisonReport(BaseModel):
    """What OMNI returns after watching the side-by-side video."""

    face: CategoryScore
    body: CategoryScore
    voice: CategoryScore
    moments: list[MomentNote] = Field(default_factory=list)
    best_moment: MomentNote | None = None
    worst_moment: MomentNote | None = None
    player_not_visible: bool = False
    player_silent: bool = False
    # How many posture measures the reference's visible region supported. A
    # head-and-shoulders close-up yields a handful; a thin round is shown, not hidden.
    body_measures: int = 0

    def score(self, category: Category) -> CategoryScore:
        return getattr(self, category)


# ------------------------------------------------------- keypoint timelines
class PoseLandmark(BaseModel):
    """One MediaPipe pose landmark, x/y normalised to the frame, as the model emits it."""

    x: float
    y: float
    z: float = 0.0
    visibility: float = 0.0


class KeypointSample(BaseModel):
    """What the landmarkers saw at one instant. Empty means no person detected."""

    t: float  # seconds since the take (or trimmed clip) started
    pose: list[PoseLandmark] = Field(default_factory=list)  # 33 points, or none
    face: dict[str, float] = Field(default_factory=dict)  # blendshape name -> 0..1


class KeypointTimeline(BaseModel):
    """Per-frame pose and expression for one performer. Same shape both sides."""

    fps: float = 0.0
    # width / height of the frames the landmarks were normalised against. Angles
    # need it: x and y are fractions of different pixel lengths.
    aspect: float = 16 / 9
    samples: list[KeypointSample] = Field(default_factory=list)


# --------------------------------------------------------------- vote (code)
class JudgeVote(BaseModel):
    """Decided by plain code, never by a model -- same performance, same result."""

    judge_id: str
    category: Category
    score: int
    threshold: int
    vote: Vote


class Verdict(BaseModel):
    votes: list[JudgeVote]
    passed: bool
    golden_buzzer: bool = False
    combined: int = 0


# ------------------------------------------------------------ OpenAI output
class JudgeLine(BaseModel):
    """One judge's written reaction. Must agree with the vote it was given."""

    judge_id: str
    spoken: str  # under ~2 sentences, read aloud by ElevenLabs
    bubble: str  # slightly longer speech-bubble text
    tip: str  # coaching line, shown on the retry screen when the vote is NO


class JudgeLines(BaseModel):
    lines: list[JudgeLine]


# ------------------------------------------------------------- round result
class JudgeResult(BaseModel):
    judge_id: str
    name: str
    category: Category
    vote: Vote
    score: int
    spoken: str
    bubble: str
    tip: str
    audio_url: str | None = None


class JudgeStub(BaseModel):
    """A judge who hasn't spoken yet: enough to put them on stage, waiting."""

    judge_id: str
    name: str
    category: Category


class RoundResult(BaseModel):
    round_id: str
    nickname: str
    attempt: int = 1
    scene_id: str
    face: int = 0
    body: int = 0
    voice: int = 0
    combined: int = 0
    judges: list[JudgeResult] = Field(default_factory=list)
    best_moment: MomentNote | None = None
    worst_moment: MomentNote | None = None
    passed: bool = False
    golden_buzzer: bool = False
    dub_url: str | None = None
    # The player's skeleton on the replay (the character's is the scene's
    # overlay.json). None when the replay fell back to the side-by-side.
    replay_overlay: str | None = None
    # Loudness envelopes of the original clip and the player's raw microphone,
    # for the replay's side-by-side waveform. None if either had no audio.
    waveforms: str | None = None
    fallback_used: bool = False  # UI shows "judges on a coffee break"
    # False while the voice judge is still listening: face and body are decided
    # and can be revealed; `pending` lists who is still to come. Final results
    # (and every stored result) are complete.
    complete: bool = True
    pending: list[JudgeStub] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class LeaderboardEntry(BaseModel):
    nickname: str
    combined: int
    scene_id: str
    passed: bool
    created_at: datetime


# ------------------------------------------------------------- SSE events
# partial_ready: face and body judged and voiced, voice still scoring.
EventName = Literal["judging", "partial_ready", "verdict_ready", "dub_ready", "error"]


class RoundEvent(BaseModel):
    event: EventName
    round_id: str
    detail: str = ""
