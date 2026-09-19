"""Visual similarity: dHash + colour histogram. Pure Pillow/NumPy."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image

HASH_SIZE = 8
HIST_BINS = 8
HASH_WEIGHT = 0.6  # remainder goes to the colour histogram


@dataclass(eq=False)
class Signature:
    hash_bits: np.ndarray  # bool, HASH_SIZE * HASH_SIZE
    hist: np.ndarray       # float, 3 * HIST_BINS, each channel sums to 1


def dhash(img: Image.Image, size: int = HASH_SIZE) -> np.ndarray:
    """Difference hash: left-to-right brightness gradient on a (size+1) x size grid."""
    gray = img.convert("L").resize((size + 1, size), Image.Resampling.LANCZOS)
    a = np.asarray(gray, dtype=np.int16)
    return (a[:, 1:] > a[:, :-1]).ravel()


def color_hist(img: Image.Image, bins: int = HIST_BINS) -> np.ndarray:
    small = np.asarray(img.convert("RGB").resize((64, 64), Image.Resampling.BILINEAR))
    out = []
    for c in range(3):
        h, _ = np.histogram(small[:, :, c], bins=bins, range=(0, 256))
        out.append(h / h.sum())
    return np.concatenate(out)


def compute_signature(img: Image.Image) -> Signature:
    return Signature(hash_bits=dhash(img), hist=color_hist(img))


def hash_similarity(a: np.ndarray, b: np.ndarray) -> float:
    return 1.0 - float(np.count_nonzero(a != b)) / a.size


def hist_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Histogram intersection averaged over the three channels (1.0 = identical)."""
    return float(np.minimum(a, b).sum() / 3.0)


def similarity(a: Signature, b: Signature, hash_weight: float = HASH_WEIGHT) -> float:
    """Combined similarity in [0, 1]."""
    return hash_weight * hash_similarity(a.hash_bits, b.hash_bits) + (
        1.0 - hash_weight
    ) * hist_similarity(a.hist, b.hist)
