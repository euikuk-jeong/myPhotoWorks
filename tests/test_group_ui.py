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


def test_status_bar_splits_counts_adopted_and_selected_file(window, qtbot):
    assert window._status_label.text() == "사진 6장"
    assert window._pick_label.text() == ""
    run_grouping(window, qtbot)
    assert window._status_label.text() == "사진 6장, 그룹 4개"
    assert window._pick_label.text() == "채택 4장"
    photo = window._thumb_panel.photos()[0]
    window._show_file(photo)
    text = window._file_label.text()
    assert text.startswith(f"파일명: {photo.source_path.name}")
    size = window._thumb_panel.image_size(photo)
    if size is not None:
        assert text.endswith(f"해상도: {size[0]:,} x {size[1]:,}")


def test_toolbar_marks_process_as_primary_and_view_as_segments(window):
    assert window._process_btn.property("primary") is True
    assert window._all_view_btn.property("segment") is True
    assert window._remove_btn.property("quiet") is True


def test_settings_panel_sections_have_header_bands(qtbot):
    from PyQt6.QtWidgets import QToolButton

    from myphotoworks.ui.section import HEADER_H, Section
    from myphotoworks.ui.settings_panel import SettingsPanel

    panel = SettingsPanel(AppSettings())
    qtbot.addWidget(panel)
    sections = panel.findChildren(Section)
    titles = [s.title() for s in sections]
    assert "보정 방식" in titles and "그룹핑 설정" in titles
    for s in sections:
        header = s.findChild(QToolButton, "sectionHeader")
        assert header.text() == s.title()
        assert s.layout().contentsMargins().top() > HEADER_H   # content starts below the band


def test_section_fold_restores_only_previously_visible_content(qtbot):
    from PyQt6.QtWidgets import QLabel, QVBoxLayout

    from myphotoworks.ui.section import Section

    s = Section("테스트")
    qtbot.addWidget(s)
    layout = QVBoxLayout(s)
    shown, hidden = QLabel("a"), QLabel("b")
    layout.addWidget(shown)
    layout.addWidget(hidden)
    hidden.setVisible(False)          # hidden on purpose (like a progress bar)
    s.show()
    s.set_expanded(False)
    assert not shown.isVisible() and not s.is_expanded()
    s.set_expanded(True)
    assert shown.isVisible() and not hidden.isVisible()


def test_review_page_keys_step_groups_and_toolbar_shows_adopted(qtbot, tmp_path):
    from PyQt6.QtTest import QTest

    from myphotoworks.models.group_session import GroupSession
    from myphotoworks.models.photo_item import PhotoItem
    from myphotoworks.ui.group_review_window import GroupReviewWindow
    from tests.synthetic import scores

    photos = []
    for i in range(4):
        p = tmp_path / f"pg_{i}.jpg"
        scene(i).save(p, "JPEG")
        item = PhotoItem(p)
        item.scores = scores(50, 60, 60)
        photos.append(item)
    session = GroupSession(photos, [[0, 1], [2, 3]], 1.0)
    win = GroupReviewWindow(session, AppSettings())
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)
    ids = [g.id for g in session.groups()]
    assert win._gid == ids[0]
    assert win._adopted_label.text() == f"채택 {session.adopted_count()}장/4장"
    assert win.windowTitle().endswith(f"· 채택 {session.adopted_count()}장/4장")
    QTest.keyClick(win._strip, Qt.Key.Key_PageDown)
    assert win._gid == ids[1]
    QTest.keyClick(win._strip, Qt.Key.Key_PageDown)   # already last: stays
    assert win._gid == ids[1]
    QTest.keyClick(win._strip, Qt.Key.Key_PageUp)
    assert win._gid == ids[0]


def test_adoption_bar_fill_is_proportional_with_visible_minimum():
    from myphotoworks.ui.group_review_window import adoption_bar_fill

    assert adoption_bar_fill(72, 0, 12) == 0
    assert adoption_bar_fill(72, 6, 12) == 36
    assert adoption_bar_fill(72, 12, 12) == 72
    assert adoption_bar_fill(72, 1, 500) == 4      # a sliver stays visible
    assert adoption_bar_fill(72, 3, 0) == 0


