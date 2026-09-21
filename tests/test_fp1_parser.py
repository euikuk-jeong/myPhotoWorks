"""Tests for fp1_parser module."""
import textwrap
from pathlib import Path

import pytest

from myphotoworks.recipes.fp1_parser import Fp1Parser, _parse_film_sim, _parse_wb_kelvin
from myphotoworks.recipes.recipe_data import FilmSim, RecipeData

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_fp1(tmp_path: Path, content: str, filename: str = "test.fp1") -> Path:
    p = tmp_path / filename
    p.write_text(textwrap.dedent(content), encoding="utf-8")
    return p


_MINIMAL_FP1 = """\
    <?xml version="1.0" encoding="utf-8"?>
    <ConversionProfile application="FUJIFILM X RAW STUDIO" version="1.0.0">
      <PropertyGroup label="My Recipe" version="1.0.0">
        <FilmSimulation>Velvia</FilmSimulation>
        <GrainEffect>OFF</GrainEffect>
        <GrainEffectSize>SMALL</GrainEffectSize>
        <WhiteBalance>Kelvin</WhiteBalance>
        <Kelvin>5200</Kelvin>
        <WhiteBalanceShiftR>1</WhiteBalanceShiftR>
        <WhiteBalanceShiftB>-2</WhiteBalanceShiftB>
        <HighlightTone>1</HighlightTone>
        <ShadowTone>2</ShadowTone>
        <Color>3</Color>
        <Sharpness>1</Sharpness>
        <NoiseReduction>0</NoiseReduction>
        <Clarity>2</Clarity>
      </PropertyGroup>
    </ConversionProfile>
    """


# ---------------------------------------------------------------------------
# _parse_film_sim
# ---------------------------------------------------------------------------

class TestParseFilmSim:
    @pytest.mark.parametrize("value,expected", [
        ("Provia",          FilmSim.PROVIA),
        ("PROVIA/STANDARD", FilmSim.PROVIA),
        ("Velvia",          FilmSim.VELVIA),
        ("Velvia/Vivid",    FilmSim.VELVIA),
        ("Astia",           FilmSim.ASTIA),
        ("Astia/Soft",      FilmSim.ASTIA),
        ("Classic Chrome",  FilmSim.CLASSIC_CHROME),
        ("Classic",         FilmSim.CLASSIC_CHROME),
        ("Classic Neg",     FilmSim.CLASSIC_NEG),
        ("Classic Negative",FilmSim.CLASSIC_NEG),
        ("ClassicNEGA",     FilmSim.CLASSIC_NEG),
        ("Pro Neg. Hi",     FilmSim.PRO_NEG_HI),
        ("Eterna",          FilmSim.ETERNA),
        ("Eterna/Cinema",   FilmSim.ETERNA),
        ("Acros",           FilmSim.ACROS),
        ("ACROS+R",         FilmSim.ACROS),
    ])
    def test_known_values(self, value, expected):
        assert _parse_film_sim(value) == expected

    def test_unknown_falls_back_to_provia(self):
        assert _parse_film_sim("UnknownSim") == FilmSim.PROVIA


# ---------------------------------------------------------------------------
# _parse_wb_kelvin
# ---------------------------------------------------------------------------

class TestParseWbKelvin:
    def test_kelvin_mode_uses_kelvin_tag(self):
        assert _parse_wb_kelvin("Kelvin", "6400") == 6400

    def test_auto_returns_default(self):
        assert _parse_wb_kelvin("Auto", "5500") == 5500

    def test_daylight_preset(self):
        assert _parse_wb_kelvin("Daylight", "5500") == 5500

    def test_shade_preset(self):
        assert _parse_wb_kelvin("Shade", "5500") == 7500

    def test_numeric_string_in_mode(self):
        assert _parse_wb_kelvin("5800", "0") == 5800

    def test_numeric_with_k_suffix(self):
        assert _parse_wb_kelvin("5800K", "0") == 5800

    def test_kelvin_tag_with_k_suffix(self):
        assert _parse_wb_kelvin("Kelvin", "7500K") == 7500


# ---------------------------------------------------------------------------
# Fp1Parser.parse
# ---------------------------------------------------------------------------

