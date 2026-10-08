"""Recommendation v2, stage 2 — review window detail panel for person groups (plan §4-7, §5-4).

A group with at least one main face shows the four person criteria instead of the three
subject criteria: 눈 감음 / 웃음 / 얼굴 선명도 / 얼굴 노출. Bars are relative to the group best
(``ranking.criterion_rows``); the deciding row is emphasised and ties get "≈" like in stage 1.
Only the rows that are *visible* count here, so the panel may keep a hidden spare slot.

The one-line face summary under the bars (``주요 인물 N명 · 눈 감음 M명 · 웃음 P%``) is the
optional "얼굴별 요약" of plan §5-4 ("표시 검토"): drop its TC if the summary is not wanted.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QLabel  # noqa: E402

from myphotoworks.models.settings import AppSettings  # noqa: E402
from tests.synthetic import person, scores  # noqa: E402
from tests.test_grouping import scene  # noqa: E402


def _review(qtbot, tmp_path, group_scores):
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
    win = GroupReviewWindow(session, AppSettings())
    qtbot.addWidget(win)
    win.resize(1100, 720)
    win.show()
    qtbot.wait(50)
    return win, photos


def _names(win):
    return [n.text() for n in win._bar_names if n.isVisibleTo(win)]


def _values(win):
    return [b.value() for b in win._bars if b.isVisibleTo(win)]


def test_person_group_shows_the_four_person_rows_and_no_subject_rows(qtbot, tmp_path):
    win, _ = _review(qtbot, tmp_path, [person(), person(face_sharp=50)])
    names = _names(win)
    assert len(names) == 4
    for row, word in zip(names, ("눈 감음", "웃음", "얼굴 선명도", "얼굴 노출"), strict=True):
        assert word in row
    assert not any(w in n for n in names for w in ("주제", "색감"))


def test_person_bars_are_drawn_against_the_recommended_photo(qtbot, tmp_path):
    win, _ = _review(qtbot, tmp_path, [person(smile=0.8, face_sharp=80, face_exposure=40),
                                       person(smile=0.4, face_sharp=40, face_exposure=80)])
    win._strip.setCurrentRow(1)
    # nobody blinks: the eye bar is on the centre; smile and sharpness worse, exposure better
    assert _values(win) == [0, -80, -100, 100]
    win._strip.setCurrentRow(0)                        # the recommended photo is the centre line
    assert _values(win) == [0, 0, 0, 0]


def test_detail_panel_names_the_deciding_face_criterion(qtbot, tmp_path):
    win, _ = _review(qtbot, tmp_path, [person(closed=1), person(closed=0)])
    win._strip.setCurrentRow(1)
    assert "눈 감은 사람이 가장 적어요" in win._reason_label.text()


def test_tied_person_rows_are_marked_with_the_approx_sign(qtbot, tmp_path):
    win, _ = _review(qtbot, tmp_path, [person(face_sharp=80.0, face_exposure=40),
                                       person(face_sharp=79.5, face_exposure=85)])
    win._strip.setCurrentRow(1)
    names = _names(win)
    assert "≈" in names[0] and "≈" in names[2] and "≈" not in names[3]    # exposure decides


def test_a_faceless_photo_of_a_person_group_shows_empty_bars(qtbot, tmp_path):
    win, _ = _review(qtbot, tmp_path, [person(), scores(90, 90, 90)])
    win._strip.setCurrentRow(1)
    assert _values(win) == [0, 0, 0, 0]
    assert win._facts_label.text() == "얼굴 인식 안 됨"     # fact line; the sentence says why
    assert "얼굴이 인식되지 않아" in win._reason_label.text()
    assert [v.text() for v in win._bar_values if v.isVisibleTo(win)] == ["-"] * 4   # no fake "0"


def test_detail_panel_summarises_the_faces_of_the_photo(qtbot, tmp_path):
    win, _ = _review(qtbot, tmp_path, [person(n=2, closed=1, smile=0.6), person(n=2, closed=0)])
    win._strip.setCurrentRow(0)
    texts = [lbl.text() for lbl in win.findChildren(QLabel) if lbl.isVisibleTo(win)]
    assert any("주요 인물 2명" in t and "눈 감음 1명" in t and "웃음 60%" in t for t in texts)
