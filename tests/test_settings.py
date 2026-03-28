"""Unit tests for AppSettings, ResizeAxis, OutputPathMode."""
import copy
from pathlib import Path

from myphotoworks.models.settings import AppSettings, OutputPathMode, ResizeAxis


class TestResizeAxis:
    def test_long_value(self):
        assert ResizeAxis.LONG.value == "long"

    def test_short_value(self):
        assert ResizeAxis.SHORT.value == "short"


class TestOutputPathMode:
    def test_enum_values(self):
        assert OutputPathMode.FIRST_FILE.value == "first_file"
        assert OutputPathMode.PER_FILE.value == "per_file"
        assert OutputPathMode.CUSTOM.value == "custom"


class TestAppSettingsDefaults:
    def test_effects_defaults(self):
        s = AppSettings()
        assert s.auto_level is False
        assert s.auto_contrast is False
        assert s.brightness == 0
        assert s.contrast == 0

    def test_resize_defaults(self):
        s = AppSettings()
        assert s.resize_enabled is False
        assert s.resize_axis == ResizeAxis.LONG
        assert s.resize_px == 1920

    def test_output_defaults(self):
        s = AppSettings()
        assert s.output_path_mode == OutputPathMode.FIRST_FILE
        assert s.output_prefix == ""
        assert s.output_suffix == ""
        assert s.output_quality == 90

    def test_output_custom_dir_is_path(self):
        s = AppSettings()
        assert isinstance(s.output_custom_dir, Path)


class TestAppSettingsCopy:
    def test_copy_is_independent(self):
        """copy.copy는 독립적인 인스턴스를 만들어야 함."""
        s1 = AppSettings()
        s2 = copy.copy(s1)
        s2.brightness = 50
        assert s1.brightness == 0

    def test_copy_preserves_values(self):
        s1 = AppSettings(auto_level=True, resize_px=2560, output_quality=75)
        s2 = copy.copy(s1)
        assert s2.auto_level is True
        assert s2.resize_px == 2560
        assert s2.output_quality == 75
