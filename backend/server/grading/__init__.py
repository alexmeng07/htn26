"""Geometric grading: face and body scores measured from keypoints, never judged.

Pure functions over two keypoint timelines -- no I/O, no network, no model
calls -- so the same take always yields the same face and body score (I3).
Keypoints are extracted elsewhere: the browser during the take, prep for the
reference clip, `server/media/keypoints.py` as the server-side fallback.
"""

from server.grading.score import grade

__all__ = ["grade"]
