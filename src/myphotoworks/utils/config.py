"""Persistent user configuration (last-used paths, window geometry, etc.)."""
from __future__ import annotations

import json
from pathlib import Path

_CONFIG_PATH = Path.home() / ".myphotoworks" / "config.json"


def load_config() -> dict:
    try:
        return json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_config(data: dict) -> None:
    _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CONFIG_PATH.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
