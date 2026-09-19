"""Unit tests for config save/load settings persistence."""
import json
from pathlib import Path

import pytest

from myphotoworks.models.settings import (
    AppSettings, CorrectionMode, OutputPathMode, ResizeAxis,
)
from myphotoworks.utils.config import load_settings, save_settings


class TestSaveSettings:
    def test_saves_to_cfg_dict(self):
        cfg = {}
        settings = AppSettings()
        save_settings(cfg, settings)
        assert "app_settings" in cfg

    def test_all_fields_present(self):
        cfg = {}
        save_settings(cfg, AppSettings())
        data = cfg["app_settings"]
        expected_keys = {
            "correction_mode", "recipe_name", "brightness", "contrast",
            "resize_enabled", "resize_axis", "resize_px",
            "output_path_mode", "output_custom_dir",
            "output_prefix", "output_suffix", "output_quality",
            "grouping_mode", "similarity_slider", "time_gap",
            "weight_sharpness", "weight_exposure", "weight_color",
            "show_reason", "show_score",
        }
        assert expected_keys == set(data.keys())

    def test_enum_stored_as_value(self):
        cfg = {}
        save_settings(cfg, AppSettings(resize_axis=ResizeAxis.SHORT))
        assert cfg["app_settings"]["resize_axis"] == "short"

    def test_correction_mode_stored_as_value(self):
        cfg = {}
        save_settings(cfg, AppSettings(correction_mode=CorrectionMode.AUTO_LEVEL))
        assert cfg["app_settings"]["correction_mode"] == "auto_level"

    def test_path_stored_as_string(self):
        cfg = {}
        save_settings(cfg, AppSettings(output_custom_dir=Path("/some/path")))
        assert isinstance(cfg["app_settings"]["output_custom_dir"], str)


class TestLoadSettings:
    def test_returns_defaults_when_empty_cfg(self):
        settings = load_settings({})
        assert settings == AppSettings()

    def test_returns_defaults_on_missing_key(self):
        settings = load_settings({"other_key": 123})
        assert settings == AppSettings()

    def test_roundtrip_default_values(self):
        cfg = {}
        original = AppSettings()
        save_settings(cfg, original)
        restored = load_settings(cfg)
        assert restored == original

    def test_roundtrip_custom_values(self):
        cfg = {}
        original = AppSettings(
            correction_mode=CorrectionMode.AUTO_LEVEL_CONTRAST,
            brightness=-30,
            contrast=20,
            resize_enabled=True,
            resize_axis=ResizeAxis.SHORT,
            resize_px=2560,
            output_path_mode=OutputPathMode.PER_FILE,
            output_custom_dir=Path("/tmp/out"),
            output_prefix="web_",
            output_suffix="_sm",
            output_quality=75,
        )
        save_settings(cfg, original)
        restored = load_settings(cfg)

        assert restored.correction_mode == CorrectionMode.AUTO_LEVEL_CONTRAST
        assert restored.brightness == -30
        assert restored.contrast == 20
        assert restored.resize_enabled is True
        assert restored.resize_axis == ResizeAxis.SHORT
        assert restored.resize_px == 2560
        assert restored.output_path_mode == OutputPathMode.PER_FILE
        assert restored.output_prefix == "web_"
        assert restored.output_suffix == "_sm"
        assert restored.output_quality == 75

    def test_roundtrip_recipe_mode(self):
        cfg = {}
        original = AppSettings(
            correction_mode=CorrectionMode.RECIPE,
            recipe_name="velvia",
        )
        save_settings(cfg, original)
        restored = load_settings(cfg)
        assert restored.correction_mode == CorrectionMode.RECIPE
        assert restored.recipe_name == "velvia"

    def test_roundtrip_all_output_path_modes(self):
        for mode in OutputPathMode:
            cfg = {}
            save_settings(cfg, AppSettings(output_path_mode=mode))
            restored = load_settings(cfg)
            assert restored.output_path_mode == mode

    def test_roundtrip_all_resize_axes(self):
        for axis in ResizeAxis:
            cfg = {}
            save_settings(cfg, AppSettings(resize_axis=axis))
            restored = load_settings(cfg)
            assert restored.resize_axis == axis

    def test_returns_defaults_on_corrupt_data(self):
        """잘못된 데이터가 있어도 기본값으로 폴백해야 함."""
        cfg = {"app_settings": {"resize_axis": "invalid_value"}}
        settings = load_settings(cfg)
        assert settings == AppSettings()

    def test_cfg_is_json_serializable_after_save(self, tmp_path):
        """save_settings 후 cfg가 JSON으로 직렬화 가능해야 함."""
        cfg = {}
        save_settings(cfg, AppSettings(output_custom_dir=Path("/tmp")))
        json_str = json.dumps(cfg)
        assert json_str  # 직렬화 성공

    def test_backward_compat_auto_level_bool(self):
        """구 config (auto_level=True) → CorrectionMode.AUTO_LEVEL 변환."""
        cfg = {"app_settings": {"auto_level": True, "auto_contrast": False}}
        restored = load_settings(cfg)
        assert restored.correction_mode == CorrectionMode.AUTO_LEVEL

    def test_backward_compat_auto_contrast_bool(self):
        """구 config (auto_contrast=True) → CorrectionMode.AUTO_CONTRAST 변환."""
        cfg = {"app_settings": {"auto_level": False, "auto_contrast": True}}
        restored = load_settings(cfg)
        assert restored.correction_mode == CorrectionMode.AUTO_CONTRAST

    def test_backward_compat_both_bools(self):
        """구 config (auto_level=True, auto_contrast=True) → AUTO_LEVEL_CONTRAST 변환."""
        cfg = {"app_settings": {"auto_level": True, "auto_contrast": True}}
        restored = load_settings(cfg)
        assert restored.correction_mode == CorrectionMode.AUTO_LEVEL_CONTRAST


class TestGroupingSettingsRoundTrip:
    def test_round_trip(self):
        from myphotoworks.core.grouping import GroupingMode
        from myphotoworks.utils.config import load_settings

        s = AppSettings(
            grouping_mode=GroupingMode.TIME_FIRST, similarity_slider=70, time_gap=3.5,
            weight_sharpness=0.2, weight_exposure=0.5, weight_color=0.3,
            show_reason=False, show_score=False,
        )
        cfg = {}
        save_settings(cfg, s)
        loaded = load_settings(cfg)
        assert loaded.grouping_mode == GroupingMode.TIME_FIRST
        assert loaded.similarity_slider == 70
        assert loaded.time_gap == 3.5
        assert loaded.weights() == (0.2, 0.5, 0.3)
        assert loaded.show_reason is False and loaded.show_score is False

    def test_old_config_without_grouping_keys_uses_defaults(self):
        from myphotoworks.core.grouping import GroupingMode
        from myphotoworks.utils.config import load_settings

        cfg = {"app_settings": {"correction_mode": "none", "brightness": 5}}
        loaded = load_settings(cfg)
        assert loaded.brightness == 5
        assert loaded.grouping_mode == GroupingMode.AUTO
        assert loaded.weights() == (0.5, 0.3, 0.2)