def test_group_summary_text_uses_thousands_separator():
    from myphotoworks.ui.group_review_window import GroupSummary

    s = GroupSummary(number=1000, count=1234, adopted=1001, span="", tag="미확인", cover=None)
    assert s.text == "그룹 1,000 · 1,234장 · 채택 1,001  [미확인]"


def test_slider_spin_box_fits_three_digit_negative(qtbot):
    from myphotoworks.ui.settings_panel import _LabeledSlider
    from myphotoworks.ui.styles import tokens

    w = _LabeledSlider(-100, 100, -100)
    qtbot.addWidget(w)
    assert w._spin.width() == tokens.SPIN_WIDTH
    assert w._spin.text() == "-100"


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


def test_adding_photos_keeps_session_and_adds_ungrouped_singles(window, qtbot, tmp_path):
    run_grouping(window, qtbot)
    session = window._session
    before_groups = session.group_count()
    extra = tmp_path / "new.jpg"
    scene(9).save(extra, "JPEG")
    window._thumb_panel.add_photos([extra])
    assert window._session is session
    assert session.group_count() == before_groups + 1
    assert session.added_count() == 1
    new_item = window._thumb_panel.all_photos()[-1]
    assert new_item.is_adopted and new_item.scores is None
    assert window._process_btn.text() == "일괄 적용 (7장)"
    assert "그룹핑 전" in window._status_label.text()
    run_grouping_again = window._settings_panel.group_tab._run_btn
    run_grouping_again.click()
    qtbot.waitUntil(lambda: window._session is not session and window._session is not None,
                    timeout=15000)
    assert window._session.added_count() == 0


def test_rerun_while_previous_thread_is_exiting_is_not_ignored(window, qtbot):
    """done re-enables '다시 그룹핑' before the old thread's finished arrives."""
    run_grouping(window, qtbot)
    first = window._session

    class _Exiting:  # the old worker: done already emitted, thread not yet reaped
        waited = False

        def wait(self):
            _Exiting.waited = True

    window._group_worker = _Exiting()
    window._on_group_run()
    assert _Exiting.waited
    qtbot.waitUntil(lambda: window._session is not None and window._session is not first,
                    timeout=15000)


def test_removing_photos_keeps_groups_and_undo_is_cleared(window, qtbot):
    run_grouping(window, qtbot)
    session = window._session
    panel = window._thumb_panel
    victim = panel.all_photos()[0]
    for i in range(panel.count()):
        if panel.item(i).data(Qt.ItemDataRole.UserRole) is victim:
            panel.setCurrentRow(i)
            panel.item(i).setSelected(True)
    session.set_adopted(victim, not victim.is_adopted)
    assert session.can_undo
    panel.remove_selected()
    assert window._session is session
    assert victim not in panel.all_photos()
    assert not session.can_undo
    assert len(session.photos_flat()) == 5


def test_clear_all_drops_session(window, qtbot):
    run_grouping(window, qtbot)
    window._on_clear_all()
    assert window._session is None
    assert not window._review_btn.isEnabled()


def test_correction_change_marks_scores_stale_and_rescore_keeps_groups(window, qtbot):
    from myphotoworks.models.settings import CorrectionMode

    run_grouping(window, qtbot)
    session = window._session
    tab = window._settings_panel.group_tab
    assert not tab._stale_frame.isVisibleTo(tab)
    groups_before = [[p.source_path.name for p in g.photos] for g in session.groups()]
    victim = window._thumb_panel.all_photos()[1]
    session.set_adopted(victim, True)       # a user edit that must survive
    window._settings.correction_mode = CorrectionMode.AUTO_LEVEL
    window._settings_panel.settings_changed.emit(window._settings)
    assert tab._stale_frame.isVisibleTo(tab)
    tab._stale_btn.click()
    qtbot.waitUntil(lambda: window._rescore_worker is None, timeout=15000)
    assert not tab._stale_frame.isVisibleTo(tab)
    assert window._session is session
    assert [[p.source_path.name for p in g.photos] for g in session.groups()] == groups_before
    assert victim.is_adopted


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


