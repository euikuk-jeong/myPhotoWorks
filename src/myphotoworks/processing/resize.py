"""Resize utilities."""
from __future__ import annotations

from PIL import Image

from myphotoworks.models.settings import ResizeAxis


def resize_by_axis(image: Image.Image, axis: ResizeAxis, px: int) -> Image.Image:
    """Resize image so that the specified axis equals px, maintaining aspect ratio.

    axis=LONG  → the longer side becomes px
    axis=SHORT → the shorter side becomes px
    """
    orig_w, orig_h = image.size
    is_landscape = orig_w >= orig_h

    if axis == ResizeAxis.LONG:
        if is_landscape:
            ratio = px / orig_w
        else:
            ratio = px / orig_h
    else:  # SHORT
        if is_landscape:
            ratio = px / orig_h
        else:
            ratio = px / orig_w

    target = (max(1, int(orig_w * ratio)), max(1, int(orig_h * ratio)))
    return image.resize(target, Image.Resampling.LANCZOS)
