"""Tests for the Light Table theme: tokens, QSS rendering and bundled fonts."""
import re

import pytest

from myphotoworks.ui.styles import build_palette, load_fonts, load_theme, render_qss, tokens


def test_all_tokens_are_hex_colours():
    values = tokens.all_tokens()
    assert values["ground"] == tokens.GROUND
    assert values["pick"] == tokens.PICK
    assert "font_family" not in values
    assert all(re.fullmatch(r"#[0-9a-f]{6}", v) for v in values.values())


def test_render_qss_replaces_longest_token_name():
    qss = render_qss("a { color: @text; } b { color: @text_muted; }")
    assert f"color: {tokens.TEXT};" in qss
    assert f"color: {tokens.TEXT_MUTED};" in qss


def test_render_qss_unknown_token_raises():
    with pytest.raises(KeyError):
        render_qss("a { color: @no_such_token; }")


def test_load_theme_resolves_every_token():
    qss = load_theme()
    assert "@" not in qss
    assert tokens.GROUND in qss


def test_theme_icon_urls_point_to_existing_files():
    from pathlib import Path

    urls = re.findall(r'url\("([^"]+)"\)', load_theme())
    assert urls
    assert all(Path(u).is_file() for u in urls)


def test_theme_has_no_legacy_glass_blue():
    qss = load_theme().lower()
    assert "88, 166, 255" not in qss and "58a6ff" not in qss


def test_pick_colour_is_distinct_from_warn_and_danger():
    assert len({tokens.PICK, tokens.WARN, tokens.DANGER}) == 3


def test_selected_list_item_has_border():
    qss = load_theme()
    rule = qss.split("QListWidget::item:selected {", 1)[1].split("}", 1)[0]
    assert f"border: 1px solid {tokens.TEXT_MUTED}" in rule


def test_theme_defines_primary_button_rule():
    assert 'QPushButton[primary="true"]' in load_theme()


def test_color_applies_alpha():
    c = tokens.color(tokens.PANEL, 128)
    assert c.name() == tokens.PANEL
    assert c.alpha() == 128


def test_every_theme_icon_used_in_src_exists(qapp):
    from pathlib import Path

    from myphotoworks.ui.styles import theme_icon

    src = Path(__file__).parents[1] / "src" / "myphotoworks"
    names = {
        m for f in src.rglob("*.py")
        for m in re.findall(r'theme_icon\("([^"]+)"\)', f.read_text(encoding="utf-8"))
    }
    assert names  # guards the regex itself
    styles = src / "ui" / "styles"
    for name in names:
        assert (styles / f"{name}.svg").is_file(), name
        assert not theme_icon(name).isNull(), name


def test_build_palette_uses_tokens(qapp):
    from PyQt6.QtGui import QPalette

    pal = build_palette()
    role = QPalette.ColorRole
    assert pal.color(role.Window).name() == tokens.GROUND
    assert pal.color(role.Link).name() == tokens.TEXT_STRONG
    assert pal.color(QPalette.ColorGroup.Disabled, role.Text).name() == tokens.TEXT_DISABLED


def test_load_fonts_registers_bundled_family(qapp):
    from PyQt6.QtGui import QFontDatabase

    assert tokens.FONT_FAMILY in load_fonts()
    styles = QFontDatabase.styles(tokens.FONT_FAMILY)
    assert {"Regular", "Medium", "SemiBold"} <= set(styles)
