"""Environment check: do the MediaPipe landmarkers construct and run here?

Resolving wheels proves nothing about whether the native TFLite delegate loads,
so this builds both tasks and runs them on a synthetic frame. Run by
setup-grading.ps1; useful on any new development machine.

Expected output: both landmarkers OK with zero detections on a grey frame. Zero
is the correct answer -- it shows inference ran and returned empty results
rather than raising, which is the no-person-detected path grading relies on.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
MODELS = ROOT / "assets" / "models"


def main() -> int:
    import mediapipe as mp
    import numpy as np

    print(f"mediapipe {mp.__version__}")
    print(f"numpy     {np.__version__}")

    from mediapipe.tasks import python as mp_python
    from mediapipe.tasks.python import vision

    # A mid-grey frame. We expect NO detections -- the point is that inference
    # runs and returns empty results rather than throwing.
    frame = np.full((720, 1280, 3), 128, dtype=np.uint8)
    image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame)

    pose_path = MODELS / "pose_landmarker_full.task"
    face_path = MODELS / "face_landmarker.task"
    for path in (pose_path, face_path):
        if not path.exists():
            print(f"MISSING MODEL: {path}")
            return 1

    pose_options = vision.PoseLandmarkerOptions(
        base_options=mp_python.BaseOptions(model_asset_path=str(pose_path)),
        running_mode=vision.RunningMode.VIDEO,
    )
    with vision.PoseLandmarker.create_from_options(pose_options) as pose:
        result = pose.detect_for_video(image, 0)
        print(f"pose landmarker OK, poses detected on grey frame: {len(result.pose_landmarks)}")

    face_options = vision.FaceLandmarkerOptions(
        base_options=mp_python.BaseOptions(model_asset_path=str(face_path)),
        running_mode=vision.RunningMode.VIDEO,
        output_face_blendshapes=True,
    )
    with vision.FaceLandmarker.create_from_options(face_options) as face:
        result = face.detect_for_video(image, 0)
        print(f"face landmarker OK, faces detected on grey frame: {len(result.face_landmarks)}")
        print(f"blendshapes available: {bool(result.face_blendshapes)}")

    print("PROBE OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
