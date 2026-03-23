"""Resize utilities."""
from __future__ import annotations

from PIL import Image


def resize_image(
    image: Image.Image,
    width: int,
    height: int,
    keep_aspect: bool = True,
) -> Image.Image:
    """Resize image to target dimensions.

    If keep_aspect is True, fits within (width, height) while maintaining ratio.
    If width or height is 0, only the non-zero dimension is used as constraint.
    """
    orig_w, orig_h = image.size

    if width <= 0 and height <= 0:
        return image

    if keep_aspect:
        if width <= 0:
            ratio = height / orig_h
            target = (int(orig_w * ratio), height)
        elif height <= 0:
            ratio = width / orig_w
            target = (width, int(orig_h * ratio))
        else:
            ratio = min(width / orig_w, height / orig_h)
            target = (int(orig_w * ratio), int(orig_h * ratio))
    else:
        target = (width if width > 0 else orig_w, height if height > 0 else orig_h)

    return image.resize(target, Image.Resampling.LANCZOS)
