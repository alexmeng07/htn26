"""FastAPI app: routes + the live event stream.

Route contract is fixed by HANDOFF.md section 9.1. Handlers marked NOT
IMPLEMENTED are scaffolding for their lane (see HANDOFF.md section 13).
"""

from __future__ import annotations

import asyncio
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from server.config import get_settings
from server.scene import ScenePack, load_pack
from server.schemas import RoundEvent, RoundResult

settings = get_settings()


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


async def publish(event: RoundEvent) -> None:
    await _streams[event.round_id].put(event)


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

    services = {
        name: ("missing keys: " + ", ".join(keys) if (keys := missing.get(name)) else "configured")
        for name in ("omni", "openai", "elevenlabs", "baseten", "mongodb")
    }
    return {
        "ok": not missing and scene_ok,
        "services": services,
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
def start_round(nickname: str = Form(...)) -> dict:
    round_id = uuid.uuid4().hex[:12]
    _streams[round_id] = asyncio.Queue()
    return {"round_id": round_id, "nickname": nickname, "scene_id": settings.active_scene}


@app.post("/rounds/{round_id}/take")
async def upload_take(round_id: str, take: UploadFile = File(...)) -> dict:
    """Upload the recorded take, then kick off judging in the background.

    Lane E (server/round/) owns the pipeline: side-by-side -> OMNI -> rules ->
    OpenAI -> ElevenLabs, emitting events on /rounds/{id}/events as it goes.
    """
    raise HTTPException(status_code=501, detail="Lane E: round pipeline not implemented yet")


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
    if round_id not in _results:
        raise HTTPException(status_code=404, detail="Round not found")
    return _results[round_id]


@app.get("/leaderboard")
def leaderboard(limit: int = 10) -> JSONResponse:
    """Top players. Lane E (server/store/) backs this with MongoDB Atlas."""
    return JSONResponse([])
