"""The replay: the player composited INTO the scene, in place of the character.

Per frame of the trimmed clip:
  1. SAM 2's mask (from prep, masks/masks.json) says where the character is.
  2. That region is filled from its surroundings (inpainted at low resolution,
     which is plenty under a person-sized patch) -- a rough clean plate.
  3. The player is cut out of their take with MediaPipe's pose segmentation
     mask -- the same pinned model grading uses, so no extra download and no
     per-round SAM 2 call.
  4. The cutout is scaled and placed to fill the character's outline (heights
     matched, tops and centres aligned, smoothed over time so it doesn't
     jitter), colour-matched toward the scene, and feathered in.
Frames where the character is off screen (a cutaway) play untouched.

Beside the video it writes `replay_overlay.json`: the player's pose and face
points for every frame, moved through the SAME scale and offset as the pasted
cut-out, so they sit exactly on the player in the replay. Together with the
scene's overlay.json (the character's points, same frame) the replay can show
both skeletons at once. Drawing only.

Cosmetic only: nothing here feeds a score (I9). It runs in the replay task
after the verdict, and any failure falls back to the side-by-side (R13.3).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import numpy as np

from server.config import get_settings
from server.media.ffmpeg import video_size
from server.media.keypoints import FACE_MODEL, POSE_MODEL, _model

# Width the player is segmented at; masks are upscaled from there.
SEGMENT_WIDTH = 640
# Clean plate is inpainted at this fraction of full size. Inpainting cost grows
# with the hole, and a close-up's hole is ~40% of the frame; 1/8 is fast and,
# under a person-sized patch that the player then covers, smooth enough.
PLATE_SCALE = 0.125
# Exponential smoothing for the placement boxes: lower = steadier, laggier.
SMOOTHING = 0.25
# How far to pull the player's colours toward the scene (0 = none, 1 = full).
COLOUR_MATCH = 0.6
PERSON_THRESHOLD = 0.5


def decode_rle(rle: dict) -> np.ndarray:
    """COCO compressed RLE -> HxW uint8 mask. Mirrors pycocotools' rleFrString."""
    h, w = rle["size"]
    s = rle["counts"].encode() if isinstance(rle["counts"], str) else bytes(rle["counts"])
    counts: list[int] = []
    p = 0
    while p < len(s):
        x, k, more = 0, 0, True
        while more:
            c = s[p] - 48
            x |= (c & 0x1F) << (5 * k)
            more = bool(c & 0x20)
            p += 1
            k += 1
            if not more and (c & 0x10):
                x |= -1 << (5 * k)
        if len(counts) > 2:
            x += counts[-2]
        counts.append(x)
    flat = np.zeros(h * w, dtype=np.uint8)
    pos = 0
    for i, run in enumerate(counts):
        if i % 2:
            flat[pos:pos + run] = 1
        pos += run
    return flat.reshape((w, h)).T  # COCO runs are column-major


