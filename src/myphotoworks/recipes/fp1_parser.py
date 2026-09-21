"""Parser for Fujifilm FP1 (XML) recipe files."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from myphotoworks.recipes.recipe_data import FilmSim, RecipeData

# Fujifilm FP1 FilmSimulation tag values → FilmSim enum
_FILM_SIM_MAP: dict[str, FilmSim] = {
    "provia":             FilmSim.PROVIA,
    "provia/standard":    FilmSim.PROVIA,
    "velvia":             FilmSim.VELVIA,
    "velvia/vivid":       FilmSim.VELVIA,
    "astia":              FilmSim.ASTIA,
    "astia/soft":         FilmSim.ASTIA,
    "classic chrome":     FilmSim.CLASSIC_CHROME,
    "classic_chrome":     FilmSim.CLASSIC_CHROME,
    "classic":            FilmSim.CLASSIC_CHROME,
    "classic neg":        FilmSim.CLASSIC_NEG,
    "classic neg.":       FilmSim.CLASSIC_NEG,
    "classic negative":   FilmSim.CLASSIC_NEG,
    "classicnega":        FilmSim.CLASSIC_NEG,
    "classic nega":       FilmSim.CLASSIC_NEG,
    "pro neg. hi":        FilmSim.PRO_NEG_HI,
    "pro neg hi":         FilmSim.PRO_NEG_HI,
    "pro_neg_hi":         FilmSim.PRO_NEG_HI,
    "pro neg. std":       FilmSim.PRO_NEG_HI,
    "eterna":             FilmSim.ETERNA,
    "eterna/cinema":      FilmSim.ETERNA,
    "acros":              FilmSim.ACROS,
    "acros+r":            FilmSim.ACROS,
    "acros+ye":           FilmSim.ACROS,
    "acros+g":            FilmSim.ACROS,
}

# WB preset names → approximate Kelvin values
_WB_PRESET_KELVIN: dict[str, int] = {
    "auto":              5500,
    "daylight":          5500,
    "shade":             7500,
    "cloudy":            6500,
    "fluorescent 1":     6500,
    "fluorescent 2":     4250,
    "fluorescent 3":     3000,
    "incandescent":      3200,
    "underwater":        5500,
}

_GRAIN_MAP: dict[str, str] = {
    "off":    "off",
    "weak":   "weak",
    "strong": "strong",
}


def _parse_film_sim(value: str) -> FilmSim:
    return _FILM_SIM_MAP.get(value.lower().strip(), FilmSim.PROVIA)


def _parse_wb_kelvin(wb_mode: str, kelvin_tag: str) -> int:
    """Resolve WB mode + Kelvin tag to a colour temperature integer."""
    mode = wb_mode.strip().lower()
    if mode in ("kelvin", "color temperature", "colour temperature"):
        try:
            return int(kelvin_tag.replace("K", "").strip())
        except ValueError:
            return 5500
    # Try parsing the mode value itself as a number (e.g. "5500" or "5500K")
    try:
        return int(mode.replace("k", "").strip())
    except ValueError:
        pass
    return _WB_PRESET_KELVIN.get(mode, 5500)


class Fp1Parser:
    """Parse Fujifilm FP1 XML files into RecipeData objects."""

    def parse(self, path: Path) -> RecipeData:
        """Parse a single .fp1 file. Raises ValueError on missing PropertyGroup."""
        tree = ET.parse(path)
        root = tree.getroot()
        pg = root.find("PropertyGroup")
        if pg is None:
            raise ValueError(f"No <PropertyGroup> element in {path}")

        def get(tag: str, default: str = "") -> str:
            el = pg.find(tag)
            return (el.text or "").strip() if el is not None else default

        def get_int(tag: str, default: int = 0) -> int:
            raw = get(tag)
            if not raw:
                return default
            try:
                return int(raw)
            except ValueError:
                return default

        name = (pg.get("label") or "").strip() or path.stem

        grain_raw = get("GrainEffect", "OFF").upper()
        grain = _GRAIN_MAP.get(grain_raw.lower(), "off")

        # Color tag takes priority over legacy Saturation tag
        color_raw = get("Color")
        if not color_raw:
            color_raw = get("Saturation", "0")
        try:
            color = int(color_raw)
        except ValueError:
            color = 0

        return RecipeData(
            name=name,
            film_sim=_parse_film_sim(get("FilmSimulation", "Provia")),
            tone_shadow=get_int("ShadowTone", 0),
            tone_highlight=get_int("HighlightTone", 0),
            color=color,
            sharpness=get_int("Sharpness", 0),
            clarity=get_int("Clarity", 0),
            grain_effect=grain,
            wb_kelvin=_parse_wb_kelvin(get("WhiteBalance", "Auto"), get("Kelvin", "5500")),
            wb_shift_r=get_int("WhiteBalanceShiftR", 0),
            wb_shift_b=get_int("WhiteBalanceShiftB", 0),
        )

    def parse_dir(self, folder: Path) -> dict[str, RecipeData]:
        """Parse all *.fp1 files in *folder*. Key = filename stem.

        Skips files that fail to parse (logs a warning to stderr).
        """
        import sys

        recipes: dict[str, RecipeData] = {}
        if not folder.exists():
            return recipes
        for fp1_file in sorted(f for f in folder.iterdir() if f.suffix.lower() == ".fp1"):
            key = fp1_file.stem
            try:
                recipes[key] = self.parse(fp1_file)
            except Exception as exc:
                print(f"[fp1_parser] skipping {fp1_file.name}: {exc}", file=sys.stderr)
        return recipes
