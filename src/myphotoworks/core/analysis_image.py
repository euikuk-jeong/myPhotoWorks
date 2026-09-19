"""Load a small analysis copy of a photo (shared by similarity and scoring)."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageOps

DEFAULT_LONG_SIDE = 512


def load_analysis_image(path: Path, long_side: int = DEFAULT_LONG_SIDE) -> Image.Image:
    """Return an EXIF-rotated RGB copy whose longer side is at most ``long_side``.

    JPEGs are decoded at reduced scale via ``Image.draft`` so large files load quickly.
    Never upscales. Raises OSError / PIL.UnidentifiedImageError for unreadable files.
    """
    if long_side <= 0:
        raise ValueError("long_side must be positive")

    with Image.open(path) as img:
        if img.format == "JPEG":
            img.draft("RGB", (long_side, long_side))
        img = ImageOps.exif_transpose(img)
        img = img.convert("RGB")
        img.thumbnail((long_side, long_side), Image.Resampling.LANCZOS)
        return img
