"""Synthetic images for recommendation v2 tests (NumPy gray arrays, deterministic seeds).

Not a test module. The helpers never import ``myphotoworks`` so they work before the
code under test exists.
"""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageFilter

H, W = 384, 512  # analysis copies are at most 512 px on the long side


def texture(h: int = H, w: int = W, seed: int = 0, cell: int = 4) -> np.ndarray:
    """High-contrast blocky gray texture, values 0..255 (strong edges everywhere)."""
    rng = np.random.default_rng(seed)
    small = rng.random((h // cell, w // cell)) * 255
    return np.kron(small, np.ones((cell, cell)))[:h, :w]


def blur(a: np.ndarray, sigma: float) -> np.ndarray:
    img = Image.fromarray(np.clip(a, 0, 255).astype("uint8"))
    return np.asarray(img.filter(ImageFilter.GaussianBlur(sigma)), dtype=np.float64)


def motion_blur_x(a: np.ndarray, length: int = 15) -> np.ndarray:
    """Average along the horizontal axis only (simulates horizontal camera shake)."""
    kernel = np.ones(length) / length
    padded = np.pad(a, ((0, 0), (length // 2, length - 1 - length // 2)), mode="edge")
    return np.apply_along_axis(lambda r: np.convolve(r, kernel, mode="valid"), 1, padded)


def add_grain(a: np.ndarray, sigma: float = 14.0, seed: int = 1) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return np.clip(a + rng.normal(0.0, sigma, a.shape), 0, 255)


# Subject patch used by the shallow-depth-of-field and backlit scenes: x0, y0, x1, y1
PATCH = (300, 120, 440, 260)


def shallow_dof(seed: int = 0, bg_sigma: float = 6.0) -> np.ndarray:
    """Sharp subject patch on a strongly defocused background."""
    base = texture(seed=seed)
    out = blur(base, bg_sigma)
    x0, y0, x1, y1 = PATCH
    out[y0:y1, x0:x1] = base[y0:y1, x0:x1]
    return out


def backlit(bg: float = 252.0, subject_mean: float = 118.0, seed: int = 0) -> np.ndarray:
    """Blown-out background with a textured mid-tone subject patch."""
    out = np.full((H, W), bg, dtype=np.float64)
    x0, y0, x1, y1 = PATCH
    tex = texture(y1 - y0, x1 - x0, seed=seed)
    out[y0:y1, x0:x1] = np.clip(subject_mean + (tex - 127.5) * 0.25, 0, 255)
    return out


def midtone_scene(seed: int = 0, mean: float = 118.0) -> np.ndarray:
    """Mid-grey background with the same subject patch as ``backlit``."""
    out = backlit(bg=mean, subject_mean=mean, seed=seed)
    return out


def to_rgb_image(gray: np.ndarray) -> Image.Image:
    return Image.fromarray(np.clip(gray, 0, 255).astype("uint8")).convert("RGB")


def scores(sharp: float = 70.0, exposure: float = 70.0, color: float = 60.0, **kw):
    """``QualityScores`` built with the v2 field names (imported lazily so a missing field
    fails the individual test, not the collection)."""
    from myphotoworks.core.scoring import QualityScores

    return QualityScores(subject_sharpness=sharp, subject_exposure=exposure, color=color, **kw)
