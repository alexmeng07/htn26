"""MongoDB Atlas: scene packs, round results, live leaderboard.

Every read falls back to local JSON so the game survives the Wi-Fi dying.
"""

from __future__ import annotations

from functools import lru_cache

from pymongo import MongoClient

from server.config import get_settings
from server.schemas import LeaderboardEntry, RoundResult


@lru_cache
def client() -> MongoClient | None:
    uri = get_settings().mongodb_uri
    return MongoClient(uri, serverSelectionTimeoutMS=3000) if uri else None


def save_result(result: RoundResult) -> None:
    """Lane E: upsert into `rounds`; local JSON mirror under DATA_DIR."""
    raise NotImplementedError("Lane E: result persistence not implemented yet")


def top(limit: int = 10, scene_id: str | None = None) -> list[LeaderboardEntry]:
    """Lane E: best combined score per nickname. Change streams drive live updates."""
    raise NotImplementedError("Lane E: leaderboard query not implemented yet")
