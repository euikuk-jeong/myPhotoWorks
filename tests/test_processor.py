"""Unit tests for processor.process() and processor.save()."""
import io
from pathlib import Path

import pytest
from PIL import Image

from myphotoworks.models.photo_item import PhotoItem
from myphotoworks.models.settings import AppSettings, ResizeAxis
from myphotoworks.processing import processor


def make_jpeg_file(tmp_path: Path, width: int = 200, height: int = 100) -> Path:
    """Create a temporary JPEG file and return its path."""
    path = tmp_path / "test.jpg"
    img = Image.new("RGB", (width, height), (128, 100, 80))
    img.save(path, format="JPEG", quality=90)
    return path


def make_photo_item(path: Path) -> PhotoItem:
    return PhotoItem(source_path=path)


class TestProcess:
    def test_returns_pil_image(self, tmp_path):
        path = make_jpeg_file(tmp_path)
        photo = make_photo_item(path)
        result = processor.process(photo, AppSettings())
        assert isinstance(result, Image.Image)

    def test_no_resize_by_default(self, tmp_path):
        path = make_jpeg_file(tmp_path, 200, 100)
        photo = make_photo_item(path)
        result = processor.process(photo, AppSettings())
        assert result.size == (200, 100)

    def test_resize_applied_when_enabled(self, tmp_path):
        path = make_jpeg_file(tmp_path, 2000, 1000)
        photo = make_photo_item(path)
        settings = AppSettings(resize_enabled=True, resize_axis=ResizeAxis.LONG, resize_px=1000)
        result = processor.process(photo, settings)
        assert result.width == 1000
        assert result.height == 500

    def test_apply_effects_false_skips_color_correction(self, tmp_path):
        """apply_effects=False 시 보정 없이 리사이즈만 적용."""
        path = make_jpeg_file(tmp_path, 2000, 1000)
        photo = make_photo_item(path)
        settings = AppSettings(
            auto_level=True,
            auto_contrast=True,
            brightness=50,
            resize_enabled=True,
            resize_px=1000,
        )
        result = processor.process(photo, settings, apply_effects=False)
        # 리사이즈는 적용됨
        assert result.width == 1000
        # 보정 없이 열었을 때와 동일한 평균 밝기여야 함
        original = Image.open(path).convert("RGB")
        import numpy as np
        orig_mean = float(np.array(original).mean())
        result_resized = original.resize((1000, 500), Image.Resampling.LANCZOS)
        result_mean = float(np.array(result_resized).mean())
        assert abs(float(np.array(result).mean()) - result_mean) < 2.0

    def test_apply_effects_true_changes_brightness(self, tmp_path):
        """brightness=50 적용 시 평균 픽셀값이 증가해야 함."""
        path = make_jpeg_file(tmp_path, 100, 100)
        photo = make_photo_item(path)

        baseline = processor.process(photo, AppSettings(), apply_effects=True)
        brighter = processor.process(
            photo, AppSettings(brightness=50), apply_effects=True
        )

        import numpy as np
        assert float(np.array(brighter).mean()) > float(np.array(baseline).mean())

    def test_output_is_rgb(self, tmp_path):
        path = make_jpeg_file(tmp_path)
        photo = make_photo_item(path)
        result = processor.process(photo, AppSettings())
        assert result.mode == "RGB"


class TestPreviewNoResize:
    """미리보기 렌더링 시 resize_enabled=False 복사본을 사용하는 동작 검증."""

    def test_preview_copy_disables_resize(self, tmp_path):
        """resize_enabled=True 설정에서 preview_settings 복사본은 리사이즈 없이 원본 크기 유지."""
        import copy
        path = make_jpeg_file(tmp_path, 2000, 1000)
        photo = make_photo_item(path)

        settings = AppSettings(resize_enabled=True, resize_axis=ResizeAxis.LONG, resize_px=500)
        preview_settings = copy.copy(settings)
        preview_settings.resize_enabled = False

        result = processor.process(photo, preview_settings, apply_effects=True)
        assert result.size == (2000, 1000)  # 원본 크기 유지

    def test_original_settings_unchanged_after_copy(self, tmp_path):
        """복사본 수정이 원본 설정에 영향을 주지 않아야 함."""
        import copy
        settings = AppSettings(resize_enabled=True, resize_px=500)
        preview_settings = copy.copy(settings)
        preview_settings.resize_enabled = False

        assert settings.resize_enabled is True  # 원본 유지

    def test_save_still_applies_resize(self, tmp_path):
        """저장 시에는 resize가 적용되어 크기가 줄어야 함."""
        path = make_jpeg_file(tmp_path, 2000, 1000)
        photo = make_photo_item(path)

        settings = AppSettings(resize_enabled=True, resize_axis=ResizeAxis.LONG, resize_px=500)
        img = processor.process(photo, settings, apply_effects=True)
        assert img.width == 500
        assert img.height == 250


class TestSave:
    def test_saves_jpeg(self, tmp_path):
        path = make_jpeg_file(tmp_path)
        photo = make_photo_item(path)
        img = processor.process(photo, AppSettings())
        out = tmp_path / "out.jpg"
        processor.save(img, out, AppSettings(), source_path=path)
        assert out.exists()

    def test_saved_file_is_valid_jpeg(self, tmp_path):
        path = make_jpeg_file(tmp_path)
        photo = make_photo_item(path)
        img = processor.process(photo, AppSettings())
        out = tmp_path / "out.jpg"
        processor.save(img, out, AppSettings(), source_path=path)
        loaded = Image.open(out)
        assert loaded.format == "JPEG"

    def test_quality_affects_file_size(self, tmp_path):
        """품질이 높을수록 파일 크기가 커야 함."""
        path = make_jpeg_file(tmp_path, 400, 400)
        photo = make_photo_item(path)
        img = processor.process(photo, AppSettings())

        out_high = tmp_path / "high.jpg"
        out_low = tmp_path / "low.jpg"
        processor.save(img, out_high, AppSettings(output_quality=95))
        processor.save(img, out_low, AppSettings(output_quality=10))

        assert out_high.stat().st_size > out_low.stat().st_size
