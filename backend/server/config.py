"""Central settings. Every environment variable in the project is declared here.

Nothing scene-specific belongs in this file: the movie, character, thresholds and
dub voice all live in the scene pack (see server/scene.py).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- Huawei OMNI (perception: face + body + voice in one pass) ---
    omni_base_url: str = ""
    omni_api_key: str = ""
    omni_model: str = ""
    omni_model_dev: str = ""

    # --- OpenAI (judge dialogue) ---
    openai_api_key: str = ""
    openai_model_judges: str = "gpt-4.1-mini"

    # --- ElevenLabs (judge voices, SFX, dub) ---
    elevenlabs_api_key: str = ""
    voice_judge_face: str = ""
    voice_judge_body: str = ""
    voice_judge_voice: str = ""

    # --- Baseten (SAM 2, prep only) ---
    baseten_api_key: str = ""
    sam2_endpoint_url: str = ""

    # --- MongoDB Atlas ---
    mongodb_uri: str = ""
    mongodb_db: str = "scenestealer"

    # --- Scene selection ---
    active_scene: str = "dev-clip"
    default_threshold: int = 70

    # --- Local runtime ---
    server_host: str = "127.0.0.1"
    server_port: int = 8000
    web_port: int = 5173
    data_dir: str = "data"
    ffmpeg_bin: str = "ffmpeg"
    delete_takes_after_scoring: bool = True
    force_fallback: bool = False

    # ---------------- derived paths ----------------
    @property
    def root(self) -> Path:
        return ROOT

    @property
    def data_path(self) -> Path:
        p = ROOT / self.data_dir
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def scenes_path(self) -> Path:
        return ROOT / "scenes"

    @property
    def assets_path(self) -> Path:
        return ROOT / "assets"

    # ---------------- readiness ----------------
    def missing_keys(self) -> dict[str, list[str]]:
        """Which service is missing which env vars. Powers GET /health."""
        groups = {
            "omni": ["omni_base_url", "omni_api_key", "omni_model"],
            "openai": ["openai_api_key"],
            "elevenlabs": [
                "elevenlabs_api_key",
                "voice_judge_face",
                "voice_judge_body",
                "voice_judge_voice",
            ],
            "baseten": ["baseten_api_key", "sam2_endpoint_url"],
            "mongodb": ["mongodb_uri"],
        }
        return {
            service: [f.upper() for f in fields if not getattr(self, f)]
            for service, fields in groups.items()
            if any(not getattr(self, f) for f in fields)
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
