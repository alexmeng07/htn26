"""Round lifecycle: recording -> judging -> verdict -> dub.

Timing budget after the take ends (~6-8s, covered by the deliberation animation):
  side-by-side ~1s | OMNI ~3-5s | OpenAI ~1-2s | first judge voice ~0.5s
The dub runs in parallel; it isn't needed until after the verdict.
"""

from __future__ import annotations

from pathlib import Path


async def run_round(round_id: str, take: Path, nickname: str, attempt: int = 1):
    """Lane E: glue the lanes together and emit SSE events as each stage lands.

    1. media.side_by_side(isolated character, player take)
    2. compare.omni.compare  -> on timeout/failure, compare.fallback
    3. rules.votes.tally     -> plain code decides YES/NO
    4. judges.writer         -> one OpenAI call for all three reactions
    5. voice.speech.speak    -> streamed, judge 1 first
    6. store.db.save_result  -> leaderboard
    In parallel: voice.speech.dub -> emit dub_ready
    Finally: delete the raw take if DELETE_TAKES_AFTER_SCORING (privacy).
    """
    raise NotImplementedError("Lane E: round pipeline not implemented yet")
