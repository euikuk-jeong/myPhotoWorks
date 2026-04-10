"""UI style resources."""
from __future__ import annotations

from pathlib import Path


def load_glass_theme() -> str:
    """Return the glassmorphism QSS stylesheet as a string."""
    qss_path = Path(__file__).parent / "glass_theme.qss"
    return qss_path.read_text(encoding="utf-8")
