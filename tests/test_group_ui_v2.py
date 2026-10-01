"""Recommendation v2, stage 1 — UI changes (plan §4-7, Q14', Q16).

* GroupTab: no weight sliders / reset / "show score" check box; a sensitivity control
  (3-step combo, low 1.5x / normal 1.0x / high 0.6x) emitting ``sensitivity_changed``.
* ThumbnailPanel: ``set_options(show_reason)``; no composite-number badge.
* Review window detail panel: bars are group-relative per chain criterion, labelled
  "민감도: ..." instead of "가중치: ...", no composite total.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PyQt6.QtWidgets import QLabel  # noqa: E402

from myphotoworks.models.settings import AppSettings  # noqa: E402
from tests.synthetic import scores  # noqa: E402
from tests.test_group_ui import make_files, run_grouping, scene  # noqa: E402,F401
from tests.test_group_ui import window as window  # noqa: E402,F401

# ---- GroupTab -----------------------------------------------------------------------------


def test_group_tab_has_no_weight_or_score_controls(qtbot):
    from myphotoworks.ui import group_tab
    from myphotoworks.ui.group_tab import GroupTab

    tab = GroupTab(AppSettings())
    qtbot.addWidget(tab)
    for name in ("_w_sliders", "_w_labels", "_reset_btn", "_score_cb", "_on_reset_weights"):
        assert not hasattr(tab, name), name
    assert not hasattr(GroupTab, "weights_changed")
    assert not hasattr(group_tab, "rebalance_weights")


def test_sensitivity_combo_offers_low_normal_high_in_that_order(qtbot):
    from myphotoworks.ui.group_tab import GroupTab

    tab = GroupTab(AppSettings())
    qtbot.addWidget(tab)
    combo = tab._sens_combo
    assert [combo.itemData(i) for i in range(combo.count())] == [1.5, 1.0, 0.6]
    assert [combo.itemText(i) for i in range(combo.count())] == ["낮음", "보통", "높음"]
    assert combo.currentData() == 1.0                       # default = normal


def test_changing_sensitivity_updates_settings_and_emits(qtbot):
    from myphotoworks.ui.group_tab import GroupTab

    s = AppSettings()
    tab = GroupTab(s)
    qtbot.addWidget(tab)
    with qtbot.waitSignal(tab.sensitivity_changed):
        tab._sens_combo.setCurrentIndex(2)
    assert s.recommend_sensitivity == 0.6
    with qtbot.waitSignal(tab.changed):                      # persisted like other options
        tab._sens_combo.setCurrentIndex(0)
    assert s.recommend_sensitivity == 1.5


def test_group_tab_shows_the_stored_sensitivity_without_emitting(qtbot):
    from myphotoworks.ui.group_tab import GroupTab

    tab = GroupTab(AppSettings(recommend_sensitivity=1.5))
    qtbot.addWidget(tab)
    assert tab._sens_combo.currentData() == 1.5
    emitted = []
    tab.sensitivity_changed.connect(lambda: emitted.append(1))
    tab.set_settings(AppSettings(recommend_sensitivity=0.6))
    assert tab._sens_combo.currentData() == 0.6 and not emitted


def test_settings_panel_forwards_sensitivity_and_drops_weights_signal(qtbot):
    from myphotoworks.ui.settings_panel import SettingsPanel

    panel = SettingsPanel(AppSettings())
    qtbot.addWidget(panel)
    assert hasattr(panel, "sensitivity_changed") and not hasattr(panel, "weights_changed")
    with qtbot.waitSignal(panel.sensitivity_changed):
        panel.group_tab._sens_combo.setCurrentIndex(2)


# ---- MainWindow -----------------------------------------------------------------------------


def test_sensitivity_change_rescores_without_regrouping(window, qtbot):  # noqa: F811
    run_grouping(window, qtbot)
    session = window._session
    window._settings.recommend_sensitivity = 0.6
    window._on_sensitivity_changed()
    assert window._session is session
    assert session.to_label_dict()["sensitivity"] == 0.6
    assert session.adopted_count() >= session.group_count()   # every group still has a pick


# ---- ThumbnailPanel ---------------------------------------------------------------------------


def test_thumbnail_options_take_only_show_reason(qtbot):
    from myphotoworks.ui.thumbnail_panel import ThumbnailPanel

    panel = ThumbnailPanel()
    qtbot.addWidget(panel)
    panel.set_options(False)
    assert panel.show_reason is False
    panel.set_options(True)
    assert panel.show_reason is True
    with pytest.raises(TypeError):
        panel.set_options(True, True, (0.5, 0.3, 0.2))
    assert not hasattr(panel, "show_score") and not hasattr(panel, "weights")


def test_thumbnail_paints_with_reason_badges_and_no_score_text(qtbot, tmp_path):
    """Painting a scored group works with the reduced option set (no composite badge)."""
    from myphotoworks.models.group_session import GroupSession
    from myphotoworks.models.photo_item import PhotoItem
    from myphotoworks.ui.thumbnail_panel import ThumbnailPanel

    paths = []
    for i in range(2):
        p = tmp_path / f"t{i}.jpg"
        scene(i).save(p, "JPEG")
        paths.append(p)
    panel = ThumbnailPanel()
    qtbot.addWidget(panel)
    panel.resize(600, 400)
    panel.show()
    panel.add_photos(paths)
    items = panel.all_photos()
    for p, sharp in zip(items, (90, 40), strict=True):
        p.scores = scores(sharp)
    panel.set_session(GroupSession(items, [[0, 1]], 1.0))
    panel.set_options(True)
    panel.grab()
    assert isinstance(items[0], PhotoItem) and items[0].reason.startswith("주제 선명도 우세")


# ---- Review window detail panel -------------------------------------------------------------


def _review(qtbot, tmp_path, sharp_exposure_color, sensitivity=1.0):
    from myphotoworks.models.group_session import GroupSession
    from myphotoworks.models.photo_item import PhotoItem
    from myphotoworks.ui.group_review_window import GroupReviewWindow

    photos = []
    for i, (sh, ex, co) in enumerate(sharp_exposure_color):
        p = tmp_path / f"r_{i}.jpg"
        scene(i).save(p, "JPEG")
        item = PhotoItem(p)
        item.scores = scores(sh, ex, co)
        photos.append(item)
    session = GroupSession(photos, [list(range(len(photos)))], sensitivity)
    win = GroupReviewWindow(session, AppSettings(recommend_sensitivity=sensitivity))
    qtbot.addWidget(win)
    win.resize(1100, 720)
    win.show()
    qtbot.wait(50)
    return win, photos


def test_detail_bars_are_relative_to_the_group_best_per_criterion(qtbot, tmp_path):
    win, photos = _review(qtbot, tmp_path, [(80, 40, 60), (40, 80, 30)])
    win._strip.setCurrentRow(1)
    assert len(win._bars) == 3
    assert [bar.value() for bar in win._bars] == [50, 100, 50]
    win._strip.setCurrentRow(0)
    assert [bar.value() for bar in win._bars] == [100, 50, 100]


def test_detail_panel_has_no_composite_total_and_shows_sensitivity(qtbot, tmp_path):
    win, _ = _review(qtbot, tmp_path, [(80, 40, 60), (40, 80, 30)], sensitivity=0.6)
    assert not hasattr(win, "_total_label")
    texts = [lbl.text() for lbl in win.findChildren(QLabel)]
    assert any("민감도: 높음" in t for t in texts)
    assert not any(t.startswith("가중치") for t in texts)
    assert "종합" not in texts


def test_detail_panel_names_the_deciding_criterion_and_marks_tied_ones(qtbot, tmp_path):
    win, _ = _review(qtbot, tmp_path, [(80.0, 40, 60), (79.5, 85, 60)])
    win._strip.setCurrentRow(1)
    assert "주제 노출 우세" in win._reason_label.text()
    names = [lbl.text() for lbl in win.findChildren(QLabel)]
    assert any("≈" in t for t in names)                     # sharpness row is a tie


def test_detail_panel_says_negligible_difference_when_everything_ties(qtbot, tmp_path):
    win, _ = _review(qtbot, tmp_path, [(80.0, 70.0, 60.0), (80.4, 70.3, 60.2)])
    assert "차이 미미" in win._reason_label.text()