def test_review_window_drop_on_group_moves_current_photo(window, qtbot):
    run_grouping(window, qtbot)
    window._on_review()
    win = window._review_win
    qtbot.addWidget(win)
    session = window._session
    g1 = session.groups()[1]
    win._strip.setCurrentRow(1)
    photo = win._strip.current_photo()
    win._group_list.photo_dropped.emit(g1.id)   # what _GroupList emits on a drop
    assert photo.group_id == g1.id


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


def test_group_tab_has_three_titled_sections(qtbot):
    from PyQt6.QtWidgets import QGroupBox

    from myphotoworks.ui.group_tab import GroupTab

    tab = GroupTab(AppSettings())
    qtbot.addWidget(tab)
    titles = [b.title() for b in tab.findChildren(QGroupBox)]
    assert titles == ["그룹핑 설정", "실행과 결과", "추천 설정"]
    # run button and result live in section 2, sensitivity in section 3
    assert tab._run_box.isAncestorOf(tab._run_btn) and tab._run_box.isAncestorOf(tab._review_btn)
    assert tab._recommend_box.isAncestorOf(tab._sens_combo)
    assert tab._settings_box.isAncestorOf(tab._exif_cb)


def test_exif_option_default_checked_and_global_unchecked(qtbot):
    from myphotoworks.ui.group_tab import GroupTab

    tab = GroupTab(AppSettings())
    qtbot.addWidget(tab)
    assert tab._exif_cb.isChecked()
    assert not tab._global_cb.isChecked()


def test_similarity_levels_are_plain_language_and_cover_full_range():
    from myphotoworks.ui.group_tab import similarity_level

    names = {similarity_level(v)[0] for v in range(0, 101)}
    assert len(names) == 5
    assert "권장" in similarity_level(50)[0]
    assert all(similarity_level(v)[1] for v in range(0, 101))
    low, high = similarity_level(0)[1], similarity_level(100)[1]
    assert "그룹이 많아" in low and "섞일 수" in high


def test_similarity_text_updates_with_slider(qtbot):
    from myphotoworks.ui.group_tab import GroupTab

    tab = GroupTab(AppSettings())
    qtbot.addWidget(tab)
    tab._sim_slider.setValue(95)
    assert "아주 너그러움" in tab._sim_value.text() and "섞일 수" in tab._sim_text.text()


def test_no_widget_level_stylesheet_leaks_into_children(window):
    """A viewport/tab stylesheet would restyle combo popups and tooltips (bright-on-bright)."""
    scroll = window._settings_panel.widget(3)
    assert scroll.styleSheet() == ""
    assert scroll.viewport().styleSheet() == ""
    assert window._settings_panel.group_tab.styleSheet() == ""


def test_theme_defines_tooltip_and_group_scroll_rules():
    from myphotoworks.ui.styles import load_theme

    qss = load_theme()
    assert "QToolTip" in qss and "QScrollArea#groupScroll" in qss


def _wheel(view, x, y, delta=120):
    from PyQt6.QtCore import QPoint, QPointF
    from PyQt6.QtGui import QWheelEvent

    ev = QWheelEvent(QPointF(x, y), QPointF(x, y), QPoint(0, 0), QPoint(0, delta),
                     Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
                     Qt.ScrollPhase.NoScrollPhase, False)
    view.wheelEvent(ev)


def test_review_preview_is_zoomable_and_keeps_view_when_adoption_changes(window, qtbot):
    from myphotoworks.ui.zoom_view import ZoomPanView

    run_grouping(window, qtbot)
    window._on_review()
    win = window._review_win
    qtbot.addWidget(win)
    view = win._preview
    assert isinstance(view, ZoomPanView)
    assert view.relative_zoom() == 1.0
    for _ in range(4):
        _wheel(view, view.width() / 2, view.height() / 2)
    zoomed = view.zoom
    assert view.relative_zoom() > 1.0
    # toggling adoption of the shown photo refreshes the panel but must not reset the zoom
    shown = win._strip.current_photo()
    win._strip.adoption_toggle_requested.emit(shown, not shown.is_adopted)
    assert view.zoom == zoomed
    # moving to another photo starts fitted again
    win._strip.setCurrentRow(1)
    qtbot.waitUntil(lambda: view.key != str(shown.source_path), timeout=3000)
    assert view.relative_zoom() == 1.0


