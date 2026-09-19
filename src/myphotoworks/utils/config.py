"""Persistent user configuration (last-used paths, window geometry, settings)."""
from __future__ import annotations

import json
from pathlib import Path

from myphotoworks.core.grouping import GroupingMode
from myphotoworks.models.settings import (
    AppSettings, CorrectionMode, OutputPathMode, ResizeAxis,
)

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
        "correction_mode": settings.correction_mode.value,
        "recipe_name": settings.recipe_name,
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
        "grouping_mode": settings.grouping_mode.value,
        "similarity_slider": settings.similarity_slider,
        "time_gap": settings.time_gap,
        "global_clustering": settings.global_clustering,
        "use_exif_hints": settings.use_exif_hints,
        "weight_sharpness": settings.weight_sharpness,
        "weight_exposure": settings.weight_exposure,
        "weight_color": settings.weight_color,
        "show_reason": settings.show_reason,
        "show_score": settings.show_score,
    }


def load_settings(cfg: dict) -> AppSettings:
    """Deserialize AppSettings from cfg dict. Returns defaults on any error."""
    data = cfg.get(_SETTINGS_KEY)
    if not data:
        return AppSettings()
    try:
        # Backward compat: old configs may have auto_level/auto_contrast bools
        correction_mode_str = data.get("correction_mode")
        if correction_mode_str is None:
            old_al = bool(data.get("auto_level", False))
            old_ac = bool(data.get("auto_contrast", False))
            if old_al and old_ac:
                correction_mode_str = CorrectionMode.AUTO_LEVEL_CONTRAST.value
            elif old_al:
                correction_mode_str = CorrectionMode.AUTO_LEVEL.value
            elif old_ac:
                correction_mode_str = CorrectionMode.AUTO_CONTRAST.value
            else:
                correction_mode_str = CorrectionMode.NONE.value

        return AppSettings(
            correction_mode=CorrectionMode(correction_mode_str),
            recipe_name=str(data.get("recipe_name", "")),
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
            grouping_mode=GroupingMode(data.get("grouping_mode", GroupingMode.AUTO.value)),
            similarity_slider=int(data.get("similarity_slider", 50)),
            time_gap=float(data.get("time_gap", 2.0)),
            global_clustering=bool(data.get("global_clustering", False)),
            use_exif_hints=bool(data.get("use_exif_hints", False)),
            weight_sharpness=float(data.get("weight_sharpness", 0.5)),
            weight_exposure=float(data.get("weight_exposure", 0.3)),
            weight_color=float(data.get("weight_color", 0.2)),
            show_reason=bool(data.get("show_reason", True)),
            show_score=bool(data.get("show_score", True)),
        )
    except Exception:
        return AppSettings()
