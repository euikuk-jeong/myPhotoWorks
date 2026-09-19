"""Quality scoring (sharpness / exposure / colour) and weighted recommendation."""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from PIL import Image

TARGET_PIXELS = 200_000        # sharpness is measured at a fixed pixel count
SHARP_VAR_CEIL = 1000.0        # Laplacian variance mapped to 100 (log scale)
IDEAL_MEAN = 118.0
BLUR_ABS = 30.0                # sharpness below this is flagged as blur
BLUR_REL = 0.6                 # ...or below this share of the group's best
DEFAULT_WEIGHTS = (0.5, 0.3, 0.2)

Weights = tuple[float, float, float]


@dataclass(frozen=True)
class QualityScores:
    sharpness: float
    exposure: float
    color: float


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


def score_images(raw: Image.Image, corrected: Image.Image) -> QualityScores:
    """Sharpness from the uncorrected image, exposure/colour from the corrected one."""
    return QualityScores(sharpness_score(raw), exposure_score(corrected), color_score(corrected))


def normalize_weights(weights: Weights) -> Weights:
    w = [max(0.0, float(x)) for x in weights]
    total = sum(w)
    if total <= 0:
        return DEFAULT_WEIGHTS
    return (w[0] / total, w[1] / total, w[2] / total)


def composite(scores: QualityScores, weights: Weights) -> float:
    ws, we, wc = normalize_weights(weights)
    return ws * scores.sharpness + we * scores.exposure + wc * scores.color


def recommend(group: list[QualityScores], weights: Weights) -> int:
    """Index of the best photo in ``group`` (first wins ties)."""
    totals = [composite(s, weights) for s in group]
    return max(range(len(group)), key=lambda i: (totals[i], -i))


def is_blurry(scores: QualityScores, group: list[QualityScores]) -> bool:
    best = max(s.sharpness for s in group)
    return scores.sharpness < BLUR_ABS or (len(group) > 1 and scores.sharpness < BLUR_REL * best)


def explain(index: int, group: list[QualityScores], weights: Weights) -> str:
    """Short Korean reason label for why ``index`` is (or is not) the pick of its group."""
    s = group[index]
    if len(group) == 1:
        parts = ["단독 사진"]
    elif index == recommend(group, weights):
        parts = []
        if s.sharpness >= max(x.sharpness for x in group):
            parts.append("선명도 1위")
        parts.append("종합 1위")
    else:
        parts = [f"종합 {round(composite(s, weights))}점"]
    if is_blurry(s, group):
        parts.append("흐림")
    if s.exposure >= 75:
        parts.append("노출 양호")
    elif s.exposure < 45:
        parts.append("노출 부적절")
    return " · ".join(parts)
