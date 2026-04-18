"""Built-in film simulation recipes — loaded from src/fuji_fp1/ at import time."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from myphotoworks.models.settings import CorrectionMode
from myphotoworks.recipes.recipe_data import FilmSim, RecipeData
from myphotoworks.recipes.fp1_parser import Fp1Parser

# ---------------------------------------------------------------------------
# FP1 directory — src/fuji_fp1/ relative to this package
# Layout:  src/myphotoworks/recipes/builtin_recipes.py
#          src/fuji_fp1/*.fp1
# ---------------------------------------------------------------------------

_FP1_DIR: Path = Path(__file__).parent.parent.parent / "fuji_fp1"

# Load at import time: key = filename stem (e.g. "velvia"), value = RecipeData
BUILTIN_RECIPES: dict[str, RecipeData] = Fp1Parser().parse_dir(_FP1_DIR)

# ---------------------------------------------------------------------------
# Display ordering — film sim canonical order, then alphabetical by name
# ---------------------------------------------------------------------------

_SIM_ORDER: dict[FilmSim, int] = {
    FilmSim.PROVIA:         0,
    FilmSim.VELVIA:         1,
    FilmSim.ASTIA:          2,
    FilmSim.CLASSIC_CHROME: 3,
    FilmSim.PRO_NEG_HI:     4,
    FilmSim.ETERNA:         5,
    FilmSim.ACROS:          6,
}

RECIPE_DISPLAY_ORDER: list[str] = sorted(
    BUILTIN_RECIPES.keys(),
    key=lambda k: (_SIM_ORDER.get(BUILTIN_RECIPES[k].film_sim, 99),
                   BUILTIN_RECIPES[k].name),
)

# ---------------------------------------------------------------------------
# Colour square icons — keyed by FilmSim value string
# ---------------------------------------------------------------------------

RECIPE_COLORS: dict[str, str] = {
    FilmSim.PROVIA.value:         "#5B8DB8",
    FilmSim.VELVIA.value:         "#CC3333",
    FilmSim.ASTIA.value:          "#D4A843",
    FilmSim.CLASSIC_CHROME.value: "#7A5C3A",
    FilmSim.PRO_NEG_HI.value:     "#D4732A",
    FilmSim.ETERNA.value:         "#4A8A6A",
    FilmSim.ACROS.value:          "#888888",
}


def recipe_color(recipe: RecipeData) -> str:
    """Return the hex colour for a recipe's film simulation (default grey)."""
    return RECIPE_COLORS.get(recipe.film_sim.value, "#888888")


# ---------------------------------------------------------------------------
# Combo-box item helpers
# ---------------------------------------------------------------------------

@dataclass
class ComboItem:
    """Represents one entry in the correction-mode dropdown."""
    label: str
    mode: CorrectionMode
    recipe_key: str = ""
    color: str = ""           # "" = no icon; non-empty = colour square icon
    is_separator: bool = False  # non-selectable section header


def build_correction_combo_items() -> list[ComboItem]:
    """Return ordered dropdown items for SettingsPanel and _EffectsBar."""
    items: list[ComboItem] = [
        ComboItem("보정 없음",               CorrectionMode.NONE),
        ComboItem("Auto Level",             CorrectionMode.AUTO_LEVEL),
        ComboItem("Auto Contrast",          CorrectionMode.AUTO_CONTRAST),
        ComboItem("Auto Level + Contrast",  CorrectionMode.AUTO_LEVEL_CONTRAST),
        ComboItem("── Fujifilm Recipes ──", CorrectionMode.NONE, is_separator=True),
    ]
    for key in RECIPE_DISPLAY_ORDER:
        rd = BUILTIN_RECIPES[key]
        items.append(
            ComboItem(rd.name, CorrectionMode.RECIPE, key, recipe_color(rd))
        )
    return items


def populate_correction_combo(combo) -> None:
    """Populate a QComboBox with correction-mode items including icons.

    Requires PyQt6. Separated here so recipe_data/effects can be imported
    without a GUI environment (e.g., in tests).
    """
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QBrush, QColor, QIcon, QPainter, QPen, QPixmap

    def _make_icon(color: str, size: int = 14) -> QIcon:
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QBrush(QColor(color)))
        painter.setPen(QPen(QColor(color).darker(130), 1))
        painter.drawRoundedRect(1, 1, size - 2, size - 2, 2, 2)
        painter.end()
        return QIcon(pixmap)

    for item in build_correction_combo_items():
        if item.is_separator:
            combo.addItem(item.label)
            combo.model().item(combo.count() - 1).setEnabled(False)
        elif item.color:
            combo.addItem(_make_icon(item.color), item.label)
        else:
            combo.addItem(item.label)
