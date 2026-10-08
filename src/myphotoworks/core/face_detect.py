"""Finding faces in a photo: small ones in tiles, false ones dropped (pure given an engine).

The BlazeFace short-range detector shrinks what it is shown to 128 px, so on the whole frame a
face under about a tenth of the width is invisible, and its false positives (a display panel, a
shadow-play screen, a camera lens) score 0.52 - 0.67. In an overlapping tile of a larger decode
the same small face scores 0.85 - 0.97 and the false ones stay weak or vanish (dev8 review).

``detect_faces(path, raw, engine)``:

1. detect on the whole frame (``raw``, the analysis copy); a detection counts from
   ``MIN_FACE_SCORE`` while its box is at most ``MAX_FACE_WIDTH_RATIO`` of the frame wide (a
   "face" over the half of the frame is a pattern);
2. unless the whole frame found faces and every one of its detections was kept and is
   ``STRONG_FACE_SCORE`` or more (a weak or dropped detection means "look closer"), decode the
   photo at ``TILE_LONG_SIDE`` and search ``tile_rects`` as well (a failing decode keeps the
   whole-frame result); a tile detection cut by an inner tile edge is half a face and is
   ignored (the overlapping neighbour tile has it whole);
3. merge overlapping boxes (``nms``): the higher score wins.

An engine offers ``detect_scored(rgb) -> [(box, score)]``; one with only ``detect`` gives boxes
that count as score 1.0 (so no tiles).
"""
from __future__ import annotations

import logging
import math
from collections.abc import Sequence
from pathlib import Path

import numpy as np
from PIL import Image

from myphotoworks.core.analysis_image import load_analysis_image
from myphotoworks.core.faces import Box, FaceEngine

logger = logging.getLogger(__name__)

# ---- tunables (dev8 review, 2026-10-05: true faces 0.78 - 0.97 in tiles, false ones 0.52 - 0.67)
MIN_FACE_SCORE = 0.7            # a detection below this is not a face
STRONG_FACE_SCORE = 0.8         # a whole-frame detection this sure makes the tiles unnecessary
MAX_FACE_WIDTH_RATIO = 0.45     # a box wider than this share of the frame is not a face
TILE_FRACTION = 0.5             # a tile is this share of the frame in each direction
TILE_OVERLAP = 0.5              # neighbouring tiles overlap by this share (3 x 3 tiles)
TILE_LONG_SIDE = 2048           # the photo is decoded this large for the tiles
NMS_IOU = 0.3                   # boxes overlapping this much are the same face
_EDGE_MARGIN = 0.01             # "touches the tile edge": within this share of the tile size

Scored = tuple[Box, float]


def tile_rects(
    size: tuple[int, int], fraction: float = TILE_FRACTION, overlap: float = TILE_OVERLAP
) -> list[Box]:
    """Tiles of ``fraction`` of the frame, evenly spread so that neighbours overlap by at least
    ``overlap`` and the last tiles end at the frame edges (row by row)."""
    w, h = size

    def starts(total: int, tile: int) -> list[int]:
        if tile >= total:
            return [0]
        n = math.ceil((total - tile) / (tile * (1 - overlap)) - 1e-9) + 1
        return [round(i * (total - tile) / (n - 1)) for i in range(n)]

    tw, th = math.ceil(w * fraction), math.ceil(h * fraction)
    return [(x, y, x + tw, y + th) for y in starts(h, th) for x in starts(w, tw)]


def box_iou(a: Box, b: Box) -> float:
    iw = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    ih = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = iw * ih
    union = ((a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter)
    return inter / union if union > 0 else 0.0


def nms(detections: Sequence[Scored], iou: float = NMS_IOU) -> list[Scored]:
    """Highest score first; a box overlapping a kept one by ``iou`` or more is dropped."""
    kept: list[Scored] = []
    for box, score in sorted(detections, key=lambda d: -d[1]):
        if all(box_iou(box, k[0]) < iou for k in kept):
            kept.append((box, score))
    return kept


def cut_by_tile_edge(
    box: Box, tile: Box, frame: tuple[int, int], margin: float = _EDGE_MARGIN
) -> bool:
    """True when ``box`` (frame pixels) touches an edge of ``tile`` that is not an edge of the
    frame: the tile shows only part of that face."""
    tol = max(2.0, margin * max(tile[2] - tile[0], tile[3] - tile[1]))
    return ((tile[0] > 0 and box[0] <= tile[0] + tol)
            or (tile[1] > 0 and box[1] <= tile[1] + tol)
            or (tile[2] < frame[0] and box[2] >= tile[2] - tol)
            or (tile[3] < frame[1] and box[3] >= tile[3] - tol))


def _scored(engine: FaceEngine, rgb: np.ndarray) -> list[Scored]:
    detect_scored = getattr(engine, "detect_scored", None)
    if detect_scored is not None:
        return [(tuple(b), float(s)) for b, s in detect_scored(rgb)]
    return [(tuple(b), 1.0) for b in engine.detect(rgb)]


def _keep(detections: Sequence[Scored], size: tuple[int, int]) -> list[Scored]:
    """Boxes clipped to the frame; weak, empty and over-wide ones dropped."""
    w, h = size
    kept = []
    for (x0, y0, x1, y1), score in detections:
        box = (max(0, x0), max(0, y0), min(w, x1), min(h, y1))
        if (score >= MIN_FACE_SCORE and box[2] > box[0] and box[3] > box[1]
                and box[2] - box[0] <= MAX_FACE_WIDTH_RATIO * w):
            kept.append((box, score))
    return kept


def _tile_detections(path: Path, size: tuple[int, int], engine: FaceEngine) -> list[Scored]:
    """Detections in the tiles of a ``TILE_LONG_SIDE`` decode, mapped to the pixels of the
    ``size`` frame."""
    big: Image.Image = load_analysis_image(path, TILE_LONG_SIDE)
    bw, bh = big.size
    kx, ky = size[0] / bw, size[1] / bh
    pixels = np.asarray(big)
    found: list[Scored] = []
    for tile in tile_rects((bw, bh)):
        x0, y0, x1, y1 = tile
        for (a, b, c, d), score in _scored(engine, pixels[y0:y1, x0:x1]):
            box = (a + x0, b + y0, c + x0, d + y0)
            if cut_by_tile_edge(box, tile, (bw, bh)):
                continue
            found.append(((round(box[0] * kx), round(box[1] * ky),
                           round(box[2] * kx), round(box[3] * ky)), score))
    return _keep(found, size)


def detect_faces(path: Path, raw: Image.Image, engine: FaceEngine) -> list[Box]:
    """Face boxes in the pixels of ``raw`` (see the module text). Raises what the engine raises;
    the caller treats that as "no faces"."""
    found = _scored(engine, np.asarray(raw))
    whole = _keep(found, raw.size)
    if found and len(whole) == len(found) and all(s >= STRONG_FACE_SCORE for _, s in whole):
        return [box for box, _ in nms(whole)]
    try:
        tiles = _tile_detections(path, raw.size, engine)
    except Exception as e:
        logger.warning("tiled face detection failed for %s: %s", path, e)
        tiles = []
    return [box for box, _ in nms(whole + tiles)]
