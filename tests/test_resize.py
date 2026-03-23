"""Unit tests for resize utilities."""
from PIL import Image

from myphotoworks.processing.resize import resize_image


def make_image(width: int, height: int) -> Image.Image:
    return Image.new("RGB", (width, height), (128, 128, 128))


class TestResizeImage:
    def test_exact_dimensions(self):
        img = make_image(800, 600)
        result = resize_image(img, 400, 300, keep_aspect=False)
        assert result.size == (400, 300)

    def test_keep_aspect_width_constraint(self):
        img = make_image(800, 400)
        result = resize_image(img, 400, 0, keep_aspect=True)
        assert result.width == 400
        assert result.height == 200

    def test_keep_aspect_height_constraint(self):
        img = make_image(800, 400)
        result = resize_image(img, 0, 200, keep_aspect=True)
        assert result.height == 200
        assert result.width == 400

    def test_keep_aspect_both_constraints_fit_width(self):
        """800x400 → fit within 400x400: limited by width."""
        img = make_image(800, 400)
        result = resize_image(img, 400, 400, keep_aspect=True)
        assert result.width == 400
        assert result.height == 200

    def test_keep_aspect_both_constraints_fit_height(self):
        """400x800 → fit within 400x400: limited by height."""
        img = make_image(400, 800)
        result = resize_image(img, 400, 400, keep_aspect=True)
        assert result.height == 400
        assert result.width == 200

    def test_no_resize_when_zero(self):
        img = make_image(800, 600)
        result = resize_image(img, 0, 0)
        assert result.size == (800, 600)

    def test_returns_pillow_image(self):
        img = make_image(100, 100)
        result = resize_image(img, 50, 50)
        assert isinstance(result, Image.Image)
