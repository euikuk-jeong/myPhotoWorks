"""Unit tests for AppSettings, CorrectionMode, ResizeAxis, OutputPathMode."""
import copy
from pathlib import Path

from myphotoworks.models.settings import (
    AppSettings,
    CorrectionMode,
    OutputPathMode,
    ResizeAxis,
)


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


class TestCorrectionMode:
    def test_values(self):
        assert CorrectionMode.NONE.value == "none"
        assert CorrectionMode.AUTO_LEVEL.value == "auto_level"
        assert CorrectionMode.AUTO_CONTRAST.value == "auto_contrast"
        assert CorrectionMode.AUTO_LEVEL_CONTRAST.value == "auto_level_contrast"
        assert CorrectionMode.RECIPE.value == "recipe"

    def test_roundtrip(self):
        for member in CorrectionMode:
            assert CorrectionMode(member.value) == member


class TestAppSettingsDefaults:
    def test_effects_defaults(self):
        s = AppSettings()
        assert s.correction_mode == CorrectionMode.NONE
        assert s.recipe_name == ""
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
        s1 = AppSettings(
            correction_mode=CorrectionMode.AUTO_LEVEL,
            resize_px=2560,
            output_quality=75,
        )
        s2 = copy.copy(s1)
        assert s2.correction_mode == CorrectionMode.AUTO_LEVEL
        assert s2.resize_px == 2560
        assert s2.output_quality == 75
