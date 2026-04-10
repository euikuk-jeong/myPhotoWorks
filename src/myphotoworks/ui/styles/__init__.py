"""UI style resources."""
from __future__ import annotations

import sys
from pathlib import Path


def _styles_dir() -> Path:
    """Return the directory containing style assets.

    Works both in normal Python execution and inside a PyInstaller bundle
    (where sys._MEIPASS points to the extracted temp directory).
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "myphotoworks" / "ui" / "styles"
    return Path(__file__).parent


def load_glass_theme() -> str:
    """Return the glassmorphism QSS stylesheet as a string."""
    qss_path = _styles_dir() / "glass_theme.qss"
    return qss_path.read_text(encoding="utf-8")
