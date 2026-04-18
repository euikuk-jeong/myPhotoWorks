"""Film simulation effect functions — pure functions, no GUI dependency."""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageFilter

from myphotoworks.recipes.recipe_data import FilmSim

# ---------------------------------------------------------------------------
# Film simulation LUT profiles
# Each profile is a list of 256 output values per channel (R, G, B).
# Applied via Image.point() — same mechanism as auto_level, very fast.
# ---------------------------------------------------------------------------

def _build_lut(r_gamma: float, g_gamma: float, b_gamma: float,
               r_scale: float = 1.0, g_scale: float = 1.0, b_scale: float = 1.0,
               sat_mul: float = 1.0) -> dict:
    """Build a film sim profile dict from per-channel curve parameters."""
    def channel_lut(gamma: float, scale: float) -> list[int]:
        lut = []
        for i in range(256):
            v = (i / 255.0) ** (1.0 / gamma) * scale
            lut.append(max(0, min(255, round(v * 255))))
        return lut

    return {
        "r": channel_lut(r_gamma, r_scale),
        "g": channel_lut(g_gamma, g_scale),
        "b": channel_lut(b_gamma, b_scale),
        "sat_mul": sat_mul,
    }


# Profiles tuned to approximate published Fujifilm film characteristics
_FILM_SIM_PROFILES: dict[str, dict] = {
    # Provia/Standard: neutral, accurate colors
    "provia": _build_lut(1.0, 1.0, 1.0, 1.0, 1.0, 1.0, sat_mul=1.0),

    # Velvia/Vivid: high saturation, punchy contrast, warm shadows
    "velvia": _build_lut(0.90, 0.95, 1.05, 1.05, 1.0, 0.95, sat_mul=1.35),

    # Astia/Soft: muted, pastel, slightly warm
    "astia": _build_lut(1.05, 1.02, 0.98, 1.0, 1.0, 1.02, sat_mul=0.82),

    # Classic Chrome: desaturated, faded, greenish midtones
    "classic_chrome": _build_lut(1.08, 1.05, 0.95, 0.97, 1.0, 1.03, sat_mul=0.68),

    # Pro Neg. Hi: slightly contrasty, skin-tone friendly
    "pro_neg_hi": _build_lut(0.95, 1.0, 1.02, 1.0, 1.0, 0.99, sat_mul=0.90),

    # Eterna/Cinema: low contrast, desaturated, cinematic
    "eterna": _build_lut(1.10, 1.08, 1.02, 0.97, 1.0, 1.04, sat_mul=0.73),

    # Acros: monochrome — sat_mul=0.0 triggers greyscale path
    "acros": _build_lut(0.95, 0.95, 0.95, 1.0, 1.0, 1.0, sat_mul=0.0),
}


# ---------------------------------------------------------------------------
# Public effect functions
# ---------------------------------------------------------------------------

def apply_film_sim(image: Image.Image, film_sim: str) -> Image.Image:
    """Apply named film simulation via per-channel LUT + optional saturation."""
    profile = _FILM_SIM_PROFILES.get(film_sim, _FILM_SIM_PROFILES["provia"])

    if profile["sat_mul"] == 0.0:
        # Monochrome path (Acros)
        gray = image.convert("L").convert("RGB")
        lut = profile["r"] * 3
        return gray.point(lut)

    # Apply per-channel LUT for tonal shaping
    lut = profile["r"] + profile["g"] + profile["b"]
    result = image.point(lut)

    # Apply saturation multiplier if not neutral
    if profile["sat_mul"] != 1.0:
        result = _scale_saturation(result, profile["sat_mul"])

    return result


def apply_wb(image: Image.Image, kelvin: int,
             shift_r: int = 0, shift_b: int = 0) -> Image.Image:
    """Apply white balance correction by colour temperature and R/B shift.

    Kelvin interpretation: scene colour temperature (Fujifilm convention).
    Lower kelvin (warm light) → reduce red / boost blue to compensate.
    Neutral reference: 5500K.
    shift_r/shift_b: ±9 → ±0.045 multiplier offset.
    """
    if kelvin == 5500 and shift_r == 0 and shift_b == 0:
        return image

    # Linear model from reference doc (simpler and faster than Planckian locus)
    k_factor = (kelvin - 5500) / 5500.0
    r_mul = 1.0 + k_factor * 0.2 + shift_r * 0.005
    b_mul = 1.0 - k_factor * 0.2 + shift_b * 0.005

    arr = np.asarray(image, dtype=np.float32)
    arr[:, :, 0] = np.clip(arr[:, :, 0] * r_mul, 0, 255)
    arr[:, :, 2] = np.clip(arr[:, :, 2] * b_mul, 0, 255)
    return Image.fromarray(arr.astype(np.uint8))


