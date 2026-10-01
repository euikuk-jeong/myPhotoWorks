"""Recommendation v2, stage 1 — settings and config migration (plan §4-7).

``AppSettings.recommend_sensitivity`` (float deadband multiplier, normal = 1.0) replaces
``weight_*`` / ``weights()`` / ``show_score``. Old config files that still contain those keys
must load without error and without resetting the other settings.
"""
import dataclasses

from myphotoworks.models.settings import AppSettings
from myphotoworks.utils.config import load_settings, save_settings

OLD_KEYS = {"weight_sharpness", "weight_exposure", "weight_color", "show_score"}


def test_default_sensitivity_is_normal():
    assert AppSettings().recommend_sensitivity == 1.0


def test_weight_fields_and_show_score_are_gone_from_settings():
    s = AppSettings()
    for name in OLD_KEYS | {"weights"}:
        assert not hasattr(s, name), name


def test_save_writes_sensitivity_and_no_old_keys():
    cfg = {}
    save_settings(cfg, AppSettings(recommend_sensitivity=0.6))
    data = cfg["app_settings"]
    assert data["recommend_sensitivity"] == 0.6
    assert OLD_KEYS.isdisjoint(data)
    assert "show_reason" in data


def test_sensitivity_round_trip():
    for value in (0.6, 1.0, 1.5):
        cfg = {}
        save_settings(cfg, AppSettings(recommend_sensitivity=value))
        assert load_settings(cfg).recommend_sensitivity == value


def test_old_config_with_weights_and_show_score_loads_and_keeps_other_values():
    cfg = {"app_settings": {
        "brightness": 5, "show_reason": False, "similarity_slider": 70,
        "weight_sharpness": 0.1, "weight_exposure": 0.1, "weight_color": 0.8,
        "show_score": False, "grouping_ui_version": 2,
    }}
    loaded = load_settings(cfg)
    assert loaded.recommend_sensitivity == 1.0                 # old weights are simply dropped
    expected = dataclasses.replace(
        AppSettings(), brightness=5, show_reason=False, similarity_slider=70
    )
    assert loaded == expected
    assert OLD_KEYS.isdisjoint(vars(loaded))


def test_resaving_a_migrated_config_drops_the_old_keys():
    cfg = {"app_settings": {"weight_sharpness": 0.2, "show_score": True}}
    save_settings(cfg, load_settings(cfg))
    assert OLD_KEYS.isdisjoint(cfg["app_settings"])


def test_garbage_sensitivity_falls_back_to_the_default_without_raising():
    for bad in ("abc", None, -1.0, 0, float("nan")):
        loaded = load_settings({"app_settings": {"recommend_sensitivity": bad}})
        assert loaded.recommend_sensitivity == 1.0, bad


def test_sensitivity_from_a_hand_edited_config_snaps_to_the_nearest_step():
    """The settings combo only knows low / normal / high; the value used must be the shown one."""
    for raw, expected in ((1.2, 1.0), (1.3, 1.5), (5.0, 1.5), (0.7, 0.6), (0.05, 0.6)):
        loaded = load_settings({"app_settings": {"recommend_sensitivity": raw}})
        assert loaded.recommend_sensitivity == expected, raw
