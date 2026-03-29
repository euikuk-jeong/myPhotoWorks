"""Image effect functions — pure functions with no GUI dependency."""
from __future__ import annotations

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont


def apply_bw(image: Image.Image) -> Image.Image:
    """Convert to grayscale and back to RGB."""
    return image.convert("L").convert("RGB")


def apply_level(image: Image.Image, level_min: int, level_max: int) -> Image.Image:
    """Clip pixel values to [level_min, level_max] then stretch to [0, 255]."""
    if level_min == 0 and level_max == 255:
        return image
    if level_max <= level_min:
        return image
    scale = 255.0 / (level_max - level_min)
    lut = [max(0, min(255, int((min(max(i, level_min), level_max) - level_min) * scale + 0.5)))
           for i in range(256)]
    return image.point(lut * 3)


def auto_level(image: Image.Image) -> Image.Image:
    """Per-channel histogram stretch with 0.5% percentile clipping.

    Uses per-channel histogram + LUT for O(pixels) mapping instead of
    sorting-based percentile on the full array.
    """
    channels = image.split()
    result_channels = []
    for ch in channels:
        hist = ch.histogram()  # 256 bins, O(pixels) single pass
        total = sum(hist)
        # Find 0.5th percentile
        lo, hi = 0, 255
        acc = 0
        target_lo = total * 0.005
        for i in range(256):
            acc += hist[i]
            if acc >= target_lo:
                lo = i
                break
        # Find 99.5th percentile
        acc = 0
        target_hi = total * 0.995
        for i in range(256):
            acc += hist[i]
            if acc >= target_hi:
                hi = i
                break
        if hi <= lo:
            result_channels.append(ch)
            continue
        scale = 255.0 / (hi - lo)
        lut = [max(0, min(255, int((i - lo) * scale + 0.5))) for i in range(256)]
        result_channels.append(ch.point(lut))
    return Image.merge("RGB", result_channels)


def auto_contrast(image: Image.Image) -> Image.Image:
    """Adaptive gamma correction that brings mean luminance toward mid-grey (0.5).

    Uses a 256-entry LUT for O(pixels) mapping instead of per-pixel
    float32 power computation.

    Unlike auto_level (linear per-channel stretch), this uses a non-linear
    tone curve.  It works independently on images that have already been
    processed by auto_level, making the two operations composable:
      - auto_level  → removes per-channel colour cast (linear stretch)
      - auto_contrast → boosts mid-tone brightness / contrast (gamma curve)
    """
    import math
    # Compute mean luminance from histogram to avoid full array allocation
    hist = image.histogram()  # 256 * 3 entries for RGB
    total_pixels = image.width * image.height
    total_sum = 0
    for ch in range(3):
        offset = ch * 256
        for i in range(256):
            total_sum += i * hist[offset + i]
    mean_lum = total_sum / (total_pixels * 3 * 255.0)

    if mean_lum <= 0.0 or mean_lum >= 1.0:
        return image
    gamma = math.log(0.5) / math.log(mean_lum)
    gamma = max(0.2, min(4.0, gamma))
    # Build a single 256-entry LUT and apply to all channels
    lut = [min(255, int(((i / 255.0) ** gamma) * 255.0 + 0.5)) for i in range(256)]
    return image.point(lut * 3)


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
