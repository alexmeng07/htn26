"""Run MediaPipe pose + face landmarkers over a video file.

Two callers, one implementation:
  * prep, once per scene, for the reference character
  * the round pipeline, as the fallback when the browser could not sample the
    player live (R5.8) -- at a lower frame rate, same models, same maths

The browser runs the SAME pinned model files (assets/models/, fetched by
`scripts.fetch_models`), which is what keeps the two sides comparable (R6.4).
Frames are decoded by ffmpeg and piped raw, so any container the browser
records (webm/vp8) works without OpenCV codec support.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from server.config import get_settings
from server.media.ffmpeg import video_size
from server.schemas import KeypointSample, KeypointTimeline, PoseLandmark

POSE_MODEL = "pose_landmarker_full.task"
FACE_MODEL = "face_landmarker.task"
# Landmarkers see frames this wide; plenty for a person filling the frame.
WIDTH = 640


def _model(name: str) -> str:
    path = get_settings().assets_path / "models" / name
    if not path.exists():
        raise FileNotFoundError(
            f"Keypoint model missing: {path}. Run `uv run python -m scripts.fetch_models`."
        )
    return str(path)


def _frames(src: Path, fps: float, crop: list[int] | None):
    """Yield (width, height, rgb bytes) per sampled frame, decoded by ffmpeg."""
    w, h = video_size(src)
    filters = []
    if crop:
        x1, y1, x2, y2 = crop
        x1, y1, x2, y2 = max(0, x1), max(0, y1), min(w, x2), min(h, y2)
        filters.append(f"crop={x2 - x1}:{y2 - y1}:{x1}:{y1}")
        w, h = x2 - x1, y2 - y1
    out_w = min(WIDTH, w - w % 2)
    out_h = max(2, round(out_w * h / w / 2) * 2)
    filters += [f"fps={fps}", f"scale={out_w}:{out_h}"]

    proc = subprocess.Popen(
        [get_settings().ffmpeg_bin, "-loglevel", "error", "-i", str(src),
         "-vf", ",".join(filters), "-an", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        stdout=subprocess.PIPE,
    )
    size = out_w * out_h * 3
    try:
        assert proc.stdout is not None
        while chunk := proc.stdout.read(size):
            if len(chunk) < size:
                break
            yield out_w, out_h, chunk
    finally:
        proc.stdout.close()
        proc.wait()


def _run(src: Path, fps: float, crop: list[int] | None):
    """Yield (t, (width, height) of the frame seen, pose result, face result) per sample."""
    import mediapipe as mp
    import numpy as np
    from mediapipe.tasks import python as mp_python
    from mediapipe.tasks.python import vision

    pose_opts = vision.PoseLandmarkerOptions(
        base_options=mp_python.BaseOptions(model_asset_path=_model(POSE_MODEL)),
        running_mode=vision.RunningMode.VIDEO, num_poses=1,
    )
    face_opts = vision.FaceLandmarkerOptions(
        base_options=mp_python.BaseOptions(model_asset_path=_model(FACE_MODEL)),
        running_mode=vision.RunningMode.VIDEO, num_faces=1, output_face_blendshapes=True,
    )
    with (vision.PoseLandmarker.create_from_options(pose_opts) as pose_lm,
          vision.FaceLandmarker.create_from_options(face_opts) as face_lm):
        for i, (w, h, raw) in enumerate(_frames(src, fps, crop)):
            frame = np.frombuffer(raw, dtype=np.uint8).reshape(h, w, 3)
            image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame)
            ms = round(i * 1000 / fps)
            pose_res = pose_lm.detect_for_video(image, ms)
            yield ms / 1000, (w, h), pose_res, face_lm.detect_for_video(image, ms)


def _sample(t: float, pose_res, face_res) -> KeypointSample:
    return KeypointSample(
        t=round(t, 3),
        pose=[
            PoseLandmark(x=round(p.x, 4), y=round(p.y, 4), z=round(p.z, 4),
                         visibility=round(p.visibility or 0.0, 3))
            for p in (pose_res.pose_landmarks[0] if pose_res.pose_landmarks else [])
        ],
        face={
            c.category_name: round(c.score, 4)
            for c in (face_res.face_blendshapes[0] if face_res.face_blendshapes else [])
        },
    )


def extract(src: Path, fps: float = 15.0, crop: list[int] | None = None) -> KeypointTimeline:
    """Pose landmarks and face blendshapes for every sampled frame of `src`.

    `crop` is an [x1, y1, x2, y2] box in the video's pixel space; the scene's
    character_select box uses it to keep the landmarkers on the right person.
    """
    timeline, _ = extract_with_overlay(src, fps, crop, overlay=False)
    return timeline


def extract_with_overlay(
    src: Path, fps: float = 15.0, crop: list[int] | None = None, *, overlay: bool = True
) -> tuple[KeypointTimeline, dict | None]:
    """As `extract`, plus the points to DRAW over the full video during the take.

    The grading timeline is normalised to the crop (that's what the angles are
    measured in); the overlay is normalised to the whole frame so it lines up
    with the video on screen. Overlay pose points are [x, y, visibility]; face
    points are the 478 face-mesh landmarks as [x, y]. Drawing only -- never scored.
    """
    fw, fh = video_size(src)
    x0, y0, cw, ch = 0, 0, fw, fh
    if crop:
        x0, y0 = max(0, crop[0]), max(0, crop[1])
        cw, ch = min(fw, crop[2]) - x0, min(fh, crop[3]) - y0

    def full(x: float, y: float) -> list[float]:
        return [round((x0 + x * cw) / fw, 4), round((y0 + y * ch) / fh, 4)]

    samples: list[KeypointSample] = []
    frames: list[dict] = []
    aspect = 16 / 9
    for t, (w, h), pose_res, face_res in _run(src, fps, crop):
        aspect = w / h
        samples.append(_sample(t, pose_res, face_res))
        if overlay:
            pose = pose_res.pose_landmarks[0] if pose_res.pose_landmarks else []
            face = face_res.face_landmarks[0] if face_res.face_landmarks else []
            frames.append({
                "t": round(t, 3),
                "pose": [[*full(p.x, p.y), round(p.visibility or 0.0, 2)] for p in pose],
                "face": [full(p.x, p.y) for p in face],
            })
    timeline = KeypointTimeline(fps=fps, aspect=round(aspect, 4), samples=samples)
    return timeline, ({"fps": fps, "size": [fw, fh], "frames": frames} if overlay else None)
