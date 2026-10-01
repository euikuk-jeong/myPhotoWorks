"""Composition penalty for the recommendation chain (stage 3, pure NumPy, no Qt).

Two things are criticised: a tilted horizon / tilted lines (``estimate_tilt``) and main faces cut
by the frame (``cut_faces``). ``composition_score`` turns both into one 0..100 number, 100 meaning
nothing to criticise. The raw measurements live in ``QualityScores.tilt`` and
``FaceSummary.cut``; the score is derived on demand.
"""
from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from myphotoworks.core.subject import gradients

# ---- tunables (plan §7; tuned with the evaluation script on real photos) --------------------
TILT_FREE_DEG = 1.0            # a tilt up to this is not criticised (hand-held noise)
TILT_PENALTY_PER_DEG = 6.0     # score points lost per degree beyond the free zone
TILT_PENALTY_MAX = 60.0
TILT_BADGE_DEG = 3.0           # the "기울어짐" badge appears from this tilt
CUT_MARGIN_RATIO = 0.01        # a face this close to the frame edge (share of the size) is cut
CUT_PENALTY = 25.0             # points lost per cut face
CUT_PENALTY_MAX = 60.0

TILT_BLUR_SIGMA = 1.5          # smooths pixel staircases of slanted lines before measuring
TILT_EDGE_SHARE = 0.20         # the strongest 20 % of the pixels vote
TILT_MIN_EDGE = 15.0           # ... but only edges at least this strong (grey levels / px)
TILT_MIN_COHERENCE = 0.5       # below this the lines do not agree: no dominant direction
TILT_SEARCH_DEG = 15.0         # only lines this close to an axis vote; beyond that: a diagonal
_MIN_SIDE = 16


def _blur(gray: np.ndarray, sigma: float) -> np.ndarray:
    """Separable Gaussian blur (edge-replicated)."""
    r = max(1, int(round(3 * sigma)))
    x = np.arange(-r, r + 1)
    kernel = np.exp(-0.5 * (x / sigma) ** 2)
    kernel /= kernel.sum()
    out = gray
    for axis in (0, 1):
        pad = [(0, 0), (0, 0)]
        pad[axis] = (r, r)
        padded = np.pad(out, pad, mode="edge")
        n = out.shape[axis]
        if axis == 0:
            out = sum(k * padded[i:i + n, :] for i, k in enumerate(kernel))
        else:
            out = sum(k * padded[:, i:i + n] for i, k in enumerate(kernel))
    return out


def estimate_tilt(gray: np.ndarray) -> float | None:
    """Degrees by which the dominant straight lines of ``gray`` (2-D float array, 0..255) are off
    the nearest axis (horizontal or vertical), positive for counter-clockwise (lines rising to
    the right), in -45..45. ``None`` when there are no dominant lines (flat, noise, round shapes).

    Strong edges vote with their gradient direction folded to 90 degrees (a leaning building and
    a tilted horizon count alike); the votes are added as unit vectors of four times the angle,
    weighted by edge strength squared, so slanted-line staircase artefacts average out. Only
    lines within ``TILT_SEARCH_DEG`` of an axis vote: a staircase or roof edge at 20-45 degrees
    is a deliberate diagonal, not a tilt. Those lines still count in the strength the votes are
    measured against, so a scene dominated by diagonals - or with level and diagonal lines in
    equal measure - has no clear tilt. The result is trusted only when the votes agree
    (``TILT_MIN_COHERENCE``).
    """
    if min(gray.shape) < _MIN_SIDE:
        return None
    gx, gy = gradients(_blur(np.asarray(gray, dtype=np.float64), TILT_BLUR_SIGMA))
    mag = np.hypot(gx, gy)
    if mag.max() < TILT_MIN_EDGE:
        return None
    selected = mag >= max(float(np.quantile(mag, 1.0 - TILT_EDGE_SHARE)), TILT_MIN_EDGE)
    if selected.sum() < 50:
        return None
    phi = np.arctan2(gy[selected], gx[selected])
    weight = mag[selected] ** 2
    off_axis = np.degrees(phi) + 45.0                      # degrees from the nearest axis ...
    off_axis = off_axis % 90.0 - 45.0                      # ... folded into -45..45
    near = np.abs(off_axis) <= TILT_SEARCH_DEG
    vote = np.sum(weight[near] * np.exp(4j * phi[near]))
    if abs(vote) / weight.sum() < TILT_MIN_COHERENCE:
        return None
    return float(-np.degrees(np.angle(vote)) / 4.0)


def cut_faces(boxes: Sequence[tuple[int, int, int, int]], image_size: tuple[int, int]) -> int:
    """How many face boxes touch the frame edge (within ``CUT_MARGIN_RATIO`` of the size)."""
    w, h = image_size
    mx, my = CUT_MARGIN_RATIO * w, CUT_MARGIN_RATIO * h
    return sum(1 for x0, y0, x1, y1 in boxes
               if x0 <= mx or y0 <= my or x1 >= w - mx or y1 >= h - my)


def composition_score(tilt: float | None, cut_faces: int = 0) -> float:
    """0..100, 100 = nothing to criticise. A tilt beyond ``TILT_FREE_DEG`` (either direction, an
    unknown tilt counts as none) and every face cut by the frame cost points."""
    tilt_loss = 0.0 if tilt is None else min(
        TILT_PENALTY_MAX, TILT_PENALTY_PER_DEG * max(0.0, abs(tilt) - TILT_FREE_DEG))
    cut_loss = min(CUT_PENALTY_MAX, CUT_PENALTY * max(0, cut_faces))
    return max(0.0, 100.0 - tilt_loss - cut_loss)
