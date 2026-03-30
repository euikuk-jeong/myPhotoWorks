"""Persistent user configuration (last-used paths, window geometry, settings)."""
from __future__ import annotations

import json
from pathlib import Path

from myphotoworks.models.settings import AppSettings, OutputPathMode, ResizeAxis

_CONFIG_PATH = Path.home() / ".myphotoworks" / "config.json"
_SETTINGS_KEY = "app_settings"


def load_config() -> dict:
    try:
        return json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_config(data: dict) -> None:
    _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CONFIG_PATH.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def save_settings(cfg: dict, settings: AppSettings) -> None:
    """Serialize AppSettings into cfg dict (call save_config afterwards)."""
    cfg[_SETTINGS_KEY] = {
        "auto_level": settings.auto_level,
        "auto_contrast": settings.auto_contrast,
        "brightness": settings.brightness,
        "contrast": settings.contrast,
        "resize_enabled": settings.resize_enabled,
        "resize_axis": settings.resize_axis.value,
        "resize_px": settings.resize_px,
        "output_path_mode": settings.output_path_mode.value,
        "output_custom_dir": str(settings.output_custom_dir),
        "output_prefix": settings.output_prefix,
        "output_suffix": settings.output_suffix,
        "output_quality": settings.output_quality,
    }


def load_settings(cfg: dict) -> AppSettings:
    """Deserialize AppSettings from cfg dict. Returns defaults on any error."""
    data = cfg.get(_SETTINGS_KEY)
    if not data:
        return AppSettings()
    try:
        return AppSettings(
            auto_level=bool(data.get("auto_level", False)),
            auto_contrast=bool(data.get("auto_contrast", False)),
            brightness=int(data.get("brightness", 0)),
            contrast=int(data.get("contrast", 0)),
            resize_enabled=bool(data.get("resize_enabled", False)),
            resize_axis=ResizeAxis(data.get("resize_axis", ResizeAxis.LONG.value)),
            resize_px=int(data.get("resize_px", 1920)),
            output_path_mode=OutputPathMode(
                data.get("output_path_mode", OutputPathMode.FIRST_FILE.value)
            ),
            output_custom_dir=Path(data.get("output_custom_dir", ".")),
            output_prefix=str(data.get("output_prefix", "")),
            output_suffix=str(data.get("output_suffix", "")),
            output_quality=int(data.get("output_quality", 90)),
        )
    except Exception:
        return AppSettings()
