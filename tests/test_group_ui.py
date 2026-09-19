"""Offscreen smoke/behaviour tests for the Lumis Flow UI (group tab, panel, main window)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import piexif  # noqa: E402
import pytest  # noqa: E402
from PIL import ImageFilter  # noqa: E402
from PyQt6.QtCore import Qt  # noqa: E402

from myphotoworks.core.grouping import GroupingMode  # noqa: E402
from myphotoworks.models.settings import AppSettings  # noqa: E402
from tests.test_grouping import scene  # noqa: E402


def make_files(tmp_path):
    specs = [("a1", 1, "12:00:00", 0), ("a2", 1, "12:00:01", 3.0), ("b1", 2, "12:05:00", 0),
             ("b2", 2, "12:05:01", 0.8), ("c1", 3, "12:10:00", 0), ("d1", 4, "12:20:00", 0)]
    paths = []
    for name, seed, t, blur in specs:
        img = scene(seed)
        if blur:
            img = img.filter(ImageFilter.GaussianBlur(blur))
        exif = piexif.dump({"Exif": {piexif.ExifIFD.DateTimeOriginal:
                                     f"2026:01:01 {t}".encode()}})
        p = tmp_path / f"{name}.jpg"
        img.save(p, "JPEG", quality=95, exif=exif)
        paths.append(p)
    return paths


@pytest.fixture
def window(qtbot, tmp_path, monkeypatch):
    import myphotoworks.ui.main_window as mw

    monkeypatch.setattr(mw, "load_config", lambda: {})
    monkeypatch.setattr(mw, "save_config", lambda cfg: None)
    win = mw.MainWindow()
    qtbot.addWidget(win)
    win.show()
    win._thumb_panel.add_photos(make_files(tmp_path))
    return win


def run_grouping(win, qtbot):
    win._settings_panel.group_tab._run_btn.click()
    qtbot.waitUntil(lambda: win._session is not None, timeout=15000)


def test_group_tab_settings_roundtrip(qtbot):
    from myphotoworks.ui.group_tab import GroupTab

    s = AppSettings()
    tab = GroupTab(s)
    qtbot.addWidget(tab)
    tab._mode_combo.setCurrentIndex(2)
    tab._sim_slider.setValue(80)
    tab._gap_spin.setValue(4.5)
    assert s.grouping_mode == GroupingMode.SIMILARITY_ONLY
    assert s.similarity_slider == 80 and s.time_gap == 4.5
    assert not tab._gap_spin.isEnabled()        # time gap unused in similarity-only mode
    with qtbot.waitSignal(tab.weights_changed):
        tab._w_sliders[0].setValue(10)
    assert s.weight_sharpness == 0.1
    tab._on_reset_weights()
    assert s.weights() == (0.5, 0.3, 0.2)


def test_group_tab_review_button_states(qtbot):
    from myphotoworks.ui.group_tab import GroupTab

    tab = GroupTab(AppSettings())
    qtbot.addWidget(tab)
    tab.set_has_photos(True)
    assert tab._run_btn.isEnabled() and not tab._review_btn.isEnabled()
    tab.set_running(True)
    assert not tab._run_btn.isEnabled() and not tab._review_btn.isEnabled()
    assert not tab._mode_combo.isEnabled()
    tab.set_running(False)
    tab.set_done(True)
    assert tab._review_btn.isEnabled() and tab._run_btn.text() == "다시 그룹핑"


def test_initial_state_no_grouping_controls(window):
    assert not window._adopted_only_cb.isEnabled()
    assert not window._group_view_btn.isEnabled()
    assert not window._review_btn.isEnabled()
    assert window._process_btn.text() == "일괄 적용 (6장)"


def test_grouping_flow_and_adopted_filter_drive_process_scope(window, qtbot):
    run_grouping(window, qtbot)
    assert window._session.group_count() == 4
    assert window._review_btn.isEnabled() and window._group_view_btn.isChecked()
    assert len(window._thumb_panel.photos()) == 6
    window._adopted_only_cb.setChecked(True)
    assert len(window._thumb_panel.photos()) == 4     # one recommended per group
    assert window._process_btn.text() == "일괄 적용 (4장)"
    window._adopted_only_cb.setChecked(False)
    assert window._process_btn.text() == "일괄 적용 (6장)"


def test_checkbox_toggle_updates_adoption_and_counts(window, qtbot):
    run_grouping(window, qtbot)
    blurred = next(p for p in window._thumb_panel.all_photos() if p.source_path.stem == "a2")
    assert not blurred.is_adopted
    window._thumb_panel.adoption_toggle_requested.emit(blurred, True)
    assert blurred.is_adopted and window._session.adopted_count() == 5
    window._adopted_only_cb.setChecked(True)
    assert len(window._thumb_panel.photos()) == 5


def test_grouped_view_has_headers_but_photos_list_excludes_them(window, qtbot):
    run_grouping(window, qtbot)
    panel = window._thumb_panel
    assert panel.count() > len(panel.photos())        # headers are extra rows
    assert all(p is not None for p in panel.photos())
    window._all_view_btn.click()
    assert panel.count() == len(panel.photos()) == 6


def test_weight_change_rescores_without_regrouping(window, qtbot):
    run_grouping(window, qtbot)
    session = window._session
    window._settings.weight_sharpness, window._settings.weight_exposure = 0.0, 1.0
    window._settings.weight_color = 0.0
    window._on_weights_changed()
    assert window._session is session
    assert session.adopted_count() == 4


def test_adding_photos_invalidates_session(window, qtbot, tmp_path):
    run_grouping(window, qtbot)
    extra = tmp_path / "new.jpg"
    scene(9).save(extra, "JPEG")
    window._thumb_panel.add_photos([extra])
    assert window._session is None
    assert not window._review_btn.isEnabled()
    assert window._process_btn.text() == "일괄 적용 (7장)"


def test_cancel_returns_to_idle(window, qtbot):
    window._on_group_run()
    window._on_group_cancel()
    qtbot.waitUntil(lambda: window._group_worker is None, timeout=15000)
    assert window._session is None or window._session.group_count() > 0
    assert window._settings_panel.group_tab._run_btn.isEnabled()


def test_review_window_operations(window, qtbot):
    run_grouping(window, qtbot)
    window._on_review()
    win = window._review_win
    assert win is not None
    qtbot.addWidget(win)
    session = window._session
    first = session.groups()[0]
    assert win._strip.count() == len(first.photos)
    # adopt all in the current group, then undo restores the recommended-only state
    win._btn_all.click()
    assert all(p.is_adopted for p in first.photos)
    assert window._session.adopted_count() == 5
    win._btn_undo.click()
    assert sum(p.is_adopted for p in first.photos) == 1
    # keyboard-style toggle via signal
    p = first.photos[1]
    win._strip.adoption_toggle_requested.emit(p, True)
    assert p.is_adopted and window._thumb_panel.photos()  # main list refreshed
    # merge with the group below, then undo
    before = session.group_count()
    win._merge_down.click()
    assert session.group_count() == before - 1
    win._btn_undo.click()
    assert session.group_count() == before
    # selecting another group in the list updates the strip and marks it reviewed
    win._group_list.setCurrentRow(1)
    qtbot.waitUntil(lambda: session.reviewed_count() >= 2, timeout=3000)


def test_review_window_move_and_detach(window, qtbot):
    run_grouping(window, qtbot)
    window._on_review()
    win = window._review_win
    qtbot.addWidget(win)
    session = window._session
    g0, g1 = session.groups()[0], session.groups()[1]
    moved = g0.photos[1]
    win._move_photo(moved, g1.id)
    assert moved.group_id == g1.id
    win._btn_undo.click()
    assert moved.group_id == g0.id
    new_gid = session.detach_photo(moved)
    win._gid = new_gid
    win._after_change("test")
    assert session.group(new_gid).is_single


def test_settings_persist_grouping_options(window):
    tab = window._settings_panel.group_tab
    tab._sim_slider.setValue(35)
    tab._mode_combo.setCurrentIndex(1)
    assert window._settings.similarity_slider == 35
    assert window._settings.grouping_mode == GroupingMode.TIME_FIRST


def test_space_key_toggles_adoption(window, qtbot):
    run_grouping(window, qtbot)
    panel = window._thumb_panel
    photo = panel.photos()[0]
    for i in range(panel.count()):
        if panel.item(i).data(Qt.ItemDataRole.UserRole) is photo:
            panel.setCurrentRow(i)
            break
    before = photo.is_adopted
    qtbot.keyClick(panel, Qt.Key.Key_Space)
    assert photo.is_adopted != before
