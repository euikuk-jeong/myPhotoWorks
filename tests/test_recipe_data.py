"""Tests for recipe_data module."""
import pytest
from myphotoworks.recipes.recipe_data import FilmSim, RecipeData


def test_film_sim_values():
    assert FilmSim.PROVIA.value == "provia"
    assert FilmSim.ACROS.value == "acros"
    assert FilmSim.NONE.value == "none"


def test_film_sim_roundtrip():
    for member in FilmSim:
        assert FilmSim(member.value) == member


def test_recipe_data_defaults():
    rd = RecipeData()
    assert rd.name == ""
    assert rd.film_sim == FilmSim.NONE
    assert rd.tone_shadow == 0
    assert rd.tone_highlight == 0
    assert rd.color == 0
    assert rd.sharpness == 0
    assert rd.grain_effect == "off"
    assert rd.wb_kelvin == 5500
    assert rd.wb_shift_r == 0
    assert rd.wb_shift_b == 0
    assert rd.clarity == 0


def test_recipe_data_custom():
    rd = RecipeData(
        name="Test",
        film_sim=FilmSim.VELVIA,
        tone_shadow=2,
        tone_highlight=-1,
        color=3,
        wb_kelvin=4800,
    )
    assert rd.name == "Test"
    assert rd.film_sim == FilmSim.VELVIA
    assert rd.tone_shadow == 2
    assert rd.tone_highlight == -1
    assert rd.color == 3
    assert rd.wb_kelvin == 4800
