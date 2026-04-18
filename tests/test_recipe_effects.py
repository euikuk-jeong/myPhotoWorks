"""Tests for recipe_effects module."""
import numpy as np
import pytest
from PIL import Image

from myphotoworks.recipes import recipe_effects


def _solid(r: int, g: int, b: int, size: int = 64) -> Image.Image:
    img = Image.new("RGB", (size, size))
    img.paste((r, g, b), [0, 0, size, size])
    return img


def _mean_channels(img: Image.Image) -> tuple[float, float, float]:
    arr = np.asarray(img, dtype=float)
    return arr[:, :, 0].mean(), arr[:, :, 1].mean(), arr[:, :, 2].mean()


# ---------------------------------------------------------------------------
# apply_film_sim
# ---------------------------------------------------------------------------

class TestApplyFilmSim:
    def test_output_mode_and_size(self):
        img = _solid(128, 128, 128)
        out = recipe_effects.apply_film_sim(img, "provia")
        assert out.mode == "RGB"
        assert out.size == img.size

    def test_acros_produces_greyscale(self):
        img = _solid(200, 100, 50)
        out = recipe_effects.apply_film_sim(img, "acros")
        r, g, b = _mean_channels(out)
        assert abs(r - g) < 5, "Acros R and G should be nearly equal"
        assert abs(g - b) < 5, "Acros G and B should be nearly equal"

    def test_velvia_increases_saturation_vs_provia(self):
        # Use a colourful input; Velvia should increase colour deviation
        img = _solid(200, 80, 40)
        provia = recipe_effects.apply_film_sim(img, "provia")
        velvia = recipe_effects.apply_film_sim(img, "velvia")

        def saturation_proxy(image):
            arr = np.asarray(image, dtype=float)
            # Std deviation of R-G-B values per pixel = rough saturation indicator
            return np.std(arr, axis=2).mean()

        assert saturation_proxy(velvia) >= saturation_proxy(provia)

    @pytest.mark.parametrize("sim", ["provia", "velvia", "astia", "classic_chrome",
                                     "pro_neg_hi", "eterna", "acros"])
    def test_all_sims_preserve_size(self, sim):
        img = _solid(128, 100, 80)
        out = recipe_effects.apply_film_sim(img, sim)
        assert out.size == img.size
        assert out.mode == "RGB"


# ---------------------------------------------------------------------------
# apply_wb
# ---------------------------------------------------------------------------

class TestApplyWb:
    def test_neutral_returns_unchanged(self):
        img = _solid(128, 128, 128)
        out = recipe_effects.apply_wb(img, 5500, 0, 0)
        assert out is img  # exact same object — early return

    def test_warm_kelvin_compensates_warm(self):
        # Fujifilm convention: 3200K (warm scene) → camera compensates by reducing red
        img = _solid(128, 128, 128)
        out = recipe_effects.apply_wb(img, 3200, 0, 0)
        r, _g, b = _mean_channels(out)
        assert r < 128, "Warm scene WB: red should decrease (cool compensation)"
        assert b > 128, "Warm scene WB: blue should increase (cool compensation)"

    def test_cool_kelvin_compensates_cool(self):
        # 9000K (cool scene) → camera compensates by boosting red
        img = _solid(128, 128, 128)
        out = recipe_effects.apply_wb(img, 9000, 0, 0)
        r, _g, b = _mean_channels(out)
        assert r > b, "Cool scene WB: red should be boosted relative to blue"

    def test_output_mode_and_size(self):
        img = _solid(100, 120, 140)
        out = recipe_effects.apply_wb(img, 4000, 2, -1)
        assert out.mode == "RGB"
        assert out.size == img.size


# ---------------------------------------------------------------------------
# apply_tone_curve
# ---------------------------------------------------------------------------

class TestApplyToneCurve:
    def test_neutral_returns_unchanged(self):
        img = _solid(128, 128, 128)
        out = recipe_effects.apply_tone_curve(img, 0, 0)
        assert out is img

    def test_positive_shadow_lifts_shadows(self):
        img = _solid(30, 30, 30)  # dark image
        out = recipe_effects.apply_tone_curve(img, 4, 0)
        r, _g, _b = _mean_channels(out)
        assert r > 30, "Positive shadow should lift dark areas"

    def test_negative_highlight_lowers_highlights(self):
        img = _solid(230, 230, 230)  # bright image
        out = recipe_effects.apply_tone_curve(img, 0, -4)
        r, _g, _b = _mean_channels(out)
        assert r < 230, "Negative highlight should lower bright areas"

    def test_output_size(self):
        img = _solid(128, 128, 128)
        out = recipe_effects.apply_tone_curve(img, 2, -1)
        assert out.size == img.size


