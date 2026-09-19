"""The replay compositor's pure parts: mask decoding and placement smoothing.

The compositing itself needs video and the pose model, so it is exercised by a
real round, not here. SAM 2 masks arrive as COCO compressed RLE; the decoder is
checked against an encoder written from pycocotools' rleToString, so the test
needs neither pycocotools nor a clip.
"""

from __future__ import annotations

import numpy as np

from server.media.composite import _bbox, _placed, _smooth, decode_rle


def encode_rle(mask: np.ndarray) -> dict:
    """COCO compressed RLE, as pycocotools writes it (column-major runs, 0s first)."""
    flat = mask.T.reshape(-1)
    counts, current, run = [], 0, 0
    for v in flat:
        if v != current:
            counts.append(run)
            current, run = v, 0
        run += 1
    counts.append(run)
    out = []
    for i, x in enumerate(counts):
        if i > 2:
            x -= counts[i - 2]
        more = True
        while more:
            c = x & 0x1F
            x >>= 5
            more = (x != -1) if (c & 0x10) else (x != 0)
            if more:
                c |= 0x20
            out.append(chr(c + 48))
    return {"size": list(mask.shape), "counts": "".join(out)}


def test_rle_round_trip():
    rng = np.random.default_rng(7)
    mask = np.zeros((72, 128), dtype=np.uint8)
    mask[10:60, 30:90] = 1  # a person-ish block
    mask[rng.random(mask.shape) < 0.05] ^= 1  # ragged edges, runs that shrink and grow
    assert np.array_equal(decode_rle(encode_rle(mask)), mask)


def test_rle_empty_and_full():
    for mask in (np.zeros((9, 16), np.uint8), np.ones((9, 16), np.uint8)):
        assert np.array_equal(decode_rle(encode_rle(mask)), mask)


def test_bbox_and_smoothing():
    mask = np.zeros((10, 10), np.uint8)
    mask[2:5, 3:8] = 1
    assert _bbox(mask) == (3.0, 2.0, 8.0, 5.0)
    assert _bbox(np.zeros((4, 4))) is None
    assert _smooth(None, (0, 0, 4, 4)) == (0, 0, 4, 4)
    assert _smooth((0, 0, 4, 4), None) == (0, 0, 4, 4)
    moved = _smooth((0.0, 0.0, 4.0, 4.0), (4.0, 4.0, 8.0, 8.0))
    assert all(0 < a < b for a, b in zip(moved, (4, 4, 8, 8), strict=True))


def test_player_points_follow_the_cut_out_into_the_replay():
    # Cut-out pasted at (300, 100), scaled to 640x360, in a 1280x720 replay.
    at = (300, 100, 640, 360, 1280, 720)
    assert _placed(0.0, 0.0, at) == [round(300 / 1280, 4), round(100 / 720, 4)]
    assert _placed(1.0, 1.0, at) == [round(940 / 1280, 4), round(460 / 720, 4)]
    assert _placed(0.5, 0.5, at) == [0.4844, 0.3889]