def apply_tone_curve(image: Image.Image, shadow: int, highlight: int) -> Image.Image:
    """Apply tone curve via shadow/highlight control points.

    shadow/highlight: -4 to +4.  Uses np.interp() — no scipy needed.
    """
    if shadow == 0 and highlight == 0:
        return image

    # 5 control points; shadow shifts [0..128], highlight shifts [128..255]
    shadow_shift = shadow * 8.0      # ±4 → ±32 pixel shift
    highlight_shift = highlight * 8.0

    x_ctrl = np.array([0.0, 64.0, 128.0, 192.0, 255.0])
    y_ctrl = np.array([
        max(0.0, shadow_shift),
        64.0 + shadow_shift * 0.5,
        128.0,
        192.0 + highlight_shift * 0.5,
        min(255.0, 255.0 + highlight_shift),
    ])

    lut = np.interp(np.arange(256), x_ctrl, y_ctrl).clip(0, 255).astype(np.uint8).tolist()
    return image.point(lut * 3)


def apply_saturation(image: Image.Image, amount: int) -> Image.Image:
    """Apply saturation adjustment.  amount: -4 to +4."""
    if amount == 0:
        return image
    factor = 1.0 + amount * 0.15
    return _scale_saturation(image, factor)


def apply_clarity(image: Image.Image, amount: int) -> Image.Image:
    """Apply clarity (local contrast / midtone contrast).

    Uses BoxBlur (O(N) linear time) instead of GaussianBlur for preview speed.
    amount: -5 to +5.
    """
    if amount == 0:
        return image

    # BoxBlur radius=8 is ~10x faster than GaussianBlur(radius=10) on 1600px images
    blurred = image.filter(ImageFilter.BoxBlur(radius=8))
    arr = np.asarray(image, dtype=np.float32)
    blur_arr = np.asarray(blurred, dtype=np.float32)
    strength = amount * 0.08
    result = np.clip(arr + strength * (arr - blur_arr), 0, 255)
    return Image.fromarray(result.astype(np.uint8))


def apply_sharpness(image: Image.Image, amount: int) -> Image.Image:
    """Apply sharpness adjustment.  amount: -4 to +4."""
    if amount == 0:
        return image
    if amount > 0:
        radius = 1.0 + amount * 0.3
        percent = 80 + amount * 30
        return image.filter(
            ImageFilter.UnsharpMask(radius=radius, percent=percent, threshold=2)
        )
    # Negative: soften with mild gaussian
    return image.filter(ImageFilter.GaussianBlur(radius=abs(amount) * 0.4))


def apply_grain(image: Image.Image, effect: str) -> Image.Image:
    """Add simulated film grain.  effect: 'off' | 'weak' | 'strong'."""
    if effect == "off":
        return image

    strength = 0.022 if effect == "weak" else 0.045
    arr = np.asarray(image, dtype=np.float32) / 255.0
    h, w = arr.shape[:2]

    # Luminance-weighted noise — grain is weaker in highlights
    noise = np.random.normal(0, strength, (h, w, 1))
    lum = (0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2])[:, :, np.newaxis]
    noise *= (1.0 - lum * 0.5)

    result = np.clip((arr + noise) * 255.0, 0, 255)
    return Image.fromarray(result.astype(np.uint8))


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _scale_saturation(image: Image.Image, factor: float) -> Image.Image:
    """Scale saturation by blending towards luminance."""
    arr = np.asarray(image, dtype=np.float32)
    gray = (0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2])[:, :, np.newaxis]
    result = np.clip(gray + factor * (arr - gray), 0, 255)
    return Image.fromarray(result.astype(np.uint8))