class TestFp1ParserParse:
    def test_parses_name_from_label_attribute(self, tmp_path):
        fp1 = _write_fp1(tmp_path, _MINIMAL_FP1)
        rd = Fp1Parser().parse(fp1)
        assert rd.name == "My Recipe"

    def test_uses_stem_as_name_when_label_missing(self, tmp_path):
        content = """\
            <?xml version="1.0" encoding="utf-8"?>
            <ConversionProfile>
              <PropertyGroup>
                <FilmSimulation>Provia</FilmSimulation>
              </PropertyGroup>
            </ConversionProfile>
            """
        fp1 = _write_fp1(tmp_path, content, filename="my_recipe.fp1")
        rd = Fp1Parser().parse(fp1)
        assert rd.name == "my_recipe"

    def test_film_sim_parsed(self, tmp_path):
        fp1 = _write_fp1(tmp_path, _MINIMAL_FP1)
        rd = Fp1Parser().parse(fp1)
        assert rd.film_sim == FilmSim.VELVIA

    def test_wb_kelvin_parsed(self, tmp_path):
        fp1 = _write_fp1(tmp_path, _MINIMAL_FP1)
        rd = Fp1Parser().parse(fp1)
        assert rd.wb_kelvin == 5200

    def test_wb_shifts_parsed(self, tmp_path):
        fp1 = _write_fp1(tmp_path, _MINIMAL_FP1)
        rd = Fp1Parser().parse(fp1)
        assert rd.wb_shift_r == 1
        assert rd.wb_shift_b == -2

    def test_tone_parsed(self, tmp_path):
        fp1 = _write_fp1(tmp_path, _MINIMAL_FP1)
        rd = Fp1Parser().parse(fp1)
        assert rd.tone_highlight == 1
        assert rd.tone_shadow == 2

    def test_color_parsed(self, tmp_path):
        fp1 = _write_fp1(tmp_path, _MINIMAL_FP1)
        rd = Fp1Parser().parse(fp1)
        assert rd.color == 3

    def test_sharpness_and_clarity_parsed(self, tmp_path):
        fp1 = _write_fp1(tmp_path, _MINIMAL_FP1)
        rd = Fp1Parser().parse(fp1)
        assert rd.sharpness == 1
        assert rd.clarity == 2

    def test_grain_off(self, tmp_path):
        fp1 = _write_fp1(tmp_path, _MINIMAL_FP1)
        rd = Fp1Parser().parse(fp1)
        assert rd.grain_effect == "off"

    def test_grain_weak(self, tmp_path):
        content = _MINIMAL_FP1.replace("<GrainEffect>OFF</GrainEffect>",
                                       "<GrainEffect>WEAK</GrainEffect>")
        fp1 = _write_fp1(tmp_path, content)
        rd = Fp1Parser().parse(fp1)
        assert rd.grain_effect == "weak"

    def test_grain_strong(self, tmp_path):
        content = _MINIMAL_FP1.replace("<GrainEffect>OFF</GrainEffect>",
                                       "<GrainEffect>STRONG</GrainEffect>")
        fp1 = _write_fp1(tmp_path, content)
        rd = Fp1Parser().parse(fp1)
        assert rd.grain_effect == "strong"

    def test_returns_recipe_data_instance(self, tmp_path):
        fp1 = _write_fp1(tmp_path, _MINIMAL_FP1)
        rd = Fp1Parser().parse(fp1)
        assert isinstance(rd, RecipeData)

    def test_missing_property_group_raises(self, tmp_path):
        content = '<?xml version="1.0"?><ConversionProfile/>'
        fp1 = _write_fp1(tmp_path, content)
        with pytest.raises(ValueError, match="PropertyGroup"):
            Fp1Parser().parse(fp1)

    def test_saturation_tag_fallback(self, tmp_path):
        """Legacy <Saturation> tag used when <Color> is absent."""
        content = """\
            <?xml version="1.0" encoding="utf-8"?>
            <ConversionProfile>
              <PropertyGroup label="Leg">
                <FilmSimulation>Provia</FilmSimulation>
                <Saturation>-3</Saturation>
              </PropertyGroup>
            </ConversionProfile>
            """
        fp1 = _write_fp1(tmp_path, content)
        rd = Fp1Parser().parse(fp1)
        assert rd.color == -3

    def test_wb_auto_defaults_to_5500(self, tmp_path):
        content = """\
            <?xml version="1.0" encoding="utf-8"?>
            <ConversionProfile>
              <PropertyGroup label="WB Test">
                <FilmSimulation>Provia</FilmSimulation>
                <WhiteBalance>Auto</WhiteBalance>
                <Kelvin>4000</Kelvin>
              </PropertyGroup>
            </ConversionProfile>
            """
        fp1 = _write_fp1(tmp_path, content)
        rd = Fp1Parser().parse(fp1)
        assert rd.wb_kelvin == 5500


