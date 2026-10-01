"""Subject region detection on a small grayscale analysis copy (pure NumPy, no Qt).

Chain: main faces (stage 2) -> sharpest area -> centre. Later stages insert more sources (AF
point) in front of the sharpest area, so callers only depend on ``SubjectRegion`` and its
``source`` label.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

GRID = 16                  # the image is cut into GRID x GRID cells to find the sharpest area
GROW_RATIO = 0.5           # neighbouring cells join when their edge energy >= this share of the max
MIN_CONFIDENCE = 0.5       # below this the scene is evenly sharp (or flat): fall back to the centre
CENTER_FRACTION = 0.6      # the centre fallback covers this share of each side


@dataclass(frozen=True)
class SubjectRegion:
    """Where the subject is. ``bbox`` = (x0, y0, x1, y1) in pixels, x1/y1 exclusive."""

    bbox: tuple[int, int, int, int]
    source: str            # "face" | "sharpest" | "center"
    confidence: float      # 0..1


def downsample2(gray: np.ndarray) -> np.ndarray:
    """2x2 mean: halves the size and averages away most pixel-level noise / film grain."""
    h, w = gray.shape[0] // 2 * 2, gray.shape[1] // 2 * 2
    g = gray[:h, :w]
    return (g[0::2, 0::2] + g[1::2, 0::2] + g[0::2, 1::2] + g[1::2, 1::2]) / 4.0


def gradients(gray: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Sobel gradients scaled to grey levels per pixel (a 0->255 step reads about 128)."""
    p = np.pad(gray, 1, mode="edge")
    gx = (p[:-2, 2:] + 2 * p[1:-1, 2:] + p[2:, 2:]) - (p[:-2, :-2] + 2 * p[1:-1, :-2] + p[2:, :-2])
    gy = (p[2:, :-2] + 2 * p[2:, 1:-1] + p[2:, 2:]) - (p[:-2, :-2] + 2 * p[:-2, 1:-1] + p[:-2, 2:])
    return gx / 8.0, gy / 8.0


def _center_box(h: int, w: int) -> tuple[int, int, int, int]:
    mx, my = round(w * (1 - CENTER_FRACTION) / 2), round(h * (1 - CENTER_FRACTION) / 2)
    return mx, my, max(mx + 1, w - mx), max(my + 1, h - my)


def _face_region(h: int, w: int, face_boxes) -> SubjectRegion | None:
    """Union of the face boxes clipped to the image, or ``None`` when no box is inside it."""
    clipped = [(max(0, x0), max(0, y0), min(w, x1), min(h, y1)) for x0, y0, x1, y1 in face_boxes]
    clipped = [b for b in clipped if b[2] > b[0] and b[3] > b[1]]
    if not clipped:
        return None
    bbox = (min(b[0] for b in clipped), min(b[1] for b in clipped),
            max(b[2] for b in clipped), max(b[3] for b in clipped))
    return SubjectRegion(bbox, "face", 1.0)


def detect_subject(gray: np.ndarray, face_boxes=None) -> SubjectRegion:
    """Find the subject of ``gray`` (2-D float array, 0..255).

    Main-face boxes (``face_boxes``, pixels of ``gray``) win: the subject is their union.
    Otherwise it is the sharpest area: cells are ranked by mean gradient magnitude; cells
    connected to the strongest one with at least ``GROW_RATIO`` of its energy form the subject.
    Confidence is how far the strongest cell stands out from the typical one
    (1 - median / max), so a pan-focus scene where everything is equally sharp scores low and
    falls back to the centre.
    """
    h, w = gray.shape
    if face_boxes:
        region = _face_region(h, w, face_boxes)
        if region is not None:
            return region
    small = downsample2(gray)
    sh, sw = small.shape
    if sh < 2 or sw < 2:
        return SubjectRegion((0, 0, w, h), "center", 0.0)
    gx, gy = gradients(small)
    mag = np.hypot(gx, gy)

    grid = max(1, min(GRID, sh, sw))
    ys = np.linspace(0, sh, grid + 1).astype(int)
    xs = np.linspace(0, sw, grid + 1).astype(int)
    energy = np.array([[mag[ys[i]:ys[i + 1], xs[j]:xs[j + 1]].mean() for j in range(grid)]
                       for i in range(grid)])
    peak = float(energy.max())
    if peak <= 1e-6:
        return SubjectRegion(_center_box(h, w), "center", 0.0)
    confidence = float(np.clip(1.0 - np.median(energy) / peak, 0.0, 1.0))
    if confidence < MIN_CONFIDENCE:
        return SubjectRegion(_center_box(h, w), "center", confidence)

    keep = energy >= GROW_RATIO * peak
    seed = tuple(int(v) for v in np.unravel_index(int(energy.argmax()), energy.shape))
    region = np.zeros_like(keep)
    stack = [seed]
    while stack:
        i, j = stack.pop()
        if region[i, j] or not keep[i, j]:
            continue
        region[i, j] = True
        for a, b in ((i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1)):
            if 0 <= a < grid and 0 <= b < grid:
                stack.append((a, b))
    rows, cols = np.where(region)
    x0, x1 = xs[cols.min()] * w / sw, xs[cols.max() + 1] * w / sw
    y0, y1 = ys[rows.min()] * h / sh, ys[rows.max() + 1] * h / sh
    bbox = (int(round(x0)), int(round(y0)), max(int(round(x0)) + 1, int(round(x1))),
            max(int(round(y0)) + 1, int(round(y1))))
    return SubjectRegion(bbox, "sharpest", confidence)
