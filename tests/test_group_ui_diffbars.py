"""Explainability, item 5 — the review window's score panel draws bars from the centre.

``win._bars`` are ``DiffBar`` s: ``value()`` is -100..100, ``verdict()`` better / worse / same /
none. The hint under the file name says how to read them; for the recommended photo itself it says
that every bar sits on the centre line because this photo is the reference.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from myphotoworks.models.settings import AppSettings  # noqa: E402
from tests.synthetic import person, scores  # noqa: E402
from tests.test_grouping import scene  # noqa: E402


def _review(qtbot, tmp_path, group_scores, sensitivity=1.0):
    from myphotoworks.models.group_session import GroupSession
    from myphotoworks.models.photo_item import PhotoItem
    from myphotoworks.ui.group_review_window import GroupReviewWindow

    photos = []
    for i, s in enumerate(group_scores):
        p = tmp_path / f"d_{i}.jpg"
        scene(i).save(p, "JPEG")
        item = PhotoItem(p)
        item.scores = s
        photos.append(item)
    session = GroupSession(photos, [list(range(len(photos)))], sensitivity)
    win = GroupReviewWindow(session, AppSettings())
    qtbot.addWidget(win)
    win.resize(1100, 720)
    win.show()
    qtbot.wait(50)
    return win


def _visible(win):
    return [b for b in win._bars if b.isVisibleTo(win)]


def test_bars_are_diverging_bars(qtbot, tmp_path):
    from myphotoworks.ui.diff_bar import DiffBar

    win = _review(qtbot, tmp_path, [scores(80, 40, 60), scores(40, 80, 30)])
    assert all(isinstance(bar, DiffBar) for bar in win._bars)


def test_other_photo_is_drawn_against_the_recommended_one(qtbot, tmp_path):
    win = _review(qtbot, tmp_path, [scores(80, 40, 60), scores(40, 80, 30)])
    win._strip.setCurrentRow(1)
    assert [bar.value() for bar in _visible(win)] == [-100, 100, -75]
    assert [bar.verdict() for bar in _visible(win)] == ["worse", "better", "worse"]


def test_the_recommended_photo_sits_on_the_centre_line(qtbot, tmp_path):
    win = _review(qtbot, tmp_path, [scores(80, 40, 60), scores(40, 80, 30)])
    win._strip.setCurrentRow(0)
    assert [bar.value() for bar in _visible(win)] == [0, 0, 0]
    assert {bar.verdict() for bar in _visible(win)} == {"same"}


def test_person_bars_are_drawn_against_the_recommended_photo(qtbot, tmp_path):
    win = _review(qtbot, tmp_path, [person(smile=0.8, face_sharp=80, face_exposure=40),
                                    person(smile=0.4, face_sharp=40, face_exposure=80)])
    win._strip.setCurrentRow(1)
    assert [bar.value() for bar in _visible(win)] == [0, -80, -100, 100]
    win._strip.setCurrentRow(0)
    assert [bar.value() for bar in _visible(win)] == [0, 0, 0, 0]


def test_a_photo_without_scores_has_empty_bars(qtbot, tmp_path):
    win = _review(qtbot, tmp_path, [scores(71), None])
    win._strip.setCurrentRow(1)
    assert [bar.value() for bar in _visible(win)] == [0, 0, 0]
    assert {bar.verdict() for bar in _visible(win)} == {"none"}


def test_hint_explains_the_bars(qtbot, tmp_path):
    win = _review(qtbot, tmp_path, [scores(80, 40, 60), scores(40, 80, 30)])
    win._strip.setCurrentRow(1)
    text = win._bar_hint.text()
    assert "추천 사진" in text and "오른쪽" in text and "왼쪽" in text
    assert "가운데" in text


def test_hint_for_the_recommended_photo_says_it_is_the_reference(qtbot, tmp_path):
    win = _review(qtbot, tmp_path, [scores(80, 40, 60), scores(40, 80, 30)])
    win._strip.setCurrentRow(0)
    assert "이 사진이 추천 사진" in win._bar_hint.text()
    win._strip.setCurrentRow(1)
    assert "이 사진이 추천 사진" not in win._bar_hint.text()


def test_value_labels_still_show_the_photos_own_numbers(qtbot, tmp_path):
    win = _review(qtbot, tmp_path, [scores(80, 40, 60), scores(40, 80, 30)])
    win._strip.setCurrentRow(1)
    assert [v.text() for v in win._bar_values if v.isVisibleTo(win)] == ["40", "80", "30"]
