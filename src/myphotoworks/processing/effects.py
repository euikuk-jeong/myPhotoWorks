"""Image effect functions — pure functions with no GUI dependency."""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont


def apply_bw(image: Image.Image) -> Image.Image:
    """Convert to grayscale and back to RGB."""
    return image.convert("L").convert("RGB")


def apply_level(image: Image.Image, level_min: int, level_max: int) -> Image.Image:
    """Clip pixel values to [level_min, level_max] then stretch to [0, 255]."""
    if level_min == 0 and level_max == 255:
        return image
    arr = np.array(image, dtype=np.float32)
    arr = np.clip(arr, level_min, level_max)
    if level_max > level_min:
        arr = (arr - level_min) / (level_max - level_min) * 255.0
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def auto_level(image: Image.Image) -> Image.Image:
    """Per-channel histogram stretch with 0.5% percentile clipping.

    Using absolute min/max fails when even one pixel is fully black (0) and
    one is fully white (255) — the stretch ratio becomes 1.0 (no change).
    Percentile clipping ignores outliers like isolated bright stars or noise pixels.
    """
    arr = np.array(image, dtype=np.float32)
    for ch in range(3):
        lo = np.percentile(arr[:, :, ch], 0.5)
        hi = np.percentile(arr[:, :, ch], 99.5)
        if hi > lo:
            arr[:, :, ch] = (arr[:, :, ch] - lo) / (hi - lo) * 255.0
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def auto_contrast(image: Image.Image) -> Image.Image:
    """Adaptive gamma correction that brings mean luminance toward mid-grey (0.5).

    Unlike auto_level (linear per-channel stretch), this uses a non-linear
    tone curve.  It works independently on images that have already been
    processed by auto_level, making the two operations composable:
      - auto_level  → removes per-channel colour cast (linear stretch)
      - auto_contrast → boosts mid-tone brightness / contrast (gamma curve)

    For dark images (mean < 0.5) the gamma < 1 brightens mid-tones.
    For bright images (mean > 0.5) the gamma > 1 darkens them.
    The black point (0) and white point (255) are preserved exactly.
    """
    import math
    arr = np.array(image, dtype=np.float32) / 255.0
    mean_lum = float(arr.mean())
    if mean_lum <= 0.0 or mean_lum >= 1.0:
        return image
    # gamma that maps mean_lum → 0.5: 0.5 = mean_lum^gamma
    gamma = math.log(0.5) / math.log(mean_lum)
    gamma = max(0.2, min(4.0, gamma))   # clamp to a safe range
    arr = np.power(np.clip(arr, 0.0, 1.0), gamma)
    return Image.fromarray(np.clip(arr * 255.0, 0, 255).astype(np.uint8))


def apply_brightness_contrast(
    image: Image.Image, brightness: int, contrast: int
) -> Image.Image:
    """Apply brightness and contrast adjustments.

    brightness/contrast: -100 ~ +100, where 0 means no change.
    Converts to Pillow's enhancement factor: 0.0 = min, 1.0 = original, 2.0 = max.
    """
    if brightness != 0:
        factor = 1.0 + brightness / 100.0
        image = ImageEnhance.Brightness(image).enhance(max(0.0, factor))
    if contrast != 0:
        factor = 1.0 + contrast / 100.0
        image = ImageEnhance.Contrast(image).enhance(max(0.0, factor))
    return image


def apply_sharpen(image: Image.Image, amount: float = 1.0) -> Image.Image:
    """Unsharp mask sharpening. amount: 0.0 ~ 3.0."""
    radius = 2
    percent = int(amount * 100)
    threshold = 3
    return image.filter(
        ImageFilter.UnsharpMask(radius=radius, percent=percent, threshold=threshold)
    )


def apply_gaussian(image: Image.Image, radius: float = 1.0) -> Image.Image:
    """Gaussian blur."""
    return image.filter(ImageFilter.GaussianBlur(radius=radius))


def apply_watermark(
    image: Image.Image,
    text: str,
    font_size: int = 24,
    position: str = "bottom-right",
    opacity: int = 180,
) -> Image.Image:
    """Overlay text watermark onto the image.

    position: 'bottom-right' | 'bottom-left' | 'top-right' | 'top-left' | 'center'
    opacity: 0 (transparent) ~ 255 (opaque)
    """
    if not text:
        return image

    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    try:
        font = ImageFont.truetype("arial.ttf", font_size)
    except (OSError, IOError):
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    margin = 10
    w, h = image.size
    positions = {
        "bottom-right": (w - text_w - margin, h - text_h - margin),
        "bottom-left": (margin, h - text_h - margin),
        "top-right": (w - text_w - margin, margin),
        "top-left": (margin, margin),
        "center": ((w - text_w) // 2, (h - text_h) // 2),
    }
    xy = positions.get(position, positions["bottom-right"])

    # Shadow for readability
    draw.text((xy[0] + 1, xy[1] + 1), text, font=font, fill=(0, 0, 0, opacity))
    draw.text(xy, text, font=font, fill=(255, 255, 255, opacity))

    base = image.convert("RGBA")
    combined = Image.alpha_composite(base, overlay)
    return combined.convert("RGB")
