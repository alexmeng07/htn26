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
from server.schemas import KeypointTimeline


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
    overlay: str = ""  # the character's skeleton points, drawn during the take
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


def _attach_generated_media(pack: ScenePack, scene_id: str) -> ScenePack:
    """Point the pack at whatever Scene Prep has produced so far.

    Prep runs in stages, so the app has to work with a half-built scene: after
    `prep.isolate_client` there is an isolated video to play even though the
    reference sheet and pack.json don't exist yet. Paths are URLs under /media,
    which server/main.py serves from the scenes directory.
    """
    folder = scene_dir(scene_id)
    if not pack.isolated_video and (folder / "isolated.mp4").exists():
        pack.isolated_video = f"/media/{scene_id}/isolated.mp4"
    if not pack.cue_audio and (folder / "trimmed.mp4").exists():
        # The trimmed clip carries the scene's own audio, which is the player's
        # cue track until a dedicated audio export exists.
        pack.cue_audio = f"/media/{scene_id}/trimmed.mp4"
    if not pack.key_moments and (folder / "key_moments.json").exists():
        moments = json.loads((folder / "key_moments.json").read_text(encoding="utf-8"))
        pack.key_moments = [KeyMoment(**m) for m in moments]
    if not pack.overlay and (folder / "overlay.json").exists():
        pack.overlay = f"/media/{scene_id}/overlay.json"
    if not pack.masks_dir and (folder / "masks" / "masks.json").exists():
        pack.masks_dir = f"/media/{scene_id}/masks/masks.json"
    if not pack.duration_s:
        source = folder / "isolated.mp4"
        if not source.exists():
            source = folder / "trimmed.mp4"
        if source.exists():
            from server.media.ffmpeg import duration_s

            try:
                pack.duration_s = duration_s(source)
            except Exception:  # noqa: BLE001 - a missing ffprobe must not break /scene
                pass
    return pack


def load_pack(scene_id: str | None = None) -> ScenePack:
    """Load the active scene pack.

    Prefers the generated pack.json; falls back to the raw config so the UI can
    boot before Scene Prep has run (fields will simply be empty).
    """
    settings = get_settings()
    scene_id = scene_id or settings.active_scene
    pack_path = scene_dir(scene_id) / "pack.json"
    if pack_path.exists():
        pack = ScenePack(**json.loads(pack_path.read_text(encoding="utf-8")))
    else:
        pack = ScenePack(**load_config(scene_id).model_dump())
    return _attach_generated_media(pack, scene_id)


def reference_keypoints(scene_id: str) -> KeypointTimeline | None:
    """The character's pose + expression timeline from prep, or None before prep ran."""
    path = scene_dir(scene_id) / "keypoints.json"
    if not path.exists():
        return None
    return KeypointTimeline.model_validate_json(path.read_text(encoding="utf-8"))


def save_pack(pack: ScenePack) -> Path:
    """Write the local JSON copy. MongoDB persistence lives in server/store/."""
    path = scene_dir(pack.scene_id) / "pack.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(pack.model_dump_json(indent=2), encoding="utf-8")
    return path
