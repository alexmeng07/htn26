"""ElevenLabs: judge voices, cached sound effects, and the dub voice changer."""

from __future__ import annotations

from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path

from elevenlabs.client import ElevenLabs

from server.config import get_settings
from server.schemas import JudgeLine

# Low-latency model for the judges' live lines; STS model for the dub.
TTS_MODEL = "eleven_flash_v2_5"
STS_MODEL = "eleven_multilingual_sts_v2"
OUTPUT_FORMAT = "mp3_44100_128"

SFX = ("drumroll", "yes_ding", "no_buzzer", "applause", "golden_buzzer", "confetti_pop")

SFX_PROMPTS: dict[str, tuple[str, float]] = {
    "drumroll": ("tense snare drum roll building suspense, talent show", 4.0),
    "yes_ding": ("bright bell ding, game show correct answer", 1.0),
    "no_buzzer": ("loud game show wrong-answer buzzer", 1.0),
    "applause": ("enthusiastic theatre audience applause and cheering", 4.0),
    "golden_buzzer": ("triumphant golden buzzer fanfare with sparkling chimes", 3.0),
    "confetti_pop": ("party popper confetti burst", 1.0),
}


@lru_cache
def client() -> ElevenLabs:
    key = get_settings().elevenlabs_api_key
    if not key:
        raise RuntimeError("ELEVENLABS_API_KEY is not set")
    return ElevenLabs(api_key=key)


def _write(chunks: Iterable[bytes], dst: Path) -> Path:
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(dst.suffix + ".part")
    with tmp.open("wb") as f:
        for chunk in chunks:
            f.write(chunk)
    tmp.replace(dst)
    return dst


def speak(line: JudgeLine, voice_id: str, dst: Path) -> Path:
    """Low-latency model, streamed to disk. The pipeline voices judge 1 first."""
    return _write(
        client().text_to_speech.stream(
            voice_id=voice_id, text=line.spoken, model_id=TTS_MODEL, output_format=OUTPUT_FORMAT
        ),
        dst,
    )


def sfx_dir() -> Path:
    return get_settings().assets_path / "sfx"


def ensure_sfx_cache() -> dict[str, Path]:
    """Generate the SFX set once into assets/sfx/ and reuse forever."""
    paths = {}
    for name in SFX:
        dst = sfx_dir() / f"{name}.mp3"
        if not dst.exists():
            prompt, seconds = SFX_PROMPTS[name]
            _write(
                client().text_to_sound_effects.convert(
                    text=prompt, duration_seconds=seconds, output_format=OUTPUT_FORMAT
                ),
                dst,
            )
        paths[name] = dst
    return paths


def design_voice(name: str, description: str) -> str:
    """DESIGN a voice from words and save it; return its voice ID.

    Never clones the real actor's voice, or anyone's.
    """
    previews = client().text_to_voice.design(voice_description=description, auto_generate_text=True)
    if not previews.previews:
        raise RuntimeError(f"ElevenLabs returned no voice previews for '{name}'")
    voice = client().text_to_voice.create(
        voice_name=name,
        voice_description=description,
        generated_voice_id=previews.previews[0].generated_voice_id,
    )
    return voice.voice_id


def design_dub_voice(style_description: str) -> str:
    """Design the scene's dub voice from the scene pack's text description."""
    return design_voice("SceneStealer dub", style_description)


def dub(player_audio: Path, voice_id: str, dst: Path) -> Path:
    """Voice-changer pass over the player's recorded audio."""
    with player_audio.open("rb") as audio:
        return _write(
            client().speech_to_speech.convert(
                voice_id=voice_id,
                audio=audio,
                model_id=STS_MODEL,
                output_format=OUTPUT_FORMAT,
                remove_background_noise=True,
            ),
            dst,
        )
