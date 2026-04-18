"""Tests for recipe_processor and builtin_recipes."""
import numpy as np
import pytest
from PIL import Image

from myphotoworks.recipes.recipe_data import FilmSim, RecipeData
from myphotoworks.recipes.recipe_processor import apply_recipe
from myphotoworks.recipes.builtin_recipes import (
    BUILTIN_RECIPES,
    RECIPE_DISPLAY_ORDER,
    RECIPE_COLORS,
    build_correction_combo_items,
    ComboItem,
)
from myphotoworks.models.settings import CorrectionMode


def _solid(r: int, g: int, b: int, size: int = 64) -> Image.Image:
    img = Image.new("RGB", (size, size))
    img.paste((r, g, b), [0, 0, size, size])
    return img


# ---------------------------------------------------------------------------
# apply_recipe
# ---------------------------------------------------------------------------

class TestApplyRecipe:
    def test_default_recipe_is_near_noop(self):
        img = _solid(128, 100, 80)
        rd = RecipeData()  # all defaults, film_sim=NONE
        out = apply_recipe(img, rd)
        arr_in = np.asarray(img, dtype=float)
        arr_out = np.asarray(out, dtype=float)
        # Should not change at all (film_sim=NONE, all values 0)
        assert np.allclose(arr_in, arr_out, atol=1)

    def test_acros_produces_greyscale(self):
        img = _solid(200, 100, 50)
        rd = RecipeData(film_sim=FilmSim.ACROS)
        out = apply_recipe(img, rd)
        arr = np.asarray(out, dtype=float)
        r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
        assert np.abs(r - g).mean() < 5
        assert np.abs(g - b).mean() < 5

    def test_output_size_preserved(self):
        img = Image.new("RGB", (100, 80))
        rd = RecipeData(film_sim=FilmSim.VELVIA, color=2, sharpness=1)
        out = apply_recipe(img, rd)
        assert out.size == img.size
        assert out.mode == "RGB"

    def test_grain_adds_noise(self):
        img = _solid(128, 128, 128, size=128)
        rd = RecipeData(grain_effect="strong")
        out = apply_recipe(img, rd)
        diff = np.abs(np.asarray(out, dtype=float) - np.asarray(img, dtype=float))
        assert diff.std() > 0


# ---------------------------------------------------------------------------
# BUILTIN_RECIPES
# ---------------------------------------------------------------------------

class TestBuiltinRecipes:
    def test_all_display_order_keys_present(self):
        for key in RECIPE_DISPLAY_ORDER:
            assert key in BUILTIN_RECIPES

    def test_all_recipes_have_names(self):
        for key, rd in BUILTIN_RECIPES.items():
            assert rd.name, f"Recipe '{key}' has no name"

    def test_acros_film_sim(self):
        assert BUILTIN_RECIPES["acros"].film_sim == FilmSim.ACROS

    def test_all_recipes_have_colors(self):
        for key in RECIPE_DISPLAY_ORDER:
            assert key in RECIPE_COLORS
            assert RECIPE_COLORS[key].startswith("#")


# ---------------------------------------------------------------------------
# build_correction_combo_items
# ---------------------------------------------------------------------------

class TestBuildCorrectionComboItems:
    def test_returns_list_of_combo_items(self):
        items = build_correction_combo_items()
        assert isinstance(items, list)
        assert all(isinstance(i, ComboItem) for i in items)

    def test_contains_none_mode(self):
        items = build_correction_combo_items()
        modes = [i.mode for i in items if not i.is_separator]
        assert CorrectionMode.NONE in modes

    def test_contains_all_correction_modes(self):
        items = build_correction_combo_items()
        modes = {i.mode for i in items if not i.is_separator}
        assert CorrectionMode.AUTO_LEVEL in modes
        assert CorrectionMode.AUTO_CONTRAST in modes
        assert CorrectionMode.AUTO_LEVEL_CONTRAST in modes
        assert CorrectionMode.RECIPE in modes

    def test_has_fujifilm_separator(self):
        items = build_correction_combo_items()
        separators = [i for i in items if i.is_separator]
        assert len(separators) >= 1
        assert any("Fujifilm" in s.label for s in separators)

    def test_recipe_items_have_color(self):
        items = build_correction_combo_items()
        recipe_items = [i for i in items if i.mode == CorrectionMode.RECIPE]
        assert len(recipe_items) == len(RECIPE_DISPLAY_ORDER)
        for item in recipe_items:
            assert item.color.startswith("#")
            assert item.recipe_key in BUILTIN_RECIPES
