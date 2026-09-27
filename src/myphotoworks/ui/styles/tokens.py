"""Light Table design tokens.

Neutral mid-grey workspace so the UI never tints how a photo's colour reads.
Ochre (china-marker) is reserved for picks (adopted / recommended) — nothing else.
The same names are substituted into ``light_table.qss`` as ``@name``.
"""
from __future__ import annotations

from PyQt6.QtGui import QColor

GROUND = "#38383a"          # workspace behind photos
PANEL = "#2c2c2e"           # toolbar, side panel, status bar
SUNKEN = "#232325"          # segmented-control track, list wells
RAISED = "#4a4a4d"          # checked segment, selected item, slider groove
FIELD = "#38383a"           # input fields on panels
LINE = "#4e4e52"            # control borders
DIVIDER = "#3d3d40"         # hairlines inside panels
EDGE = "#242426"            # borders between regions

TEXT = "#e8e8ea"
TEXT_STRONG = "#f2f2f4"
TEXT_MUTED = "#a2a2a8"
TEXT_DISABLED = "#6c6c72"

PRIMARY = "#ececee"         # primary button fill, slider handle, focus
ON_PRIMARY = "#1d1d1f"

PICK = "#cfa54f"            # ochre china-marker: adopted / recommended marks
PICK_TEXT = "#d8b366"       # ochre text on dark surfaces (contrast-safe)
WARN = "#b9794b"            # soft warnings such as the blur badge (rust, apart from PICK)
DANGER = "#d0655c"          # destructive actions such as deleting an original
OK = "#5fb36f"              # completed state such as the "reviewed" group tag

FONT_FAMILY = "IBM Plex Sans KR"
SPIN_WIDTH = 76             # numeric spin boxes: fits "-100" plus the up/down buttons


def all_tokens() -> dict[str, str]:
    """Return every colour token as ``{lower_name: hex}`` for QSS substitution."""
    return {
        name.lower(): value
        for name, value in globals().items()
        if name.isupper() and isinstance(value, str) and value.startswith("#")
    }


def color(hex_value: str, alpha: int = 255) -> QColor:
    """Return a QColor for a token, optionally with alpha (0–255)."""
    c = QColor(hex_value)
    c.setAlpha(alpha)
    return c
