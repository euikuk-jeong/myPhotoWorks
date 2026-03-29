"""Unit tests for config save/load settings persistence."""
import json
from pathlib import Path

import pytest

from myphotoworks.models.settings import AppSettings, OutputPathMode, ResizeAxis
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
            "auto_level", "auto_contrast", "brightness", "contrast",
            "resize_enabled", "resize_axis", "resize_px",
            "output_path_mode", "output_custom_dir",
            "output_prefix", "output_suffix", "output_quality",
        }
        assert expected_keys == set(data.keys())

    def test_enum_stored_as_value(self):
        cfg = {}
        save_settings(cfg, AppSettings(resize_axis=ResizeAxis.SHORT))
        assert cfg["app_settings"]["resize_axis"] == "short"

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
            auto_level=True,
            auto_contrast=True,
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

        assert restored.auto_level is True
        assert restored.auto_contrast is True
        assert restored.brightness == -30
        assert restored.contrast == 20
        assert restored.resize_enabled is True
        assert restored.resize_axis == ResizeAxis.SHORT
        assert restored.resize_px == 2560
        assert restored.output_path_mode == OutputPathMode.PER_FILE
        assert restored.output_prefix == "web_"
        assert restored.output_suffix == "_sm"
        assert restored.output_quality == 75

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
