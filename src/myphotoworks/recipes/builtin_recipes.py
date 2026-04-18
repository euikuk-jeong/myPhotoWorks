"""Built-in film simulation recipes — bundled at build time."""
from __future__ import annotations

from dataclasses import dataclass

from myphotoworks.models.settings import CorrectionMode
from myphotoworks.recipes.recipe_data import FilmSim, RecipeData

# ---------------------------------------------------------------------------
# Built-in recipe definitions
# Parameters tuned to approximate Fujifilm film simulation characteristics.
# ---------------------------------------------------------------------------

BUILTIN_RECIPES: dict[str, RecipeData] = {
    "provia": RecipeData(
        name="Provia / Standard",
        film_sim=FilmSim.PROVIA,
        tone_shadow=0, tone_highlight=0,
        color=0, sharpness=0, clarity=0,
        grain_effect="off", wb_kelvin=5500,
    ),
    "velvia": RecipeData(
        name="Velvia / Vivid",
        film_sim=FilmSim.VELVIA,
        tone_shadow=1, tone_highlight=1,
        color=2, sharpness=1, clarity=1,
        grain_effect="off", wb_kelvin=5200,
    ),
    "astia": RecipeData(
        name="Astia / Soft",
        film_sim=FilmSim.ASTIA,
        tone_shadow=-1, tone_highlight=-1,
        color=-1, sharpness=0, clarity=0,
        grain_effect="off", wb_kelvin=5600,
    ),
    "classic_chrome": RecipeData(
        name="Classic Chrome",
        film_sim=FilmSim.CLASSIC_CHROME,
        tone_shadow=-1, tone_highlight=0,
        color=-2, sharpness=0, clarity=0,
        grain_effect="weak", wb_kelvin=5800,
    ),
    "pro_neg_hi": RecipeData(
        name="Pro Neg. Hi",
        film_sim=FilmSim.PRO_NEG_HI,
        tone_shadow=0, tone_highlight=1,
        color=0, sharpness=1, clarity=1,
        grain_effect="off", wb_kelvin=5400,
    ),
    "eterna": RecipeData(
        name="Eterna / Cinema",
        film_sim=FilmSim.ETERNA,
        tone_shadow=-2, tone_highlight=-1,
        color=-2, sharpness=-1, clarity=0,
        grain_effect="weak", wb_kelvin=5700,
    ),
    "acros": RecipeData(
        name="Acros (흑백)",
        film_sim=FilmSim.ACROS,
        tone_shadow=0, tone_highlight=0,
        color=0, sharpness=1, clarity=1,
        grain_effect="off", wb_kelvin=5500,
    ),
}

RECIPE_DISPLAY_ORDER = [
    "provia", "velvia", "astia", "classic_chrome", "pro_neg_hi", "eterna", "acros"
]

# Colour used for the small square icon in the dropdown
RECIPE_COLORS: dict[str, str] = {
    "provia":         "#5B8DB8",  # neutral blue
    "velvia":         "#CC3333",  # vivid red
    "astia":          "#D4A843",  # soft yellow
    "classic_chrome": "#7A5C3A",  # vintage brown
    "pro_neg_hi":     "#D4732A",  # warm orange
    "eterna":         "#4A8A6A",  # cinema green
    "acros":          "#888888",  # monochrome grey
}

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
            ComboItem(rd.name, CorrectionMode.RECIPE, key, RECIPE_COLORS[key])
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