def test_review_preview_loads_detail_image_on_zoom_in(window, qtbot):
    run_grouping(window, qtbot)
    window._on_review()
    win = window._review_win
    qtbot.addWidget(win)
    view = win._preview
    for _ in range(3):
        _wheel(view, view.width() / 2, view.height() / 2)
    key = view.key
    qtbot.waitUntil(lambda: key in win._details, timeout=10000)
    assert view._has_detail
    assert not win._details[key].isNull()


def test_review_preview_unreadable_photo_shows_message(window, qtbot, tmp_path):
    run_grouping(window, qtbot)
    window._on_review()
    win = window._review_win
    qtbot.addWidget(win)
    photo = win._strip.current_photo()
    photo.source_path.write_bytes(b"broken")           # can no longer be decoded
    win._big.pop(str(photo.source_path), None)
    win._preview.clear()
    win._show_current()
    assert win._preview._pixmap is None and "불러올 수 없음" in win._preview._message


def _big_group_review(qtbot, tmp_path, n=24):
    from myphotoworks.models.group_session import GroupSession
    from myphotoworks.models.photo_item import PhotoItem
    from myphotoworks.ui.group_review_window import GroupReviewWindow
    from tests.synthetic import scores

    photos = []
    for i in range(n):
        p = tmp_path / f"big_{i:02d}.jpg"
        scene(i % 5).save(p, "JPEG")
        item = PhotoItem(p)
        item.scores = scores(50 + i, 60, 60)
        photos.append(item)
    session = GroupSession(photos, [list(range(n))], 1.0)
    win = GroupReviewWindow(session, AppSettings())
    qtbot.addWidget(win)
    win.resize(1100, 720)
    win.show()
    qtbot.wait(100)
    return win, photos


def test_review_cards_wrap_and_scroll_vertically(qtbot, tmp_path):
    win, photos = _big_group_review(qtbot, tmp_path)
    strip = win._strip
    assert strip.count() == 24
    assert strip.horizontalScrollBar().maximum() == 0              # no sideways scrolling
    assert strip.verticalScrollBar().maximum() > 0                 # scrolls downwards instead
    rows = {strip.visualItemRect(strip.item(i)).top() - strip.verticalScrollBar().value()
            for i in range(strip.count())}
    assert len(rows) > 1                                           # cards wrapped onto rows
    assert strip.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff


def test_review_strip_wheel_scrolls_down_and_current_card_stays_visible(qtbot, tmp_path):
    win, photos = _big_group_review(qtbot, tmp_path)
    strip = win._strip
    bar = strip.verticalScrollBar()
    assert bar.value() == 0
    bar.setValue(bar.maximum())
    assert bar.value() > 0
    strip.setCurrentRow(0)
    strip.scrollToItem(strip.item(0))
    assert bar.value() == 0
    strip.setCurrentRow(strip.count() - 1)
    strip.scrollToItem(strip.item(strip.count() - 1))
    assert bar.value() == bar.maximum()


def test_review_few_photos_need_no_scrollbar_and_splitter_is_resizable(qtbot, tmp_path):
    win, _ = _big_group_review(qtbot, tmp_path, n=3)
    assert win._strip.verticalScrollBar().maximum() == 0
    assert win._splitter.count() == 2 and not win._splitter.childrenCollapsible()
    before = win._splitter.sizes()
    win._splitter.setSizes([before[0] - 100, before[1] + 100])
    assert win._splitter.sizes()[1] > before[1]


def test_review_toolbar_title_and_score_panel(qtbot, tmp_path):
    win, _photos = _big_group_review(qtbot, tmp_path, n=6)
    assert win._title_label.text() == "그룹 1 / 1"
    assert win._export_btn.property("primary") is True
    photo = win._strip.current_photo()
    assert win._score_title.text() == photo.source_path.name
    assert [lbl.text() for lbl in win._bar_values] == [
        str(round(v)) for v in (photo.scores.subject_sharpness, photo.scores.subject_exposure,
                                photo.scores.color)
    ]


