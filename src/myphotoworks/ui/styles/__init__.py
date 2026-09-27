"""UI style resources."""
from __future__ import annotations

import re
import sys
from pathlib import Path

from myphotoworks.ui.styles import tokens

_FONT_FILES = (
    "IBMPlexSansKR-Regular.ttf",
    "IBMPlexSansKR-Medium.ttf",
    "IBMPlexSansKR-SemiBold.ttf",
)
_TOKEN_RE = re.compile(r"@([a-z_]+)")


def _package_dir() -> Path:
    """Return the ``myphotoworks`` package directory.

    Works both in normal Python execution and inside a PyInstaller bundle
    (where sys._MEIPASS points to the extracted temp directory).
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "myphotoworks"
    return Path(__file__).parents[2]


def _styles_dir() -> Path:
    return _package_dir() / "ui" / "styles"


def _fonts_dir() -> Path:
    return _package_dir() / "resources" / "fonts"


def render_qss(template: str) -> str:
    """Replace every ``@token`` in *template* with its value.

    Colour tokens become hex values; ``@styles_dir`` becomes the directory
    holding the theme's icons (forward slashes, as QSS ``url()`` expects).
    Raises KeyError for an unknown token so a typo never ships silently.
    """
    values = tokens.all_tokens()
    values["styles_dir"] = _styles_dir().as_posix()
    return _TOKEN_RE.sub(lambda m: values[m.group(1)], template)


def load_theme() -> str:
    """Return the Light Table QSS stylesheet with tokens resolved."""
    qss_path = _styles_dir() / "light_table.qss"
    return render_qss(qss_path.read_text(encoding="utf-8"))


def theme_icon(name: str):
    """QIcon for ``ui/styles/<name>.svg`` (stroked in tokens.TEXT)."""
    from PyQt6.QtGui import QIcon

    return QIcon(str(_styles_dir() / f"{name}.svg"))


def build_palette():
    """Return a QPalette from the tokens.

    QSS does not reach every surface (plain top-level QWidgets, rich-text links,
    item views); the palette covers what the stylesheet leaves to Fusion defaults.
    """
    from PyQt6.QtGui import QColor, QPalette

    role = QPalette.ColorRole
    pal = QPalette()
    for r, value in (
        (role.Window, tokens.GROUND),
        (role.WindowText, tokens.TEXT),
        (role.Base, tokens.FIELD),
        (role.AlternateBase, tokens.PANEL),
        (role.Text, tokens.TEXT),
        (role.PlaceholderText, tokens.TEXT_MUTED),
        (role.Button, tokens.PANEL),
        (role.ButtonText, tokens.TEXT),
        (role.BrightText, tokens.TEXT_STRONG),
        (role.Highlight, tokens.RAISED),
        (role.HighlightedText, tokens.TEXT_STRONG),
        (role.ToolTipBase, tokens.SUNKEN),
        (role.ToolTipText, tokens.TEXT),
        (role.Link, tokens.TEXT_STRONG),
        (role.LinkVisited, tokens.TEXT_MUTED),
    ):
        pal.setColor(r, QColor(value))
    for r in (role.WindowText, role.Text, role.ButtonText):
        pal.setColor(QPalette.ColorGroup.Disabled, r, QColor(tokens.TEXT_DISABLED))
    return pal


def load_fonts() -> list[str]:
    """Register the bundled UI typeface; return the families Qt registered.

    Needs a QGuiApplication. A file Qt cannot load is skipped (Qt then falls
    back to a system font).
    """
    from PyQt6.QtGui import QFontDatabase

    families: list[str] = []
    for name in _FONT_FILES:
        font_id = QFontDatabase.addApplicationFont(str(_fonts_dir() / name))
        if font_id >= 0:
            families.extend(QFontDatabase.applicationFontFamilies(font_id))
    return families
