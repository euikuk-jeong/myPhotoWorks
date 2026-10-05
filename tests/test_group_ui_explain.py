"""Explainability, item 1 — the review window shows the measured area of the selected photo.

A checkbox "측정 영역 보기" (default on) switches the boxes. The choice is a view preference, kept
in the main window's config under ``review_show_subject_box`` (not in ``AppSettings``: the settings
panel works on its own copy, so a value written there from the review window could be lost).
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PyQt6.QtCore import pyqtSignal  # noqa: E402
from PyQt6.QtWidgets import QWidget  # noqa: E402

from myphotoworks.models.settings import AppSettings  # noqa: E402
from tests.synthetic import scores  # noqa: E402
from tests.test_grouping import scene  # noqa: E402


def _measured(source="sharpest"):
    return scores(subject_bbox=(100, 80, 220, 200), analysis_size=(512, 384),
                  subject_source=source)


def _review(qtbot, tmp_path, group_scores, **kw):
    from myphotoworks.models.group_session import GroupSession
    from myphotoworks.models.photo_item import PhotoItem
    from myphotoworks.ui.group_review_window import GroupReviewWindow

    photos = []
    for i, s in enumerate(group_scores):
        p = tmp_path / f"f_{i}.jpg"
        scene(i).save(p, "JPEG")
        item = PhotoItem(p)
        item.scores = s
        photos.append(item)
    session = GroupSession(photos, [list(range(len(photos)))], 1.0)
    win = GroupReviewWindow(session, AppSettings(), **kw)
    qtbot.addWidget(win)
    win.resize(1100, 720)
    win.show()
    qtbot.wait(50)
    return win


def _labels(win):
    return [box.label for box, _rect in win._preview.overlay_rects()]


def test_selected_photo_shows_its_own_measured_area(qtbot, tmp_path):
    win = _review(qtbot, tmp_path, [_measured("sharpest"), _measured("af")])
    win._strip.setCurrentRow(0)
    assert _labels(win) == ["가장 선명한 영역"]
    win._strip.setCurrentRow(1)
    assert _labels(win) == ["AF 포인트"]


def test_photo_without_analysis_geometry_shows_no_box(qtbot, tmp_path):
    win = _review(qtbot, tmp_path, [_measured(), scores()])
    win._strip.setCurrentRow(1)
    assert _labels(win) == []
    win._strip.setCurrentRow(0)
    assert _labels(win) == ["가장 선명한 영역"]


def test_two_faces_get_two_boxes_and_one_label(qtbot, tmp_path):
    from tests.synthetic import face_summary

    faces = scores(subject_bbox=(10, 10, 140, 70), analysis_size=(512, 384),
                   subject_source="face", faces=face_summary(n=2))
    win = _review(qtbot, tmp_path, [faces, _measured()])
    win._strip.setCurrentRow(0)
    assert _labels(win) == ["얼굴 2명", ""]


def test_checkbox_defaults_to_on_and_is_named(qtbot, tmp_path):
    win = _review(qtbot, tmp_path, [_measured(), _measured()])
    assert win._overlay_cb.text() == "측정 영역 보기"
    assert win._overlay_cb.isChecked()
    assert win._preview.overlay_visible


def test_checkbox_hides_and_shows_the_box(qtbot, tmp_path):
    win = _review(qtbot, tmp_path, [_measured(), _measured()])
    win._overlay_cb.setChecked(False)
    assert win._preview.overlay_visible is False and _labels(win) == []
    win._overlay_cb.setChecked(True)
    assert _labels(win) == ["가장 선명한 영역"]


def test_the_choice_survives_switching_photos(qtbot, tmp_path):
    win = _review(qtbot, tmp_path, [_measured("sharpest"), _measured("af")])
    win._overlay_cb.setChecked(False)
    win._strip.setCurrentRow(1)
    assert _labels(win) == []


def test_toggle_emits_the_new_choice(qtbot, tmp_path):
    win = _review(qtbot, tmp_path, [_measured(), _measured()])
    with qtbot.waitSignal(win.subject_box_toggled) as sig:
        win._overlay_cb.setChecked(False)
    assert sig.args == [False]


def test_window_starts_with_the_saved_choice(qtbot, tmp_path):
    win = _review(qtbot, tmp_path, [_measured(), _measured()], show_subject_box=False)
    assert not win._overlay_cb.isChecked()
    assert win._preview.overlay_visible is False and _labels(win) == []


# ---- main window keeps the choice in its config -----------------------------------------------

@pytest.fixture
def main(qtbot, monkeypatch):
    import myphotoworks.ui.main_window as mw

    monkeypatch.setattr(mw, "load_config", lambda: {})
    monkeypatch.setattr(mw, "save_config", lambda cfg: None)
    win = mw.MainWindow()
    qtbot.addWidget(win)
    return win


def test_main_window_stores_the_toggled_choice(main):
    main._on_subject_box_toggled(False)
    assert main._cfg["review_show_subject_box"] is False
    main._on_subject_box_toggled(True)
    assert main._cfg["review_show_subject_box"] is True


class _StubReview(QWidget):
    """Stands in for GroupReviewWindow: records how the main window opens it."""

    changed = pyqtSignal()
    subject_box_toggled = pyqtSignal(bool)
    seen: dict = {}

    def __init__(self, session, settings, parent=None, log_dir=None, show_subject_box=True):
        super().__init__()
        _StubReview.seen["show_subject_box"] = show_subject_box


@pytest.mark.parametrize("saved, expected", [(None, True), (False, False), (True, True)])
def test_main_window_opens_the_review_with_the_saved_choice(
        qtbot, main, monkeypatch, saved, expected):
    import myphotoworks.ui.group_review_window as grw

    monkeypatch.setattr(grw, "GroupReviewWindow", _StubReview)
    _StubReview.seen = {}
    if saved is not None:
        main._cfg["review_show_subject_box"] = saved
    main._session = object()                    # any session: the review window is a stub
    main._on_review()
    qtbot.addWidget(main._review_win)
    assert _StubReview.seen["show_subject_box"] is expected


def test_main_window_listens_to_the_review_window_toggle(qtbot, main, monkeypatch):
    import myphotoworks.ui.group_review_window as grw

    monkeypatch.setattr(grw, "GroupReviewWindow", _StubReview)
    main._session = object()
    main._on_review()
    qtbot.addWidget(main._review_win)
    main._review_win.subject_box_toggled.emit(False)
    assert main._cfg["review_show_subject_box"] is False