def test_review_toggle_in_scrolled_strip_keeps_scroll_position(qtbot, tmp_path):
    win, photos = _big_group_review(qtbot, tmp_path)
    strip = win._strip
    strip.setCurrentRow(strip.count() - 1)
    strip.scrollToItem(strip.item(strip.count() - 1))
    pos = strip.verticalScrollBar().value()
    last = strip.current_photo()
    win._strip.adoption_toggle_requested.emit(last, not last.is_adopted)
    assert strip.current_photo() is last
    assert strip.verticalScrollBar().value() == pos


def test_review_merge_up_and_down_leave_one_adopted_recommendation(window, qtbot):
    run_grouping(window, qtbot)
    window._on_review()
    win = window._review_win
    qtbot.addWidget(win)
    session = window._session
    # give the first two groups extra adopted photos so a plain merge would keep several
    for g in session.groups()[:2]:
        session.adopt_all(g.id)
    win._reload()
    win._group_list.setCurrentRow(1)
    qtbot.waitUntil(lambda: win._gid == session.groups()[1].id, timeout=3000)
    win._merge_up.click()                            # group 2 merges into group 1
    merged = session.groups()[0]
    assert len(merged.photos) == 4                   # groups are 2 + 2 + 1 + 1 photos
    assert sum(p.is_adopted for p in merged.photos) == 1
    assert next(p for p in merged.photos if p.is_adopted).is_recommended
    # merge down as well (the group that is now below)
    win._gid = merged.id
    win._merge_down.click()
    merged = session.groups()[0]
    assert len(merged.photos) == 5
    assert sum(p.is_adopted for p in merged.photos) == 1
    assert window._process_btn.text().startswith("일괄 적용")


def _many_groups_review(qtbot, tmp_path, n=30):
    from myphotoworks.models.group_session import GroupSession
    from myphotoworks.models.photo_item import PhotoItem
    from myphotoworks.ui.group_review_window import GroupReviewWindow
    from tests.synthetic import scores

    photos = []
    for i in range(n * 2):
        p = tmp_path / f"g_{i:02d}.jpg"
        scene(i % 5).resize((40, 30)).save(p, "JPEG")
        item = PhotoItem(p)
        item.scores = scores(50 + i, 60, 60)
        photos.append(item)
    session = GroupSession(photos, [[2 * k, 2 * k + 1] for k in range(n)], 1.0)
    win = GroupReviewWindow(session, AppSettings())
    qtbot.addWidget(win)
    win.resize(1100, 720)
    win.show()
    qtbot.wait(100)
    return win, session


def test_time_span_formats_single_and_range(tmp_path):
    from datetime import datetime
    from types import SimpleNamespace

    from myphotoworks.models.photo_item import PhotoItem
    from myphotoworks.ui.group_review_window import time_span

    def photo(t):
        p = PhotoItem(tmp_path / "x.jpg")
        p.analysis = SimpleNamespace(taken=t)
        return p

    t1, t2 = datetime(2026, 1, 1, 9, 12, 0), datetime(2026, 1, 1, 9, 14, 5)
    assert time_span([]) == ""
    assert time_span([photo(None), PhotoItem(tmp_path / "y.jpg")]) == ""
    assert time_span([photo(t1)]) == "09:12:00"
    assert time_span([photo(t2), photo(t1)]) == "09:12:00 – 09:14:05"


def test_group_summary_uses_recommended_cover_and_counts(tmp_path):
    from myphotoworks.models.group_session import TAG_EDITED, TAG_TODO, GroupSession
    from myphotoworks.models.photo_item import PhotoItem
    from myphotoworks.ui.group_review_window import group_summary
    from tests.synthetic import scores

    photos = [PhotoItem(tmp_path / f"{i}.jpg") for i in range(3)]
    for p, s in zip(photos, (40, 90, 60), strict=True):
        p.scores = scores(s, s, s)
    session = GroupSession(photos, [[0, 1, 2]], 1.0)
    g = session.groups()[0]
    s = group_summary(session, g, 4)
    assert (s.number, s.count, s.adopted, s.tag) == (4, 3, 1, TAG_TODO)
    assert s.cover is photos[1]
    assert s.text == f"그룹 4 · 3장 · 채택 1  [{TAG_TODO}]"
    session.adopt_all(g.id)
    s = group_summary(session, session.groups()[0], 4)
    assert (s.adopted, s.tag) == (3, TAG_EDITED)