# ---------------------------------------------------------------------------
# apply_saturation
# ---------------------------------------------------------------------------

class TestApplySaturation:
    def test_zero_returns_unchanged(self):
        img = _solid(200, 80, 40)
        out = recipe_effects.apply_saturation(img, 0)
        assert out is img

    def test_positive_increases_saturation(self):
        img = _solid(200, 80, 40)
        neutral = recipe_effects.apply_saturation(img, 0)
        boosted = recipe_effects.apply_saturation(img, 4)
        r_n, _g_n, b_n = _mean_channels(neutral)
        r_b, _g_b, b_b = _mean_channels(boosted)
        # Red channel should increase, blue should decrease further from grey
        assert r_b >= r_n

    def test_negative_reduces_saturation(self):
        img = _solid(200, 80, 40)
        out = recipe_effects.apply_saturation(img, -4)
        r, g, b = _mean_channels(out)
        # Should be more grey-like (channels closer together)
        spread_in = max(200, 80, 40) - min(200, 80, 40)
        spread_out = max(r, g, b) - min(r, g, b)
        assert spread_out < spread_in


# ---------------------------------------------------------------------------
# apply_clarity
# ---------------------------------------------------------------------------

class TestApplyClarity:
    def test_zero_returns_unchanged(self):
        img = _solid(128, 128, 128)
        out = recipe_effects.apply_clarity(img, 0)
        assert out is img

    def test_output_size_and_mode(self):
        img = Image.new("RGB", (64, 64))
        out = recipe_effects.apply_clarity(img, 3)
        assert out.size == img.size
        assert out.mode == "RGB"


# ---------------------------------------------------------------------------
# apply_sharpness
# ---------------------------------------------------------------------------

class TestApplySharpness:
    def test_zero_returns_unchanged(self):
        img = _solid(128, 128, 128)
        out = recipe_effects.apply_sharpness(img, 0)
        assert out is img

    def test_output_size(self):
        img = Image.new("RGB", (64, 64))
        out = recipe_effects.apply_sharpness(img, 2)
        assert out.size == img.size

    def test_negative_blurs(self):
        # Create a sharp edge; negative sharpness should reduce contrast
        img = Image.new("RGB", (64, 64), (0, 0, 0))
        img.paste((255, 255, 255), [32, 0, 64, 64])
        out = recipe_effects.apply_sharpness(img, -3)
        # Edge pixels in output should be less extreme than input
        arr_in = np.asarray(img, dtype=float)
        arr_out = np.asarray(out, dtype=float)
        assert arr_out[:, 31, 0].mean() > arr_in[:, 31, 0].mean() or \
               arr_out[:, 32, 0].mean() < arr_in[:, 32, 0].mean()


# ---------------------------------------------------------------------------
# apply_grain
# ---------------------------------------------------------------------------

class TestApplyGrain:
    def test_off_returns_unchanged(self):
        img = _solid(128, 128, 128)
        out = recipe_effects.apply_grain(img, "off")
        assert out is img

    def test_weak_adds_noise(self):
        img = _solid(128, 128, 128, size=128)
        out = recipe_effects.apply_grain(img, "weak")
        arr_in = np.asarray(img, dtype=float)
        arr_out = np.asarray(out, dtype=float)
        diff = np.abs(arr_out - arr_in)
        assert diff.std() > 0, "Grain should add noise variance"

    def test_strong_adds_more_noise_than_weak(self):
        np.random.seed(42)
        img = _solid(128, 128, 128, size=128)
        weak = recipe_effects.apply_grain(img, "weak")
        np.random.seed(42)
        strong = recipe_effects.apply_grain(img, "strong")
        diff_weak = np.abs(np.asarray(weak, dtype=float) - np.asarray(img, dtype=float))
        diff_strong = np.abs(np.asarray(strong, dtype=float) - np.asarray(img, dtype=float))
        assert diff_strong.std() > diff_weak.std()

    def test_output_size(self):
        img = _solid(128, 128, 128)
        out = recipe_effects.apply_grain(img, "strong")
        assert out.size == img.size
