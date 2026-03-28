"""ImageProcessor — orchestrates the effect chain."""
from __future__ import annotations

from pathlib import Path

import piexif
from PIL import Image

from myphotoworks.models.photo_item import PhotoItem
from myphotoworks.models.settings import AppSettings
from myphotoworks.processing import effects
from myphotoworks.processing.resize import resize_by_axis


def process(
    photo_item: PhotoItem,
    settings: AppSettings,
    apply_effects: bool = True,
) -> Image.Image:
    """Apply the effect chain and return the processed image.

    apply_effects=False skips color corrections (Auto Level, Auto Contrast,
    Brightness/Contrast) and applies only resize. Used when saving with key '1'
    (Before pane — resize only).

    Effect chain order:
      1. Auto Level          (if apply_effects)
      2. Auto Contrast       (if apply_effects)
      3. Brightness/Contrast (if apply_effects)
      4. Resize              (always, if resize_enabled)
    """
    image = Image.open(photo_item.source_path).convert("RGB")

    if apply_effects:
        if settings.auto_level:
            image = effects.auto_level(image)

        if settings.auto_contrast:
            image = effects.auto_contrast(image)

        if settings.brightness != 0 or settings.contrast != 0:
            image = effects.apply_brightness_contrast(
                image, settings.brightness, settings.contrast
            )

    if settings.resize_enabled and settings.resize_px > 0:
        image = resize_by_axis(image, settings.resize_axis, settings.resize_px)

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
            kwargs["exif"] = piexif.dump(exif_bytes)
        except Exception:
            pass

    image.save(output_path, format="JPEG", **kwargs)
