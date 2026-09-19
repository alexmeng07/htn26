"""SAM 2 video segmentation, packaged for Baseten.

Contract
--------
predict({
    "video_b64":  str,             # the trimmed clip, base64 mp4
    "box":        [x1,y1,x2,y2],   # OR
    "point":      [x, y],          #    one prompt on the FIRST frame
    "background": "dark",          # "dark" | "blur"
    "mask_format": "rle",          # "rle" (tiny) | "png" (debuggable, large)
})
-> {
    "isolated_b64": str,           # the character alone, base64 mp4
    "masks": [...],                # per frame, COCO RLE
    "visible": [bool, ...],        # False = cutaway; skip it when scoring
    "fps": float,
    "frame_count": int,
    "size": [w, h],
}

Why compositing happens here: the frames are already decoded on the GPU box, so
returning one finished mp4 plus RLE masks is a few MB, while shipping raw
per-frame PNGs back would be hundreds. Baseten caps a request body at 100MB.
"""

from __future__ import annotations

import base64
import json
import subprocess
import tempfile
from pathlib import Path

import cv2
import numpy as np
import torch
from pycocotools import mask as mask_utils

CHECKPOINT_REPO = "facebook/sam2.1-hiera-large"
MODEL_CFG = "configs/sam2.1/sam2.1_hiera_l.yaml"

# A mask smaller than this share of the frame means the character isn't really
# there -- the film has cut away. Those frames are skipped when scoring.
VISIBLE_MIN_AREA = 0.002


class Model:
    def __init__(self, **kwargs):
        self._predictor = None

    def load(self):
        from huggingface_hub import hf_hub_download
        from sam2.build_sam import build_sam2_video_predictor

        checkpoint = hf_hub_download(CHECKPOINT_REPO, "sam2.1_hiera_large.pt")
        self._predictor = build_sam2_video_predictor(
            MODEL_CFG, checkpoint, device="cuda" if torch.cuda.is_available() else "cpu"
        )

    # ---------------------------------------------------------------- helpers
    @staticmethod
    def _explode(video: Path, frames_dir: Path) -> tuple[float, int, tuple[int, int]]:
        """SAM 2's video predictor wants a directory of zero-padded JPEGs."""
        frames_dir.mkdir(parents=True, exist_ok=True)
        capture = cv2.VideoCapture(str(video))
        fps = capture.get(cv2.CAP_PROP_FPS) or 24.0
        index, size = 0, (0, 0)
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            if index == 0:
                size = (frame.shape[1], frame.shape[0])
            cv2.imwrite(str(frames_dir / f"{index:05d}.jpg"), frame)
            index += 1
        capture.release()
        return fps, index, size

    @staticmethod
    def _composite(frame: np.ndarray, mask: np.ndarray, background: str) -> np.ndarray:
        """Keep the character, drop everything else."""
        alpha = mask[..., None].astype(np.float32)
        if background == "blur":
            back = cv2.GaussianBlur(frame, (61, 61), 0) * 0.35
        else:
            back = np.zeros_like(frame, dtype=np.float32)
        return (frame * alpha + back * (1 - alpha)).astype(np.uint8)

    @staticmethod
    def _encode_rle(mask: np.ndarray) -> dict:
        rle = mask_utils.encode(np.asfortranarray(mask.astype(np.uint8)))
        rle["counts"] = rle["counts"].decode("ascii")
        return rle

    # ---------------------------------------------------------------- predict
    def predict(self, request: dict) -> dict:
        background = request.get("background", "dark")
        mask_format = request.get("mask_format", "rle")
        box, point = request.get("box"), request.get("point")
        if not box and not point:
            raise ValueError("Provide either `box` or `point` for the first frame")

        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            video = work / "in.mp4"
            video.write_bytes(base64.b64decode(request["video_b64"]))

            frames_dir = work / "frames"
            fps, frame_count, size = self._explode(video, frames_dir)
            if frame_count == 0:
                raise ValueError("No frames decoded -- is the clip a valid mp4?")

            # Offloading keeps a 20-40s clip inside an L4's 24GB.
            state = self._predictor.init_state(
                video_path=str(frames_dir),
                offload_video_to_cpu=True,
                offload_state_to_cpu=True,
            )

            # One prompt, first frame. SAM 2 tracks the character from there.
            if box:
                self._predictor.add_new_points_or_box(
                    inference_state=state, frame_idx=0, obj_id=1,
                    box=np.array(box, dtype=np.float32),
                )
            else:
                self._predictor.add_new_points_or_box(
                    inference_state=state, frame_idx=0, obj_id=1,
                    points=np.array([point], dtype=np.float32),
                    labels=np.array([1], dtype=np.int32),
                )

            masks: dict[int, np.ndarray] = {}
            for frame_idx, _obj_ids, logits in self._predictor.propagate_in_video(state):
                masks[frame_idx] = (logits[0] > 0.0).cpu().numpy().squeeze().astype(np.uint8)

            out_dir = work / "out"
            out_dir.mkdir()
            encoded, visible = [], []
            pixels = float(size[0] * size[1])

            for index in range(frame_count):
                frame = cv2.imread(str(frames_dir / f"{index:05d}.jpg"))
                mask = masks.get(index, np.zeros(frame.shape[:2], dtype=np.uint8))

                # An empty mask means SAM 2 lost the character: a cutaway.
                visible.append(bool(mask.sum() / pixels >= VISIBLE_MIN_AREA))
                cv2.imwrite(str(out_dir / f"{index:05d}.jpg"),
                            self._composite(frame, mask, background))

                if mask_format == "rle":
                    encoded.append(self._encode_rle(mask))
                else:
                    ok, buf = cv2.imencode(".png", mask * 255)
                    encoded.append(base64.b64encode(buf).decode() if ok else "")

            isolated = work / "isolated.mp4"
            subprocess.run(
                ["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps),
                 "-i", str(out_dir / "%05d.jpg"), "-c:v", "libx264",
                 "-pix_fmt", "yuv420p", str(isolated)],
                check=True,
            )

            return {
                "isolated_b64": base64.b64encode(isolated.read_bytes()).decode(),
                "masks": encoded if mask_format == "rle" else encoded,
                "mask_format": mask_format,
                "visible": visible,
                "fps": fps,
                "frame_count": frame_count,
                "size": list(size),
                "meta": json.dumps({"checkpoint": CHECKPOINT_REPO}),
            }
