"""RecipeData — common data structure for film simulation recipes."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class FilmSim(str, Enum):
    PROVIA = "provia"
    VELVIA = "velvia"
    ASTIA = "astia"
    CLASSIC_CHROME = "classic_chrome"
    CLASSIC_NEG = "classic_neg"
    PRO_NEG_HI = "pro_neg_hi"
    ETERNA = "eterna"
    ACROS = "acros"
    NONE = "none"


@dataclass
class RecipeData:
    """Parsed representation of a film simulation recipe."""
    name: str = ""
    film_sim: FilmSim = FilmSim.NONE
    tone_shadow: int = 0        # -4 ~ +4
    tone_highlight: int = 0     # -4 ~ +4
    color: int = 0              # -4 ~ +4 (saturation)
    sharpness: int = 0          # -4 ~ +4
    grain_effect: str = "off"   # "off" | "weak" | "strong"
    wb_kelvin: int = 5500       # 2500 ~ 10000
    wb_shift_r: int = 0         # -9 ~ +9
    wb_shift_b: int = 0         # -9 ~ +9
    clarity: int = 0            # -5 ~ +5
