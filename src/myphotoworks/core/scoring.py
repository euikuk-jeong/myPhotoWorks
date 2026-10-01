"""Quality scores: subject-based sharpness / exposure (v2) next to the legacy whole-frame ones.

``QualityScores.sharpness`` / ``exposure`` are the v1.4 whole-frame values. The app does not
compute them; only the evaluation replay (``dev/eval_metrics.score_file``) fills them so the
``baseline`` algorithm can still be measured. The recommendation itself (``core/ranking.py``)
reads ``subject_sharpness`` / ``subject_exposure`` / ``color``.
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace

import numpy as np
from PIL import Image

from myphotoworks.core.faces import (
    Box,
    FaceMeasure,
    FaceSummary,
    eye_closed,
    smile_value,
    summarize_faces,
    weighted_mean,
)
from myphotoworks.core.subject import SubjectRegion, detect_subject, downsample2, gradients

TARGET_PIXELS = 200_000        # analysis copies are normalised to this pixel count
SHARP_VAR_CEIL = 1000.0        # legacy: Laplacian variance mapped to 100 (log scale)
IDEAL_MEAN = 118.0
BLUR_ABS = 30.0                # subject sharpness below this is flagged as blur
BLUR_REL = 0.6                 # ...or below this share of the group's best
DEFAULT_WEIGHTS = (0.5, 0.3, 0.2)   # legacy baseline weights
ALGORITHM_VERSION = "v2-stage2"  # recorded in exported labels; bump when scoring changes

SHARP_TOP_PERCENT = 2.0        # share of strongest edge pixels averaged for subject sharpness
SHARP_GRAD_CEIL = 150.0        # gradient (grey levels / px at half resolution) mapped to 100

Weights = tuple[float, float, float]


@dataclass(frozen=True)
class QualityScores:
    # legacy whole-frame scores (filled by the evaluation replay only; 0 in the app)
    sharpness: float = 0.0
    exposure: float = 0.0
    color: float = 0.0
    # v2 subject-based scores
    subject_sharpness: float = 0.0
    subject_exposure: float = 0.0
    subject_source: str = "center"   # which SubjectRegion source produced the numbers above
    motion_ratio: float = 1.0        # 0 = one-directional smear (shake), 1 = isotropic; stored only
    # subject box in the pixel-normalised analysis copy, so a correction change can re-measure
    # the subject's exposure without detecting the subject (or decoding) again
    subject_bbox: tuple[int, int, int, int] | None = None
    # main faces of the photo (same pixel grid as ``subject_bbox``); None = no portrait
    faces: FaceSummary | None = None


def _normalize_pixels(img: Image.Image) -> Image.Image:
    w, h = img.size
    if w * h <= TARGET_PIXELS:
        return img
    scale = math.sqrt(TARGET_PIXELS / (w * h))
    return img.resize(
        (max(1, round(w * scale)), max(1, round(h * scale))), Image.Resampling.LANCZOS
    )


def sharpness_score(img: Image.Image) -> float:
    """0..100 from the variance of the Laplacian on a pixel-count-normalised copy."""
    g = np.asarray(_normalize_pixels(img).convert("L"), dtype=np.float64)
    if g.shape[0] < 3 or g.shape[1] < 3:
        return 0.0
    lap = g[:-2, 1:-1] + g[2:, 1:-1] + g[1:-1, :-2] + g[1:-1, 2:] - 4.0 * g[1:-1, 1:-1]
    var = float(lap.var())
    return 100.0 * min(1.0, math.log1p(var) / math.log1p(SHARP_VAR_CEIL))


def exposure_score(img: Image.Image) -> float:
    """0..100: penalise mean luminance far from mid-grey and clipped shadows/highlights."""
    g = np.asarray(img.convert("L"), dtype=np.float64)
    deviation = abs(float(g.mean()) - IDEAL_MEAN) / IDEAL_MEAN
    clipped = float(((g < 5) | (g > 250)).mean())
    return 100.0 * max(0.0, 1.0 - min(1.0, 0.7 * deviation + 3.0 * clipped))


def color_score(img: Image.Image) -> float:
    """0..100 from the Hasler-Suesstrunk colourfulness metric."""
    a = np.asarray(img.convert("RGB"), dtype=np.float64)
    rg = a[:, :, 0] - a[:, :, 1]
    yb = 0.5 * (a[:, :, 0] + a[:, :, 1]) - a[:, :, 2]
    colorfulness = math.hypot(rg.std(), yb.std()) + 0.3 * math.hypot(rg.mean(), yb.mean())
    return min(100.0, colorfulness / 60.0 * 100.0)


def _normalized_size(size: tuple[int, int]) -> tuple[int, int]:
    """Size ``_normalize_pixels`` would give an image of ``size``."""
    w, h = size
    if w * h <= TARGET_PIXELS:
        return size
    scale = math.sqrt(TARGET_PIXELS / (w * h))
    return max(1, round(w * scale)), max(1, round(h * scale))


def _crop(gray: np.ndarray, region: SubjectRegion) -> np.ndarray:
    x0, y0, x1, y1 = region.bbox
    h, w = gray.shape
    return gray[max(0, y0):max(1, min(h, y1)), max(0, x0):max(1, min(w, x1))]


def _subject_gradients(gray: np.ndarray, region: SubjectRegion):
    """Gradients of the 2x2-averaged subject crop, or ``None`` when it is too small to have any."""
    small = downsample2(_crop(gray, region))
    return gradients(small) if small.size else None


def subject_sharpness(gray: np.ndarray, region: SubjectRegion) -> float:
    """0..100 edge strength of the subject: mean of the strongest gradients inside ``region``.

    The region is averaged 2x2 first and only the top ``SHARP_TOP_PERCENT`` % of the gradient
    magnitudes count, so film grain (uniform, weak after averaging) hardly lifts an out-of-focus
    shot, while a sharp subject on a blurred background is judged by the subject alone.
    ``gray`` is an analysis copy (long side <= ~512 px); values are scale dependent. A subject
    crop under 2x2 px has no measurable edges and scores 0.
    """
    grads = _subject_gradients(gray, region)
    if grads is None:
        return 0.0
    mag = np.hypot(*grads).ravel()
    k = max(1, int(round(mag.size * SHARP_TOP_PERCENT / 100.0)))
    top = float(np.partition(mag, mag.size - k)[mag.size - k:].mean())
    return 100.0 * min(1.0, math.sqrt(top / SHARP_GRAD_CEIL))


def motion_ratio(gray: np.ndarray, region: SubjectRegion) -> float:
    """0..1 ratio of the weaker to the stronger directional gradient energy of the subject.

    Camera shake smears detail along one direction, which drives the ratio towards 0; an
    isotropic texture gives about 1. Flat or too small input has no direction and returns 1.
    """
    grads = _subject_gradients(gray, region)
    if grads is None:
        return 1.0
    gx, gy = grads
    ex, ey = float((gx * gx).sum()), float((gy * gy).sum())
    hi = max(ex, ey)
    return 1.0 if hi <= 1e-9 else min(ex, ey) / hi


def subject_exposure(gray: np.ndarray, region: SubjectRegion) -> float:
    """0..100 exposure of the subject only: mean far from mid-grey and clipping *inside* it
    cost points; a blown-out background or deep shadows elsewhere do not."""
    g = _crop(gray, region)
    deviation = abs(float(g.mean()) - IDEAL_MEAN) / IDEAL_MEAN
    clipped = float(((g < 5) | (g > 250)).mean())
    return 100.0 * max(0.0, 1.0 - min(1.0, 0.7 * deviation + 3.0 * clipped))


def _gray_on_grid(img: Image.Image, size: tuple[int, int]) -> np.ndarray:
    """Float grey copy of ``img`` on the pixel grid ``size`` (the normalised analysis size)."""
    fixed = img if img.size == size else img.resize(size, Image.Resampling.LANCZOS)
    return np.asarray(fixed.convert("L"), dtype=np.float64)


def _scale_box(box: Box, src: tuple[int, int], dst: tuple[int, int]) -> Box | None:
    """``box`` moved from the pixel grid ``src`` to ``dst`` and clamped to it; None if empty."""
    sx, sy = dst[0] / src[0], dst[1] / src[1]
    x0, y0 = max(0, round(box[0] * sx)), max(0, round(box[1] * sy))
    x1, y1 = min(dst[0], round(box[2] * sx)), min(dst[1], round(box[3] * sy))
    return (x0, y0, x1, y1) if x1 > x0 and y1 > y0 else None


def _face_summary(
    gray: np.ndarray, gray_corrected: np.ndarray, faces: Sequence[tuple[Box, Mapping | None]]
) -> FaceSummary:
    """Face sharpness from the uncorrected grey copy, face exposure from the corrected one; eyes
    and smile from the blendshapes (``None`` = the landmarker saw nothing: neutral, eyes open)."""
    measures = []
    for box, shapes in faces:
        region = SubjectRegion(box, "face", 1.0)
        shapes = shapes or {}
        measures.append(FaceMeasure(
            box, eye_closed(shapes), smile_value(shapes),
            subject_sharpness(gray, region), subject_exposure(gray_corrected, region)))
    return summarize_faces(measures)


def score_images(
    raw: Image.Image,
    corrected: Image.Image,
    faces: Sequence[tuple[Box, Mapping | None]] = (),
) -> QualityScores:
    """Subject sharpness / motion from the uncorrected image, subject exposure and colour from
    the corrected one. The subject is found once on the uncorrected copy. The legacy whole-frame
    ``sharpness`` / ``exposure`` stay 0 here; only the evaluation replay fills them.

    ``faces`` are the main faces as ``(box in the pixels of raw, blendshapes or None)``; with any,
    they are the subject and ``QualityScores.faces`` is filled."""
    small = _normalize_pixels(raw)
    gray = np.asarray(small.convert("L"), dtype=np.float64)
    grid = [(b, shapes) for b, shapes in
            ((_scale_box(box, raw.size, small.size), shapes) for box, shapes in faces)
            if b is not None]
    region = detect_subject(gray, [b for b, _ in grid])
    gray_corrected = _gray_on_grid(corrected, small.size)
    return QualityScores(
        color=color_score(corrected),
        subject_sharpness=subject_sharpness(gray, region),
        subject_exposure=subject_exposure(gray_corrected, region),
        subject_source=region.source,
        motion_ratio=motion_ratio(gray, region),
        subject_bbox=region.bbox,
        faces=_face_summary(gray, gray_corrected, grid) if grid else None,
    )


def rescore_corrected(
    old: QualityScores, raw: Image.Image, corrected: Image.Image
) -> QualityScores:
    """New subject / face exposure and colour after the correction settings changed. Everything
    measured on the uncorrected image (sharpness, subject, motion, eyes, smile) is kept."""
    gray = _gray_on_grid(corrected, _normalized_size(raw.size))
    h, w = gray.shape
    x0, y0, x1, y1 = old.subject_bbox or (0, 0, w, h)
    region = SubjectRegion((x0, y0, x1, y1), old.subject_source, 1.0)
    faces = old.faces
    if faces is not None:
        exposures = [subject_exposure(gray, SubjectRegion(b, "face", 1.0)) for b in faces.boxes]
        faces = replace(faces, exposure=weighted_mean(exposures, faces.boxes))
    return replace(
        old,
        color=color_score(corrected),
        subject_exposure=subject_exposure(gray, region),
        faces=faces,
    )


def normalize_weights(weights: Weights) -> Weights:
    w = [max(0.0, float(x)) for x in weights]
    total = sum(w)
    if total <= 0:
        return DEFAULT_WEIGHTS
    return (w[0] / total, w[1] / total, w[2] / total)


def composite(scores: QualityScores, weights: Weights) -> float:
    """Legacy (v1.4) weighted sum of the whole-frame scores; used by the baseline replay."""
    ws, we, wc = normalize_weights(weights)
    return ws * scores.sharpness + we * scores.exposure + wc * scores.color


def recommend(group: list[QualityScores], weights: Weights) -> int:
    """Legacy (v1.4) pick: index of the best weighted sum, first wins ties (baseline replay)."""
    totals = [composite(s, weights) for s in group]
    return max(range(len(group)), key=lambda i: (totals[i], -i))


def _sharpness_of(s: QualityScores) -> float:
    return s.faces.sharpness if s.faces else s.subject_sharpness


def is_blurry(scores: QualityScores, group: list[QualityScores]) -> bool:
    """Blur flag: sharpness below ``BLUR_ABS``, or below ``BLUR_REL`` of the best of its peers.
    Peers are the photos measured the same way: in a group with faces, photos with a face compare
    their face sharpness with each other and photos without a face compare their subject
    sharpness with each other (the two regions are not comparable)."""
    peers = [s for s in group if bool(s.faces) == bool(scores.faces)]
    value, best = _sharpness_of(scores), max(_sharpness_of(s) for s in peers)
    return value < BLUR_ABS or (len(peers) > 1 and value < BLUR_REL * best)
