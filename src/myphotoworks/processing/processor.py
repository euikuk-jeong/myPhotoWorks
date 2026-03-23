"""ImageProcessor — orchestrates the full effect chain."""
from __future__ import annotations

import io
from pathlib import Path

import piexif
from PIL import Image

from myphotoworks.models.photo_item import PhotoItem
from myphotoworks.models.settings import AppSettings
from myphotoworks.processing import effects, resize as resize_mod


def process(photo_item: PhotoItem, settings: AppSettings) -> Image.Image:
    """Apply the full effect chain to the photo and return the processed image.

    Does NOT save to disk. Call save() separately.
    Effect chain order:
      1. B&W conversion
      2. Level clipping
      3. Auto Level
      4. Auto Contrast
      5. Brightness / Contrast
      6. Sharpen or Gaussian
      7. Watermark
      8. Resize
    """
    image = Image.open(photo_item.source_path).convert("RGB")

    if settings.bw_enabled:
        image = effects.apply_bw(image)

    if settings.level_min != 0 or settings.level_max != 255:
        image = effects.apply_level(image, settings.level_min, settings.level_max)

    if settings.auto_level:
        image = effects.auto_level(image)

    if settings.auto_contrast:
        image = effects.auto_contrast(image)

    if settings.brightness != 0 or settings.contrast != 0:
        image = effects.apply_brightness_contrast(image, settings.brightness, settings.contrast)

    if settings.sharpen_enabled:
        image = effects.apply_sharpen(image, settings.sharpen_amount)
    elif settings.gaussian_enabled:
        image = effects.apply_gaussian(image, settings.gaussian_radius)

    if settings.watermark_enabled:
        text = _build_watermark_text(photo_item, settings)
        image = effects.apply_watermark(image, text, font_size=settings.watermark_font_size)

    if settings.resize_enabled and (settings.resize_width > 0 or settings.resize_height > 0):
        image = resize_mod.resize_image(
            image,
            settings.resize_width,
            settings.resize_height,
            settings.resize_keep_aspect,
        )

    return image


def save(image: Image.Image, output_path: Path, settings: AppSettings, source_path: Path | None = None) -> None:
    """Save the processed image to output_path.

    Preserves EXIF from the source if available.
    """
    kwargs: dict = {}

    if settings.output_format == "JPEG":
        kwargs["quality"] = settings.output_quality
        kwargs["subsampling"] = 0

        # Preserve EXIF if source is available
        if source_path is not None:
            try:
                exif_bytes = piexif.load(str(source_path))
                # Update resolution fields
                exif_bytes["0th"][piexif.ImageIFD.XResolution] = (settings.target_ppi, 1)
                exif_bytes["0th"][piexif.ImageIFD.YResolution] = (settings.target_ppi, 1)
                kwargs["exif"] = piexif.dump(exif_bytes)
            except Exception:
                pass

    image.save(output_path, format=settings.output_format, **kwargs)


def _build_watermark_text(photo_item: PhotoItem, settings: AppSettings) -> str:
    if settings.watermark_use_timestamp:
        date_str = photo_item.exif.get("date", "")
        if date_str:
            # Convert "2025:06:22 12:31:59" → "2025/06/22 12:31:59"
            date_str = date_str.replace(":", "/", 2)
            return date_str
    return settings.watermark_text
