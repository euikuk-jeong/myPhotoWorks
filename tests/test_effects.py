"""Unit tests for image effect functions."""
import numpy as np
from PIL import Image

from myphotoworks.processing.effects import (
    apply_brightness_contrast,
    apply_bw,
    apply_gaussian,
    apply_level,
    apply_sharpen,
    apply_watermark,
    auto_contrast,
    auto_level,
)


def make_image(width: int = 100, height: int = 100, color: tuple = (128, 64, 32)) -> Image.Image:
    """Create a solid-color RGB test image."""
    img = Image.new("RGB", (width, height), color)
    return img


def make_gradient_image(width: int = 100, height: int = 100) -> Image.Image:
    """Create an image with varying pixel values."""
    arr = np.zeros((height, width, 3), dtype=np.uint8)
    for i in range(width):
        val = int(i / width * 200) + 20  # values from 20 to 219
        arr[:, i, :] = val
    return Image.fromarray(arr)


class TestApplyBW:
    def test_converts_to_grayscale(self):
        img = make_image(color=(200, 100, 50))
        result = apply_bw(img)
        arr = np.array(result)
        # All channels should be equal (grayscale)
        assert np.all(arr[:, :, 0] == arr[:, :, 1])
        assert np.all(arr[:, :, 1] == arr[:, :, 2])

    def test_output_is_rgb(self):
        img = make_image()
        result = apply_bw(img)
        assert result.mode == "RGB"


class TestApplyLevel:
    def test_no_change_when_full_range(self):
        img = make_gradient_image()
        result = apply_level(img, 0, 255)
        assert np.array_equal(np.array(img), np.array(result))

    def test_clips_to_range(self):
        img = make_gradient_image()
        result = apply_level(img, 50, 150)
        arr = np.array(result)
        # After level adjustment, all values should be 0 or 255 at extremes
        assert arr.min() == 0
        assert arr.max() == 255


class TestAutoLevel:
    def test_stretches_to_full_range(self):
        # Image with values from 50 to 150 per channel
        arr = np.full((50, 50, 3), 50, dtype=np.uint8)
        arr[:, :, 0] = np.linspace(50, 150, 50 * 50).reshape(50, 50).astype(np.uint8)
        img = Image.fromarray(arr)
        result = auto_level(img)
        r_arr = np.array(result)[:, :, 0]
        assert r_arr.min() == 0
        assert r_arr.max() == 255

    def test_per_channel_independence(self):
        """Each channel should be stretched independently."""
        arr = np.zeros((10, 10, 3), dtype=np.uint8)
        arr[:, :, 0] = 100  # R: uniform — should stay uniform (no stretch)
        arr[:, :, 1] = np.linspace(0, 255, 100).reshape(10, 10).astype(np.uint8)
        arr[:, :, 2] = np.linspace(50, 200, 100).reshape(10, 10).astype(np.uint8)
        img = Image.fromarray(arr)
        result = auto_level(img)
        result_arr = np.array(result)
        # Blue channel should now span 0–255
        assert result_arr[:, :, 2].min() == 0
        assert result_arr[:, :, 2].max() == 255

    def test_uniform_image_unchanged(self):
        """Uniform image (no variance) should not crash."""
        img = make_image(color=(128, 128, 128))
        result = auto_level(img)
        assert result.mode == "RGB"


class TestAutoContrast:
    def test_returns_rgb(self):
        img = make_gradient_image()
        result = auto_contrast(img)
        assert result.mode == "RGB"

    def test_expands_range(self):
        arr = np.full((50, 50, 3), 128, dtype=np.uint8)
        arr[0, 0] = [50, 50, 50]
        arr[49, 49] = [200, 200, 200]
        img = Image.fromarray(arr)
        result = auto_contrast(img)
        r_arr = np.array(result)
        assert r_arr.min() == 0
        assert r_arr.max() == 255


class TestApplyBrightnessContrast:
    def test_no_change_at_zero(self):
        img = make_image()
        result = apply_brightness_contrast(img, 0, 0)
        assert np.array_equal(np.array(img), np.array(result))

    def test_brightness_increase(self):
        img = make_image(color=(100, 100, 100))
        result = apply_brightness_contrast(img, 50, 0)
        arr = np.array(result)
        assert arr.mean() > 100

    def test_brightness_decrease(self):
        img = make_image(color=(100, 100, 100))
        result = apply_brightness_contrast(img, -50, 0)
        arr = np.array(result)
        assert arr.mean() < 100


class TestApplySharpen:
    def test_returns_same_size(self):
        img = make_gradient_image(100, 100)
        result = apply_sharpen(img)
        assert result.size == img.size

    def test_returns_rgb(self):
        img = make_gradient_image()
        result = apply_sharpen(img)
        assert result.mode == "RGB"


class TestApplyGaussian:
    def test_returns_same_size(self):
        img = make_gradient_image()
        result = apply_gaussian(img)
        assert result.size == img.size

    def test_blurs_edges(self):
        """After gaussian blur, sharp edges should be softer."""
        arr = np.zeros((50, 50, 3), dtype=np.uint8)
        arr[:, 25:, :] = 255
        img = Image.fromarray(arr)
        result = apply_gaussian(img, radius=2.0)
        r_arr = np.array(result)
        # The boundary pixel should be between 0 and 255 (not sharp)
        assert 0 < r_arr[25, 25, 0] < 255


class TestApplyWatermark:
    def test_returns_rgb(self):
        img = make_image(200, 200)
        result = apply_watermark(img, "Test", font_size=16)
        assert result.mode == "RGB"

    def test_same_size(self):
        img = make_image(200, 200)
        result = apply_watermark(img, "Hello")
        assert result.size == img.size

    def test_empty_text_unchanged(self):
        img = make_image(200, 200, color=(128, 64, 32))
        result = apply_watermark(img, "")
        assert np.array_equal(np.array(img), np.array(result))
