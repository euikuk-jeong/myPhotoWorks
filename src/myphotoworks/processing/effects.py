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
    """Histogram stretch with 0.5% percentile clipping, colour-balance preserving.

    Clip points are derived from the luminance (greyscale) histogram so that
    all three RGB channels receive the same LUT.  Per-channel independent
    stretching shifts the white balance, introducing a colour cast.
    """
    gray = image.convert("L")
    hist = gray.histogram()  # 256 bins from luminance channel
    total = sum(hist)

    # Find 0.5th percentile (low clip)
    lo, hi = 0, 255
    acc = 0
    target_lo = total * 0.005
    for i in range(256):
        acc += hist[i]
        if acc >= target_lo:
            lo = i
            break

    # Find 99.5th percentile (high clip)
    acc = 0
    target_hi = total * 0.995
    for i in range(256):
        acc += hist[i]
        if acc >= target_hi:
            hi = i
            break

    if hi <= lo:
        return image

    scale = 255.0 / (hi - lo)
    lut = [max(0, min(255, int((i - lo) * scale + 0.5))) for i in range(256)]
    return image.point(lut * 3)  # same LUT for R, G, B


def auto_contrast(image: Image.Image) -> Image.Image:
    """Min-max tonal stretch with 1% clipping via Pillow's ImageOps.autocontrast.

    Clips the darkest and lightest 1% of pixels in each channel, then
    linearly stretches the remaining range to 0–255.  This matches the
    standard behaviour of common photo-editing tools and replaces the
    previous gamma-based mean-targeting approach.
    """
    from PIL import ImageOps
    return ImageOps.autocontrast(image, cutoff=1)


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