def _frames(src: Path, fps: float, width: int, height: int, *, hflip: bool = False):
    vf = f"fps={fps},scale={width}:{height}" + (",hflip" if hflip else "")
    proc = subprocess.Popen(
        [get_settings().ffmpeg_bin, "-loglevel", "error", "-i", str(src), "-vf", vf,
         "-an", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,  # stopping early is normal; its broken pipe is not news
    )
    size = width * height * 3
    try:
        assert proc.stdout is not None
        while (chunk := proc.stdout.read(size)) and len(chunk) == size:
            yield np.frombuffer(chunk, dtype=np.uint8).reshape(height, width, 3)
    finally:
        proc.stdout.close()
        proc.wait()


def _bbox(mask: np.ndarray) -> tuple[float, float, float, float] | None:
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return None
    return float(xs.min()), float(ys.min()), float(xs.max() + 1), float(ys.max() + 1)


def _smooth(prev, new):
    if new is None:
        return prev
    if prev is None:
        return new
    return tuple(p + SMOOTHING * (n - p) for p, n in zip(prev, new, strict=True))


def _clean_plate(frame: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """The scene with the character painted out from its surroundings.

    Inpaint, blur and feather all happen at PLATE_SCALE, and the full-size blend
    is confined to the character's bounding box.
    """
    import cv2

    h, w = mask.shape
    sw, sh = max(8, int(w * PLATE_SCALE)), max(8, int(h * PLATE_SCALE))
    small = cv2.resize(frame, (sw, sh), interpolation=cv2.INTER_AREA)
    hole = cv2.resize(mask * 255, (sw, sh), interpolation=cv2.INTER_NEAREST)
    hole = cv2.dilate(hole, np.ones((5, 5), np.uint8))  # ~40px: stray hair past the mask
    box = _bbox(hole)
    if box is None:
        return frame
    filled = cv2.GaussianBlur(cv2.inpaint(small, hole, 3, cv2.INPAINT_TELEA), (0, 0), 1.0)
    alpha = cv2.GaussianBlur(hole.astype(np.float32) / 255, (0, 0), 1.0)

    fx = w / sw
    x0, y0 = max(0, int((box[0] - 2) * fx)), max(0, int((box[1] - 2) * fx))
    x1, y1 = min(w, int((box[2] + 2) * fx)), min(h, int((box[3] + 2) * fx))
    filled = cv2.resize(filled, (w, h), interpolation=cv2.INTER_LINEAR)[y0:y1, x0:x1]
    alpha = cv2.resize(alpha, (w, h), interpolation=cv2.INTER_LINEAR)[y0:y1, x0:x1, None]
    out = frame.copy()
    region = out[y0:y1, x0:x1].astype(np.float32)
    out[y0:y1, x0:x1] = (region + (filled - region) * alpha).astype(np.uint8)
    return out


def _scene_stats(scene: np.ndarray, mask: np.ndarray) -> tuple[np.ndarray, np.ndarray] | None:
    """Per-channel mean/std of the character region, measured small (plenty for stats)."""
    import cv2

    h, w = mask.shape
    size = (max(8, w // 4), max(8, h // 4))
    region = cv2.resize(mask, size, interpolation=cv2.INTER_NEAREST) > 0
    if region.sum() < 50:
        return None
    pixels = cv2.resize(scene, size, interpolation=cv2.INTER_AREA)[region].astype(np.float32)
    return pixels.mean(0), pixels.std(0) + 1e-3


def _match_colour(player: np.ndarray, alpha: np.ndarray, stats) -> np.ndarray:
    """Pull the player's per-channel mean/std toward the character region's.

    A gain and offset per channel: cheap, and enough to stop a cool-lit webcam
    face glowing inside a warm film frame.
    """
    fg = alpha > PERSON_THRESHOLD
    if stats is None or fg.sum() < 50:
        return player
    src = player[fg].astype(np.float32)
    s_mean, s_std = src.mean(0), src.std(0) + 1e-3
    r_mean, r_std = stats
    gain = 1 + COLOUR_MATCH * (r_std / s_std - 1)
    bias = COLOUR_MATCH * (r_mean - s_mean * r_std / s_std)
    return np.clip(player.astype(np.float32) * gain + bias, 0, 255).astype(np.uint8)


def _placed(x: float, y: float, at: tuple[int, int, int, int, int, int]) -> list[float]:
    """A point normalised to the player's frame -> normalised to the replay frame,
    given where the cut-out went: (left, top, width, height, frame w, frame h)."""
    ox, oy, sw, sh, w, h = at
    return [round((ox + x * sw) / w, 4), round((oy + y * sh) / h, 4)]


def overlay_path(replay_video: Path) -> Path:
    """Where the player's replay skeleton is written, beside the replay."""
    return replay_video.with_name("replay_overlay.json")


def replay(scene_clip: Path, masks_json: Path, take: Path, dst: Path) -> Path:
    """Write the composited replay to `dst`, carrying the player's own audio,
    plus the player's skeleton in replay coordinates (see overlay_path)."""
    import cv2
    import mediapipe as mp
    from mediapipe.tasks import python as mp_python
    from mediapipe.tasks.python import vision

    meta = json.loads(masks_json.read_text(encoding="utf-8"))
    if meta.get("format") != "rle":
        raise ValueError(f"unsupported mask format {meta.get('format')!r}")
    fps = float(meta["fps"])
    w, h = video_size(scene_clip)
    if [w, h] != list(meta["size"]):
        raise ValueError(f"masks are {meta['size']}, clip is {[w, h]} -- re-run segmentation")

    tw, th = video_size(take)
    pw = SEGMENT_WIDTH
    ph = max(2, round(pw * th / tw / 2) * 2)

    options = vision.PoseLandmarkerOptions(
        base_options=mp_python.BaseOptions(model_asset_path=_model(POSE_MODEL)),
        running_mode=vision.RunningMode.VIDEO, num_poses=1, output_segmentation_masks=True,
    )
    face_options = vision.FaceLandmarkerOptions(
        base_options=mp_python.BaseOptions(model_asset_path=_model(FACE_MODEL)),
        running_mode=vision.RunningMode.VIDEO, num_faces=1,
    )
    overlay: list[dict] = []
    dst.parent.mkdir(parents=True, exist_ok=True)
    encoder = subprocess.Popen(
        [get_settings().ffmpeg_bin, "-y", "-loglevel", "error",
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(fps), "-i", "-",
         "-i", str(take), "-map", "0:v", "-map", "1:a?",
         "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-shortest", str(dst)],
        stdin=subprocess.PIPE,
    )
    char_box = player_box = None
    player_iter = _frames(take, fps, pw, ph, hflip=True)  # mirrored, as the player saw it
    try:
        assert encoder.stdin is not None
        with (vision.PoseLandmarker.create_from_options(options) as segmenter,
              vision.FaceLandmarker.create_from_options(face_options) as face_lm):
            for i, scene in enumerate(_frames(scene_clip, fps, w, h)):
                player = next(player_iter, None)
                visible = i < len(meta["visible"]) and meta["visible"][i]
                if player is None or not visible:
                    encoder.stdin.write(scene.tobytes())
                    continue

                char_mask = decode_rle(meta["masks"][i])
                image = mp.Image(
                    image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(player)
                )
                result = segmenter.detect_for_video(image, round(i * 1000 / fps))
                faces = face_lm.detect_for_video(image, round(i * 1000 / fps))
                base = _clean_plate(scene, char_mask)
                if not result.segmentation_masks:
                    encoder.stdin.write(base.tobytes())
                    continue
                alpha = result.segmentation_masks[0].numpy_view().astype(np.float32)
                if alpha.ndim == 3:
                    alpha = alpha[..., 0]

                char_box = _smooth(char_box, _bbox(char_mask))
                player_box = _smooth(player_box, _bbox(alpha > PERSON_THRESHOLD))
                if char_box is None or player_box is None:
                    encoder.stdin.write(base.tobytes())
                    continue

                # Fit: match heights, align tops and horizontal centres.
                cx1, cy1, cx2, cy2 = char_box
                px1, py1, px2, py2 = player_box
                scale = (cy2 - cy1) / max(py2 - py1, 1.0)
                sw, sh = max(1, round(pw * scale)), max(1, round(ph * scale))
                ox = round((cx1 + cx2) / 2 - (px1 + px2) / 2 * scale)
                oy = round(cy1 - py1 * scale)

                # The player's points, through the same placement as the cut-out.
                at = (ox, oy, sw, sh, w, h)
                pose = result.pose_landmarks[0] if result.pose_landmarks else []
                face = faces.face_landmarks[0] if faces.face_landmarks else []
                overlay.append({
                    "t": round(i / fps, 3),
                    "pose": [[*_placed(q.x, q.y, at), round(q.visibility or 0.0, 2)] for q in pose],
                    "face": [_placed(q.x, q.y, at) for q in face],
                })

                matched = _match_colour(player, alpha, _scene_stats(scene, char_mask))
                big = cv2.resize(matched, (sw, sh), interpolation=cv2.INTER_LINEAR)
                big_a = cv2.GaussianBlur(
                    cv2.resize(alpha, (sw, sh), interpolation=cv2.INTER_LINEAR), (0, 0), 2
                )

                # Paste, clipped to the frame.
                x0, y0 = max(0, ox), max(0, oy)
                x1, y1 = min(w, ox + sw), min(h, oy + sh)
                out = base.copy()
                if x1 > x0 and y1 > y0:
                    a = big_a[y0 - oy:y1 - oy, x0 - ox:x1 - ox, None]
                    fg = big[y0 - oy:y1 - oy, x0 - ox:x1 - ox].astype(np.float32)
                    region = out[y0:y1, x0:x1].astype(np.float32)
                    out[y0:y1, x0:x1] = (region * (1 - a) + fg * a).astype(np.uint8)
                encoder.stdin.write(out.tobytes())
    finally:
        if encoder.stdin:
            encoder.stdin.close()
        encoder.wait()
        player_iter.close()
    if encoder.returncode != 0:
        raise RuntimeError(f"ffmpeg failed encoding the replay ({encoder.returncode})")
    overlay_path(dst).write_text(
        json.dumps({"fps": fps, "size": [w, h], "frames": overlay}, separators=(",", ":")),
        encoding="utf-8",
    )
    return dst
