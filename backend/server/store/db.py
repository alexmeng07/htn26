"""MongoDB Atlas: scene packs, round results, live leaderboard.

Every read falls back to local JSON so the game survives the Wi-Fi dying.
"""

from __future__ import annotations

import logging
import time
from functools import lru_cache
from pathlib import Path

from pymongo import MongoClient
from pymongo.errors import PyMongoError

from server.config import get_settings
from server.schemas import LeaderboardEntry, RoundResult

log = logging.getLogger(__name__)

# After a failure, skip Atlas for a while instead of paying the connection
# timeout on every request -- the local JSON copy carries the game meanwhile.
RETRY_AFTER_S = 60.0
_down_until = 0.0


@lru_cache
def client() -> MongoClient | None:
    uri = get_settings().mongodb_uri
    return MongoClient(uri, serverSelectionTimeoutMS=3000) if uri else None


def _collection(name: str):
    c = client()
    if c is None or time.monotonic() < _down_until:
        return None
    return c[get_settings().mongodb_db][name]


def _rounds():
    return _collection("rounds")


def save_pack(pack: dict) -> bool:
    """Upsert a scene pack into `scene_packs`. False (and a warning) if Atlas is down;
    the caller has already written pack.json, which is what the game reads."""
    packs = _collection("scene_packs")
    if packs is None:
        return False
    try:
        packs.replace_one({"scene_id": pack["scene_id"]}, pack, upsert=True)
        return True
    except PyMongoError as exc:
        _mark_down(exc)
        return False


def _mark_down(exc: Exception) -> None:
    global _down_until
    _down_until = time.monotonic() + RETRY_AFTER_S
    log.warning(
        "MongoDB unavailable, using local JSON for %.0fs: %s",
        RETRY_AFTER_S, str(exc).split(",")[0],
    )


def _local_dir() -> Path:
    path = get_settings().data_path / "rounds"
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_result(result: RoundResult) -> None:
    """Upsert into `rounds`; always mirrored to local JSON under DATA_DIR."""
    (_local_dir() / f"{result.round_id}.json").write_text(
        result.model_dump_json(indent=2), encoding="utf-8"
    )
    rounds = _rounds()
    if rounds is None:
        return
    try:
        rounds.replace_one(
            {"round_id": result.round_id}, result.model_dump(mode="python"), upsert=True
        )
    except PyMongoError as exc:
        _mark_down(exc)


def _best_per_nickname(results: list[RoundResult], limit: int) -> list[LeaderboardEntry]:
    best: dict[str, RoundResult] = {}
    for r in results:
        if r.nickname not in best or r.combined > best[r.nickname].combined:
            best[r.nickname] = r
    ranked = sorted(best.values(), key=lambda r: (-r.combined, r.created_at))[:limit]
    return [
        LeaderboardEntry(
            nickname=r.nickname, combined=r.combined, scene_id=r.scene_id,
            passed=r.passed, created_at=r.created_at,
        )
        for r in ranked
    ]


def _top_local(limit: int, scene_id: str | None) -> list[LeaderboardEntry]:
    results = []
    for path in _local_dir().glob("*.json"):
        try:
            r = RoundResult.model_validate_json(path.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if scene_id is None or r.scene_id == scene_id:
            results.append(r)
    return _best_per_nickname(results, limit)


def top(limit: int = 10, scene_id: str | None = None) -> list[LeaderboardEntry]:
    """Best combined score per nickname, highest first."""
    rounds = _rounds()
    if rounds is None:
        return _top_local(limit, scene_id)
    match = {"scene_id": scene_id} if scene_id else {}
    pipeline = [
        {"$match": match},
        {"$sort": {"combined": -1, "created_at": 1}},
        {"$group": {"_id": "$nickname", "doc": {"$first": "$$ROOT"}}},
        {"$replaceRoot": {"newRoot": "$doc"}},
        {"$sort": {"combined": -1, "created_at": 1}},
        {"$limit": limit},
    ]
    try:
        return [LeaderboardEntry(**doc) for doc in rounds.aggregate(pipeline)]
    except PyMongoError as exc:
        _mark_down(exc)
        return _top_local(limit, scene_id)


def load_result(round_id: str) -> RoundResult | None:
    """A saved round from the local mirror -- survives a server restart."""
    path = _local_dir() / f"{round_id}.json"
    if not path.exists():
        return None
    return RoundResult.model_validate_json(path.read_text(encoding="utf-8"))
