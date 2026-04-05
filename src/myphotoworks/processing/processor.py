"""ImageProcessor — orchestrates the effect chain."""
from __future__ import annotations

import logging
import time
from pathlib import Path

import piexif
from PIL import Image, ImageOps

from myphotoworks.models.photo_item import PhotoItem
from myphotoworks.models.settings import AppSettings
from myphotoworks.processing import effects
from myphotoworks.processing.resize import resize_by_axis

logger = logging.getLogger(__name__)


def process(
    photo_item: PhotoItem,
    settings: AppSettings,
    apply_effects: bool = True,
    *,
    source_image: Image.Image | None = None,
) -> Image.Image:
    """Apply the effect chain and return the processed image.

    apply_effects=False skips color corrections (Auto Level, Auto Contrast,
    Brightness/Contrast) and applies only resize. Used when saving with key '1'
    (Before pane — resize only).

    source_image: optional pre-loaded PIL Image to skip disk I/O.

    Effect chain order:
      1. Auto Level          (if apply_effects)
      2. Auto Contrast       (if apply_effects)
      3. Brightness/Contrast (if apply_effects)
      4. Resize              (always, if resize_enabled)
    """
    t_total = time.perf_counter()

    if source_image is not None:
        image = source_image.copy()
        logger.debug("[process] image from cache (copy) %.1f ms",
                     (time.perf_counter() - t_total) * 1000)
    else:
        t0 = time.perf_counter()
        image = ImageOps.exif_transpose(Image.open(photo_item.source_path)).convert("RGB")
        logger.debug("[process] Image.open + convert %.1f ms",
                     (time.perf_counter() - t0) * 1000)

    if apply_effects:
        if settings.auto_level:
            t0 = time.perf_counter()
            image = effects.auto_level(image)
            logger.debug("[process] auto_level %.1f ms",
                         (time.perf_counter() - t0) * 1000)

        if settings.auto_contrast:
            t0 = time.perf_counter()
            image = effects.auto_contrast(image)
            logger.debug("[process] auto_contrast %.1f ms",
                         (time.perf_counter() - t0) * 1000)

        if settings.brightness != 0 or settings.contrast != 0:
            t0 = time.perf_counter()
            image = effects.apply_brightness_contrast(
                image, settings.brightness, settings.contrast
            )
            logger.debug("[process] brightness/contrast %.1f ms",
                         (time.perf_counter() - t0) * 1000)

    if settings.resize_enabled and settings.resize_px > 0:
        t0 = time.perf_counter()
        image = resize_by_axis(image, settings.resize_axis, settings.resize_px)
        logger.debug("[process] resize %.1f ms",
                     (time.perf_counter() - t0) * 1000)

    logger.debug("[process] TOTAL %.1f ms  (%s)",
                 (time.perf_counter() - t_total) * 1000,
                 photo_item.source_path.name)
    return image


def save(
    image: Image.Image,
    output_path: Path,
    settings: AppSettings,
    source_path: Path | None = None,
) -> None:
    """Save the processed image as JPEG, preserving EXIF from source."""
    kwargs: dict = {
        "quality": settings.output_quality,
        "subsampling": 0,
    }

    if source_path is not None:
        try:
            exif_bytes = piexif.load(str(source_path))
            # Pixels are already rotated by exif_transpose; reset Orientation to Normal
            # so viewers don't rotate again.
            exif_bytes.setdefault("0th", {})[piexif.ImageIFD.Orientation] = 1
            kwargs["exif"] = piexif.dump(exif_bytes)
        except Exception:
            pass

    image.save(output_path, format="JPEG", **kwargs)
