"""Scene pack: the ONE place scene-specific details live.

No movie title, character name, actor, line of dialogue, timestamp or file name
may appear anywhere else in the codebase. Swapping scenes must mean re-running
Scene Prep on a new clip and changing ACTIVE_SCENE -- nothing else.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from server.config import get_settings


class Thresholds(BaseModel):
    face: int = 70
    body: int = 70
    voice: int = 70


class CharacterSelect(BaseModel):
    """Where the target character is in the first frame, for SAM 2."""

    box: list[int] | None = None  # [x1, y1, x2, y2]
    point: list[int] | None = None  # [x, y]


class KeyMoment(BaseModel):
    """A moment where the character's expression or posture clearly changes."""

    t: float  # seconds from the start of the trimmed clip
    label: str = ""
    face: str = ""  # reference description, written by OMNI during prep
    body: str = ""
    voice: str = ""


class SceneConfig(BaseModel):
    """Hand-written `scenes/<scene_id>/scene.yaml`."""

    scene_id: str
    movie_title: str
    character_name: str
    actor_name: str
    clip_file: str
    start: str
    end: str
    character_select: CharacterSelect = Field(default_factory=CharacterSelect)
    briefing: str
    tip: str
    title_line: str
    voice_mode: str = "emotional"  # "emotional" (non-verbal) | "lines" (dialogue)
    other_voices_in_audio: bool = True  # true -> headphones required
    thresholds: Thresholds = Field(default_factory=Thresholds)
    dub_voice_style: str = ""  # DESIGNS a voice; never clones a real person's
    source_note: str = ""


class ScenePack(SceneConfig):
    """Scene config + everything Scene Prep generated. Served by GET /scene."""

    isolated_video: str = ""
    cue_audio: str = ""
    subtitles: str = ""
    masks_dir: str = ""
    duration_s: float = 0.0
    key_moments: list[KeyMoment] = Field(default_factory=list)
    dub_voice_id: str = ""
    prepared_at: str = ""

    @property
    def headphones_required(self) -> bool:
        return self.other_voices_in_audio


def scene_dir(scene_id: str) -> Path:
    return get_settings().scenes_path / scene_id


def load_config(scene_id: str) -> SceneConfig:
    path = scene_dir(scene_id) / "scene.yaml"
    if not path.exists():
        raise FileNotFoundError(f"No scene.yaml for scene '{scene_id}' at {path}")
    return SceneConfig(**yaml.safe_load(path.read_text(encoding="utf-8")))


def load_pack(scene_id: str | None = None) -> ScenePack:
    """Load the active scene pack.

    Prefers the generated pack.json; falls back to the raw config so the UI can
    boot before Scene Prep has run (fields will simply be empty).
    """
    settings = get_settings()
    scene_id = scene_id or settings.active_scene
    pack_path = scene_dir(scene_id) / "pack.json"
    if pack_path.exists():
        return ScenePack(**json.loads(pack_path.read_text(encoding="utf-8")))
    return ScenePack(**load_config(scene_id).model_dump())


def save_pack(pack: ScenePack) -> Path:
    """Write the local JSON copy. MongoDB persistence lives in server/store/."""
    path = scene_dir(pack.scene_id) / "pack.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(pack.model_dump_json(indent=2), encoding="utf-8")
    return path
