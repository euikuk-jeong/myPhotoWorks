"""Unit tests for resize_by_axis."""
from PIL import Image

from myphotoworks.models.settings import ResizeAxis
from myphotoworks.processing.resize import resize_by_axis


def make_image(width: int, height: int) -> Image.Image:
    return Image.new("RGB", (width, height), (128, 128, 128))


class TestResizeByAxisLong:
    def test_landscape_long_axis(self):
        """가로 이미지: 긴 축(width)을 1000으로 맞춤."""
        img = make_image(2000, 1000)
        result = resize_by_axis(img, ResizeAxis.LONG, 1000)
        assert result.width == 1000
        assert result.height == 500

    def test_portrait_long_axis(self):
        """세로 이미지: 긴 축(height)을 1000으로 맞춤."""
        img = make_image(1000, 2000)
        result = resize_by_axis(img, ResizeAxis.LONG, 1000)
        assert result.height == 1000
        assert result.width == 500

    def test_square_long_axis(self):
        """정사각형: 긴 축 = 가로(동일), 1000으로 맞춤."""
        img = make_image(2000, 2000)
        result = resize_by_axis(img, ResizeAxis.LONG, 1000)
        assert result.width == 1000
        assert result.height == 1000


class TestResizeByAxisShort:
    def test_landscape_short_axis(self):
        """가로 이미지: 짧은 축(height)을 500으로 맞춤."""
        img = make_image(2000, 1000)
        result = resize_by_axis(img, ResizeAxis.SHORT, 500)
        assert result.height == 500
        assert result.width == 1000

    def test_portrait_short_axis(self):
        """세로 이미지: 짧은 축(width)을 500으로 맞춤."""
        img = make_image(1000, 2000)
        result = resize_by_axis(img, ResizeAxis.SHORT, 500)
        assert result.width == 500
        assert result.height == 1000

    def test_square_short_axis(self):
        img = make_image(2000, 2000)
        result = resize_by_axis(img, ResizeAxis.SHORT, 1000)
        assert result.width == 1000
        assert result.height == 1000


class TestResizeByAxisGeneral:
    def test_returns_pillow_image(self):
        img = make_image(800, 600)
        result = resize_by_axis(img, ResizeAxis.LONG, 400)
        assert isinstance(result, Image.Image)

    def test_aspect_ratio_preserved_landscape(self):
        """2:1 비율이 유지되어야 함."""
        img = make_image(2000, 1000)
        result = resize_by_axis(img, ResizeAxis.LONG, 1000)
        assert abs(result.width / result.height - 2.0) < 0.01

    def test_aspect_ratio_preserved_portrait(self):
        """1:2 비율이 유지되어야 함."""
        img = make_image(1000, 2000)
        result = resize_by_axis(img, ResizeAxis.LONG, 1000)
        assert abs(result.height / result.width - 2.0) < 0.01

    def test_minimum_size_is_one(self):
        """매우 작은 px 값에서도 0이 되지 않아야 함."""
        img = make_image(100, 50)
        result = resize_by_axis(img, ResizeAxis.LONG, 1)
        assert result.width >= 1
        assert result.height >= 1