# ---------------------------------------------------------------------------
# Fp1Parser.parse_dir
# ---------------------------------------------------------------------------

class TestFp1ParserParseDir:
    def test_returns_dict_keyed_by_stem(self, tmp_path):
        _write_fp1(tmp_path, _MINIMAL_FP1, "alpha.fp1")
        _write_fp1(tmp_path, _MINIMAL_FP1, "beta.fp1")
        result = Fp1Parser().parse_dir(tmp_path)
        assert set(result.keys()) == {"alpha", "beta"}

    def test_ignores_non_fp1_files(self, tmp_path):
        _write_fp1(tmp_path, _MINIMAL_FP1, "good.fp1")
        (tmp_path / "notes.txt").write_text("ignored")
        result = Fp1Parser().parse_dir(tmp_path)
        assert list(result.keys()) == ["good"]

    def test_matches_extension_case_insensitively(self, tmp_path):
        _write_fp1(tmp_path, _MINIMAL_FP1, "Upper Case.FP1")
        _write_fp1(tmp_path, _MINIMAL_FP1, "lower.fp1")
        result = Fp1Parser().parse_dir(tmp_path)
        assert set(result.keys()) == {"Upper Case", "lower"}

    def test_skips_malformed_files(self, tmp_path):
        _write_fp1(tmp_path, _MINIMAL_FP1, "ok.fp1")
        (tmp_path / "bad.fp1").write_text("not xml at all")
        result = Fp1Parser().parse_dir(tmp_path)
        assert "ok" in result
        assert "bad" not in result

    def test_empty_dir_returns_empty_dict(self, tmp_path):
        result = Fp1Parser().parse_dir(tmp_path)
        assert result == {}

    def test_nonexistent_dir_returns_empty_dict(self, tmp_path):
        result = Fp1Parser().parse_dir(tmp_path / "no_such_dir")
        assert result == {}

    def test_all_values_are_recipe_data(self, tmp_path):
        _write_fp1(tmp_path, _MINIMAL_FP1, "r1.fp1")
        result = Fp1Parser().parse_dir(tmp_path)
        assert all(isinstance(v, RecipeData) for v in result.values())


# ---------------------------------------------------------------------------
# Bundled FP1 files in src/fuji_fp1/
# ---------------------------------------------------------------------------

class TestBundledFp1Files:
    """Verify the FP1 files shipped with the repository parse cleanly."""

    _EXPECTED_SIMS = {
        "provia":              FilmSim.PROVIA,
        "velvia":              FilmSim.VELVIA,
        "astia":               FilmSim.ASTIA,
        "classic_chrome":      FilmSim.CLASSIC_CHROME,
        "pro_neg_hi":          FilmSim.PRO_NEG_HI,
        "eterna":              FilmSim.ETERNA,
        "acros":               FilmSim.ACROS,
        "Agfa Vista 100":      FilmSim.CLASSIC_NEG,
        "Fujichrome Sensia 100": FilmSim.PROVIA,
        "Fujicolor Natura 1600": FilmSim.CLASSIC_NEG,
        "Kodak Ektar 100":     FilmSim.CLASSIC_CHROME,
        "Kodak Portra 400":    FilmSim.CLASSIC_CHROME,
        "Kodak Ultramax 400":  FilmSim.CLASSIC_CHROME,
        "Urban Vintage Chrome": FilmSim.CLASSIC_CHROME,
    }

    @pytest.fixture(scope="class")
    def bundled(self):
        from myphotoworks.recipes.builtin_recipes import BUILTIN_RECIPES
        return BUILTIN_RECIPES

    def test_all_expected_keys_present(self, bundled):
        for key in self._EXPECTED_SIMS:
            assert key in bundled, f"Missing bundled recipe: {key}"

    @pytest.mark.parametrize("key,expected_sim", _EXPECTED_SIMS.items())
    def test_film_sim_correct(self, bundled, key, expected_sim):
        assert bundled[key].film_sim == expected_sim

    def test_all_recipes_have_names(self, bundled):
        for key, rd in bundled.items():
            assert rd.name, f"Recipe '{key}' has no name"

    def test_wb_kelvin_in_valid_range(self, bundled):
        for key, rd in bundled.items():
            assert 2500 <= rd.wb_kelvin <= 10000, \
                f"Recipe '{key}' wb_kelvin={rd.wb_kelvin} out of range"
