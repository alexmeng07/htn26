"""ElevenLabs: judge voices, cached sound effects, and the dub voice changer."""

from __future__ import annotations

from pathlib import Path

from server.schemas import JudgeLine

SFX = ("drumroll", "yes_ding", "no_buzzer", "applause", "golden_buzzer", "confetti_pop")


def speak(line: JudgeLine, voice_id: str, dst: Path) -> Path:
    """Lane D: low-latency model, STREAMED so judge 1 talks while 2 and 3 generate."""
    raise NotImplementedError("Lane D: ElevenLabs speech not implemented yet")


def ensure_sfx_cache() -> dict[str, Path]:
    """Lane D: generate the SFX set once into assets/sfx/ and reuse forever."""
    raise NotImplementedError("Lane D: SFX cache not implemented yet")


def design_dub_voice(style_description: str) -> str:
    """Design a dub voice from the scene pack's text description; return its voice ID.

    DESIGNS a voice from words. Never clones the real actor's voice, or anyone's.
    """
    raise NotImplementedError("Lane D: voice design not implemented yet")


def dub(player_audio: Path, voice_id: str, dst: Path) -> Path:
    """Lane D: voice-changer pass over the player's recorded audio."""
    raise NotImplementedError("Lane D: voice changer not implemented yet")
