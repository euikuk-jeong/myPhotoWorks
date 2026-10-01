"""Load a small analysis copy of a photo (shared by similarity and scoring)."""
from __future__ import annotations

import math
from collections.abc import Sequence
from pathlib import Path

from PIL import Image, ImageOps

DEFAULT_LONG_SIDE = 512
FACE_CROP_MARGIN = 0.25        # share of the face size added on each side of a face crop
FACE_CROP_TARGET = 320         # face region is decoded at least this large (if the file allows)
FACE_CROP_MAX_SIDE = 512       # ...and shrunk to this: the landmarker works on ~256 px anyway


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


def _face_region(box: tuple[int, int, int, int]) -> tuple[float, float, float, float]:
    """The face box plus ``FACE_CROP_MARGIN`` of its size on each side."""
    x0, y0, x1, y1 = box
    mx, my = (x1 - x0) * FACE_CROP_MARGIN, (y1 - y0) * FACE_CROP_MARGIN
    return x0 - mx, y0 - my, x1 + mx, y1 + my


def load_face_crops(
    path: Path, boxes: Sequence[tuple[int, int, int, int]], analysis_size: tuple[int, int]
) -> list[Image.Image]:
    """RGB crops of faces from the original file, at a higher resolution than the analysis copy.

    ``boxes`` are faces in the pixel grid of the analysis copy (``analysis_size`` = its width and
    height, EXIF-rotated like ``load_analysis_image``); ``FACE_CROP_MARGIN`` of the face size is
    added on each side, clamped to the image. The file is opened once: JPEGs are decoded at the
    smallest reduced scale that still gives the *smallest* face region ``FACE_CROP_TARGET`` px, so
    faces are cheap to re-read. Never upscales; each result is at most ``FACE_CROP_MAX_SIDE`` px
    on its long side.
    """
    if not boxes:
        return []
    aw, ah = analysis_size
    regions = [_face_region(b) for b in boxes]
    # image size at which the smallest face region measures FACE_CROP_TARGET px (square request:
    # the draft scale stays valid for rotated files too)
    share = max(min(max((r[2] - r[0]) / aw, (r[3] - r[1]) / ah) for r in regions), 1e-3)
    wanted = math.ceil(FACE_CROP_TARGET / share)

    crops = []
    with Image.open(path) as img:
        if img.format == "JPEG":
            img.draft("RGB", (wanted, wanted))
        img = ImageOps.exif_transpose(img).convert("RGB")
        sx, sy = img.width / aw, img.height / ah
        for region in regions:
            left = min(img.width - 1, max(0, math.floor(region[0] * sx)))
            top = min(img.height - 1, max(0, math.floor(region[1] * sy)))
            right = min(img.width, max(left + 1, math.ceil(region[2] * sx)))
            bottom = min(img.height, max(top + 1, math.ceil(region[3] * sy)))
            crop = img.crop((left, top, right, bottom))
            crop.thumbnail((FACE_CROP_MAX_SIDE, FACE_CROP_MAX_SIDE), Image.Resampling.LANCZOS)
            crops.append(crop)
    return crops


def load_face_crop(
    path: Path, box: tuple[int, int, int, int], analysis_size: tuple[int, int]
) -> Image.Image:
    """RGB crop of one face (see ``load_face_crops``)."""
    return load_face_crops(path, [box], analysis_size)[0]