def test_group_summary_without_recommendation_uses_first_photo(tmp_path):
    from myphotoworks.models.group_session import GroupSession
    from myphotoworks.models.photo_item import PhotoItem
    from myphotoworks.ui.group_review_window import group_summary

    photos = [PhotoItem(tmp_path / f"{i}.jpg") for i in range(2)]   # never analysed
    session = GroupSession(photos, [[0, 1]], 1.0)
    assert group_summary(session, session.groups()[0], 1).cover is photos[0]


def test_review_selecting_group_keeps_list_items_and_scroll(qtbot, tmp_path):
    win, session = _many_groups_review(qtbot, tmp_path)
    lst = win._group_list
    bar = lst.verticalScrollBar()
    assert bar.maximum() > 0
    bar.setValue(bar.maximum() // 2)
    pos = bar.value()
    row = lst.row(lst.itemAt(lst.viewport().rect().center()))
    items = [lst.item(i) for i in range(lst.count())]
    target = session.groups()[row].id
    lst.setCurrentRow(row)
    qtbot.waitUntil(lambda: win._gid == target, timeout=3000)
    qtbot.wait(50)
    assert bar.value() == pos                                       # list did not jump
    assert [lst.item(i) for i in range(lst.count())] == items       # updated in place
    assert lst.currentRow() == row
    assert lst.item(row).data(Qt.ItemDataRole.UserRole + 1).tag != "미확인"


def test_review_group_edit_rebuilds_list_but_keeps_scroll(qtbot, tmp_path):
    win, session = _many_groups_review(qtbot, tmp_path)
    lst = win._group_list
    bar = lst.verticalScrollBar()
    bar.setValue(bar.maximum() // 2)
    row = lst.row(lst.itemAt(lst.viewport().rect().center()))
    lst.setCurrentRow(row)
    qtbot.waitUntil(lambda: win._gid == session.groups()[row].id, timeout=3000)
    pos = bar.value()
    win._merge_down.click()                                         # one group fewer
    assert lst.count() == session.group_count() == 29
    assert bar.value() == pos
    assert lst.currentItem().data(Qt.ItemDataRole.UserRole) == win._gid
    assert lst.visualItemRect(lst.currentItem()).intersects(lst.viewport().rect())


def test_review_group_card_paints_without_error(qtbot, tmp_path):
    win, _ = _many_groups_review(qtbot, tmp_path, n=3)
    lst = win._group_list
    assert lst.visualItemRect(lst.item(0)).height() >= 60           # card rows, not text rows
    assert not lst.grab().isNull()


def test_export_labels_failure_shows_warning_instead_of_crashing(window, qtbot, tmp_path,
                                                               monkeypatch):
    import myphotoworks.dev.labels as labels
    import myphotoworks.ui.main_window as mw

    run_grouping(window, qtbot)
    monkeypatch.setattr(mw.QFileDialog, "getSaveFileName",
                        staticmethod(lambda *a, **k: (str(tmp_path / "x.json"), "")))

    def boom(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(labels, "write_labels", boom)
    shown = []
    monkeypatch.setattr(mw.QMessageBox, "warning", staticmethod(lambda *a: shown.append(a[2])))
    window._on_export_labels()
    assert shown and "disk full" in shown[0]


def test_export_labels_success_writes_file(window, qtbot, tmp_path, monkeypatch):
    import json

    import myphotoworks.ui.main_window as mw

    run_grouping(window, qtbot)
    out = tmp_path / "labels.json"
    monkeypatch.setattr(mw.QFileDialog, "getSaveFileName",
                        staticmethod(lambda *a, **k: (str(out), "")))
    monkeypatch.setattr(mw.QMessageBox, "information", staticmethod(lambda *a: None))
    window._on_export_labels()
    assert json.loads(out.read_text(encoding="utf-8"))["schema"] == 1
