"""FastAPI app: routes + the live event stream.

Route contract is fixed by HANDOFF.md section 9.1. Handlers marked NOT
IMPLEMENTED are scaffolding for their lane (see HANDOFF.md section 13).
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ValidationError
from sse_starlette.sse import EventSourceResponse

from server.config import get_settings
from server.grading import grade
from server.round.pipeline import round_dir, run_round
from server.scene import ScenePack, load_pack, reference_keypoints
from server.schemas import (
    ComparisonReport,
    KeypointTimeline,
    LeaderboardEntry,
    RoundEvent,
    RoundResult,
)
from server.store import db

settings = get_settings()
log = logging.getLogger(__name__)
logging.getLogger("server").setLevel(logging.INFO)
if not logging.getLogger().handlers:
    logging.basicConfig(format="%(levelname)s:     %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    # Unblock any browser still listening on an event stream.
    for round_id, queue in _streams.items():
        with suppress(Exception):
            queue.put_nowait(
                RoundEvent(event="error", round_id=round_id, detail="server shutdown")
            )


app = FastAPI(title="SceneStealer", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[f"http://localhost:{settings.web_port}", f"http://127.0.0.1:{settings.web_port}"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# round_id -> queue of events. In-memory is fine: one laptop, one demo.
_streams: dict[str, asyncio.Queue[RoundEvent]] = defaultdict(asyncio.Queue)
_results: dict[str, RoundResult] = {}
_rounds: dict[str, dict] = {}  # round_id -> {nickname, attempt}
_tasks: set[asyncio.Task] = set()  # keep running pipelines from being GC'd


async def publish(event: RoundEvent) -> None:
    await _streams[event.round_id].put(event)


# Scene media: the isolated character video, cue audio and masks that Scene
# Prep writes into scenes/<scene_id>/. Served straight off disk so the demo
# keeps working with the Wi-Fi off.
app.mount("/media", StaticFiles(directory=settings.scenes_path), name="media")
# Per-round output: side-by-side replay, judge voices, dub. Raw takes are
# deleted after scoring (DELETE_TAKES_AFTER_SCORING).
(settings.data_path / "rounds").mkdir(parents=True, exist_ok=True)
app.mount(
    "/round-media",
    StaticFiles(directory=settings.data_path / "rounds"),
    name="round-media",
)
# Only the public asset folders -- assets/private holds the movie clips.
app.mount("/sfx", StaticFiles(directory=settings.assets_path / "sfx", check_dir=False), name="sfx")
# Keypoint models for in-browser grading: served from our own origin so the
# game grades with the Wi-Fi off (I6), and the SAME files prep uses (R6.4).
app.mount(
    "/models", StaticFiles(directory=settings.assets_path / "models", check_dir=False),
    name="models",
)
app.mount(
    "/judges", StaticFiles(directory=settings.assets_path / "judges", check_dir=False),
    name="judges",
)


@app.get("/health")
def health() -> dict:
    """Which services are configured and reachable. Checked before every demo."""
    missing = settings.missing_keys()
    scene_ok, scene_detail = True, settings.active_scene
    try:
        pack = load_pack()
        scene_detail = f"{pack.scene_id} ({'prepped' if pack.isolated_video else 'config only'})"
    except Exception as exc:  # noqa: BLE001 - health must never raise
        scene_ok, scene_detail = False, str(exc)

    mongo = db.mongo_status()
    services = {
        name: ("missing keys: " + ", ".join(keys) if (keys := missing.get(name)) else "configured")
        for name in ("omni", "openai", "elevenlabs", "baseten")
    }
    services["mongodb"] = str(mongo["detail"])
    mongo_ready = bool(mongo["reachable"]) or settings.force_fallback
    return {
        "ok": not missing and scene_ok and mongo_ready,
        "services": services,
        "mongodb": mongo,
        "scene": {"ok": scene_ok, "active": scene_detail},
        "force_fallback": settings.force_fallback,
    }


@app.get("/scene", response_model=ScenePack)
def scene() -> ScenePack:
    """The active scene pack. The only route that knows which movie is in play."""
    try:
        return load_pack()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/rounds")
def start_round(nickname: str = Form(...), attempt: int = Form(1)) -> dict:
    round_id = uuid.uuid4().hex[:12]
    _streams[round_id] = asyncio.Queue()
    _rounds[round_id] = {"nickname": nickname.strip()[:24] or "anonymous", "attempt": attempt}
    return {"round_id": round_id, "nickname": nickname, "scene_id": settings.active_scene}


async def _judge(round_id: str, take_path, player: KeypointTimeline | None) -> None:
    meta = _rounds[round_id]
    try:
        await run_round(
            round_id, take_path, meta["nickname"], publish,
            remember=lambda result: _results.__setitem__(round_id, result),
            attempt=meta["attempt"],
            player_keypoints=player,
        )
    except Exception as exc:  # noqa: BLE001 - surface every failure to the browser
        log.exception("Round %s failed", round_id)
        await publish(RoundEvent(event="error", round_id=round_id, detail=str(exc)))


@app.post("/rounds/{round_id}/take")
async def upload_take(
    round_id: str,
    take: UploadFile = File(...),
    keypoints: UploadFile | None = File(None),
) -> dict:
    """Upload the recorded take (+ the browser's keypoint timeline), then judge it
    in the background.

    server/round/pipeline.py does grading -> side-by-side -> OMNI voice -> rules
    -> OpenAI -> ElevenLabs, emitting events on /rounds/{id}/events as it goes.
    Without keypoints (the browser couldn't sample), the server extracts them.
    """
    if round_id not in _rounds:
        raise HTTPException(status_code=404, detail="Unknown round -- POST /rounds first")
    suffix = "." + (take.filename or "take.webm").rsplit(".", 1)[-1]
    take_path = round_dir(round_id) / f"take{suffix}"
    take_path.write_bytes(await take.read())
    player = None
    if keypoints is not None:
        try:
            player = KeypointTimeline.model_validate_json(await keypoints.read())
        except ValidationError as exc:
            log.warning("Round %s: unusable browser keypoints, extracting server-side: %s",
                        round_id, exc.errors()[:1])
    task = asyncio.create_task(_judge(round_id, take_path, player))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    return {"round_id": round_id, "status": "judging"}


class GradeRequest(BaseModel):
    player: KeypointTimeline
    reference: KeypointTimeline | None = None  # default: the scene's prepped keypoints
    scene_id: str | None = None


@app.post("/grade/compare", response_model=ComparisonReport)
def grade_compare(req: GradeRequest) -> ComparisonReport:
    """Face + body grading on its own: keypoint timelines in, scores out.

    Same function the round pipeline calls, so the two can't drift. Lets the
    grading lane be driven with curl before any camera exists.
    """
    pack = load_pack(req.scene_id)
    reference = req.reference or reference_keypoints(pack.scene_id)
    if reference is None:
        raise HTTPException(status_code=409, detail=f"Scene '{pack.scene_id}' has no keypoints "
                                                    "yet -- run prep.keyframes")
    return grade(reference, req.player, [m.t for m in pack.key_moments])


@app.get("/rounds/{round_id}/events")
async def round_events(round_id: str) -> EventSourceResponse:
    """Server-Sent Events: judging -> verdict_ready -> dub_ready (or error)."""
    queue = _streams[round_id]

    async def stream():
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=30)
            except TimeoutError:
                yield {"event": "ping", "data": "{}"}
                continue
            yield {"event": event.event, "data": event.model_dump_json()}
            if event.event in ("dub_ready", "error"):
                break

    return EventSourceResponse(stream())


@app.get("/rounds/{round_id}", response_model=RoundResult)
def get_round(round_id: str) -> RoundResult:
    result = _results.get(round_id) or db.load_result(round_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Round not found")
    return result


@app.get("/leaderboard", response_model=list[LeaderboardEntry])
def leaderboard(
    limit: int = Query(default=10, ge=1, le=db.MAX_LEADERBOARD_LIMIT),
    scene_id: str | None = None,
) -> list[LeaderboardEntry]:
    """Best score per nickname, from MongoDB Atlas (local JSON if it is down)."""
    return db.top(limit=limit, scene_id=scene_id)
