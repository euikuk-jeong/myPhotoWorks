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


# ---- stage 2: faces ------------------------------------------------------------------------

# A face box (analysis-copy pixels) that is far above the 3 % width rule and fills ~14 % of the
# frame width; ``PATCH`` above is the other box the scenes already use as a "subject".
FACE = (100, 80, 220, 200)


def blend(blink_l: float = 0.0, blink_r: float = 0.0,
          smile_l: float = 0.0, smile_r: float = 0.0) -> dict[str, float]:
    """MediaPipe face-blendshape dict with the four entries the algorithm reads."""
    return {"eyeBlinkLeft": blink_l, "eyeBlinkRight": blink_r,
            "mouthSmileLeft": smile_l, "mouthSmileRight": smile_r}


def face_summary(n: int = 1, closed: int = 0, smile: float = 0.0, sharp: float = 70.0,
                 exposure: float = 70.0, boxes=None):
    """``FaceSummary`` of ``n`` main faces (imported lazily)."""
    from myphotoworks.core.faces import FaceSummary

    if boxes is None:
        boxes = [(10 + 70 * i, 10, 70 + 70 * i, 70) for i in range(n)]
    return FaceSummary(boxes=tuple(tuple(b) for b in boxes), closed_eyes=closed, smile=smile,
                       sharpness=sharp, exposure=exposure)


def person(closed: int = 0, smile: float = 0.0, face_sharp: float = 70.0,
           face_exposure: float = 70.0, n: int | None = None, subject_sharp: float = 70.0,
           subject_exposure: float = 70.0, color: float = 60.0, **kw):
    """``QualityScores`` of a photo with ``n`` main faces (default: one, or as many as closed
    eyes). Subject values are independent of the face values on purpose: the person chain must
    read the face values."""
    n = n if n is not None else max(1, closed)
    return scores(subject_sharp, subject_exposure, color,
                  faces=face_summary(n, closed, smile, face_sharp, face_exposure), **kw)


class FakeFaceEngine:
    """Stand-in for the MediaPipe engine (``detect`` + ``blendshapes``), no model needed.

    ``detect`` returns ``boxes`` (analysis-copy pixels) for every photo. ``blendshapes`` answers
    from ``shapes`` in call order (main faces are handled in detector order, photos in the order
    they are analysed); when the list runs out it answers an open-eyed, neutral face. A ``None``
    entry simulates "landmarker found no face in the crop". Everything it was asked is recorded.
    """

    def __init__(self, boxes=(), shapes=(), fail_detect: bool = False, fail_blend: bool = False):
        self.boxes = [tuple(b) for b in boxes]
        self.shapes = list(shapes)
        self.fail_detect, self.fail_blend = fail_detect, fail_blend
        self.detect_shapes: list[tuple] = []      # (h, w, channels) of each detect() input
        self.detect_dtypes: list[str] = []
        self.crop_sizes: list[tuple[int, int]] = []   # (w, h) of each blendshapes() input

    def detect(self, rgb):
        self.detect_shapes.append(tuple(rgb.shape))
        self.detect_dtypes.append(str(rgb.dtype))
        if self.fail_detect:
            raise RuntimeError("detector exploded")
        return list(self.boxes)

    def blendshapes(self, rgb):
        self.crop_sizes.append((rgb.shape[1], rgb.shape[0]))
        if self.fail_blend:
            raise RuntimeError("landmarker exploded")
        k = len(self.crop_sizes) - 1
        return self.shapes[k] if k < len(self.shapes) else blend()


def box_with_area(area: float, x0: int = 0, y0: int = 0) -> tuple[int, int, int, int]:
    """Square box of (about) ``area`` square pixels."""
    side = round(area ** 0.5)
    return (x0, y0, x0 + side, y0 + side)

