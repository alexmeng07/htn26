"""MongoDB Atlas persistence with a local JSON safety net.

Round results are always mirrored locally. Leaderboard reads merge bounded
Atlas candidates with that mirror, so scores captured during an outage do not
disappear when Atlas comes back online.
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

RETRY_AFTER_S = 60.0
MAX_LEADERBOARD_LIMIT = 100
_down_until = 0.0


@lru_cache
def client() -> MongoClient | None:
    settings = get_settings()
    return (
        MongoClient(
            settings.mongodb_uri,
            serverSelectionTimeoutMS=3000,
            connectTimeoutMS=3000,
            socketTimeoutMS=3000,
        )
        if settings.mongodb_uri
        else None
    )


def _mark_up() -> None:
    global _down_until
    _down_until = 0.0


def _mark_down(exc: Exception) -> None:
    global _down_until
    _down_until = time.monotonic() + RETRY_AFTER_S
    log.warning(
        "MongoDB unavailable, using local JSON for %.0fs (%s)",
        RETRY_AFTER_S,
        type(exc).__name__,
    )


def _collection(name: str):
    settings = get_settings()
    if settings.force_fallback or time.monotonic() < _down_until:
        return None
    try:
        c = client()
    except (PyMongoError, ValueError) as exc:
        _mark_down(exc)
        return None
    return c[settings.mongodb_db][name] if c is not None else None


def _rounds():
    return _collection("rounds")


def mongo_status(*, force_probe: bool = False) -> dict[str, bool | float | str]:
    """Return sanitized Atlas readiness without exposing connection details.

    Normal health checks honor the circuit breaker, avoiding repeated slow
    probes during an outage. The explicit sync command can force one probe.
    """
    settings = get_settings()
    if settings.force_fallback:
        return {
            "configured": bool(settings.mongodb_uri),
            "reachable": False,
            "mode": "forced-local",
            "detail": "local fallback forced",
        }
    if not settings.mongodb_uri:
        return {
            "configured": False,
            "reachable": False,
            "mode": "local",
            "detail": "MONGODB_URI missing",
        }

    retry_after = max(0.0, _down_until - time.monotonic())
    if retry_after and not force_probe:
        return {
            "configured": True,
            "reachable": False,
            "mode": "local",
            "detail": "unreachable; serving local mirror",
            "retry_after_s": round(retry_after, 1),
        }

    try:
        c = client()
        if c is None:
            raise RuntimeError("MongoDB client is not configured")
        c.admin.command("ping")
    except (PyMongoError, RuntimeError, ValueError) as exc:
        _mark_down(exc)
        return {
            "configured": True,
            "reachable": False,
            "mode": "local",
            "detail": "unreachable; serving local mirror",
            "retry_after_s": RETRY_AFTER_S,
        }

    _mark_up()
    return {
        "configured": True,
        "reachable": True,
        "mode": "atlas+local",
        "detail": "connected",
    }


def save_pack(pack: dict) -> bool:
    """Upsert a scene pack, returning whether Atlas confirmed the write."""
    packs = _collection("scene_packs")
    if packs is None:
        return False
    try:
        packs.replace_one({"scene_id": pack["scene_id"]}, pack, upsert=True)
        _mark_up()
        return True
    except (PyMongoError, ValueError) as exc:
        _mark_down(exc)
        return False


def _local_dir() -> Path:
    path = get_settings().data_path / "rounds"
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_result(result: RoundResult) -> bool:
    """Mirror a round locally, then upsert it to Atlas.

    ``False`` means the durable local copy succeeded but Atlas did not confirm
    the write. Retrying is safe because ``round_id`` is the upsert key.
    """
    (_local_dir() / f"{result.round_id}.json").write_text(
        result.model_dump_json(indent=2), encoding="utf-8"
    )
    rounds = _rounds()
    if rounds is None:
        return False
    try:
        rounds.replace_one(
            {"round_id": result.round_id}, result.model_dump(mode="python"), upsert=True
        )
        _mark_up()
        return True
    except (PyMongoError, ValueError) as exc:
        _mark_down(exc)
        return False


def _best_rounds(results: list[RoundResult], limit: int) -> list[RoundResult]:
    best: dict[str, RoundResult] = {}
    for result in results:
        current = best.get(result.nickname)
        if current is None or result.combined > current.combined or (
            result.combined == current.combined and result.created_at < current.created_at
        ):
            best[result.nickname] = result
    return sorted(best.values(), key=lambda result: (-result.combined, result.created_at))[:limit]


def _entries(results: list[RoundResult], limit: int) -> list[LeaderboardEntry]:
    return [
        LeaderboardEntry(
            nickname=result.nickname,
            combined=result.combined,
            scene_id=result.scene_id,
            passed=result.passed,
            created_at=result.created_at,
        )
        for result in _best_rounds(results, limit)
    ]


def _local_results(scene_id: str | None = None) -> list[RoundResult]:
    results: list[RoundResult] = []
    for path in _local_dir().glob("*.json"):
        try:
            result = RoundResult.model_validate_json(path.read_text(encoding="utf-8"))
        except ValueError:
            log.warning("Skipping invalid local round file: %s", path.name)
            continue
        if scene_id is None or result.scene_id == scene_id:
            results.append(result)
    return results


def _top_local(limit: int, scene_id: str | None) -> list[LeaderboardEntry]:
    safe_limit = min(max(limit, 1), MAX_LEADERBOARD_LIMIT)
    return _entries(_local_results(scene_id), safe_limit)


def _mongo_candidates(rounds, limit: int, scene_id: str | None) -> list[RoundResult]:
    """Ask Atlas for at most ``limit`` best-per-nickname documents."""
    match = {"scene_id": scene_id} if scene_id else {}
    pipeline = [
        {"$match": match},
        {"$sort": {"combined": -1, "created_at": 1}},
        {"$group": {"_id": "$nickname", "doc": {"$first": "$$ROOT"}}},
        {"$replaceRoot": {"newRoot": "$doc"}},
        {"$sort": {"combined": -1, "created_at": 1}},
        {"$limit": limit},
    ]
    candidates: list[RoundResult] = []
    for document in rounds.aggregate(pipeline):
        try:
            candidates.append(RoundResult.model_validate(document))
        except ValueError:
            log.warning("Skipping invalid MongoDB round document")
    return candidates


def top(limit: int = 10, scene_id: str | None = None) -> list[LeaderboardEntry]:
    """Return each nickname's best score across Atlas and the local mirror."""
    safe_limit = min(max(limit, 1), MAX_LEADERBOARD_LIMIT)
    local = _best_rounds(_local_results(scene_id), safe_limit)
    rounds = _rounds()
    if rounds is None:
        return _entries(local, safe_limit)

    try:
        remote = _mongo_candidates(rounds, safe_limit, scene_id)
        _mark_up()
    except (PyMongoError, ValueError) as exc:
        _mark_down(exc)
        return _entries(local, safe_limit)

    merged = {result.round_id: result for result in remote}
    # Local is written first and may contain the richer/final version of a round.
    merged.update({result.round_id: result for result in local})
    return _entries(list(merged.values()), safe_limit)


def load_result(round_id: str) -> RoundResult | None:
    """A saved round from the local mirror -- survives a server restart."""
    path = _local_dir() / f"{round_id}.json"
    if not path.exists():
        return None
    return RoundResult.model_validate_json(path.read_text(encoding="utf-8"))
