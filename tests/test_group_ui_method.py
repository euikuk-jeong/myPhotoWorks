"""Explainability, item 4 — the review window's [추천 방식] button opens a dialog with the chain.

The dialog (``ui.method_dialog.MethodDialog``) shows the overview of the *selected group*: the
person chain for a group with a face, the general chain otherwise, with the deadbands of the
session's sensitivity. A button opens the online guide.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QLabel, QPushButton  # noqa: E402

from myphotoworks.models.settings import AppSettings  # noqa: E402
from tests.synthetic import person, scores  # noqa: E402
from tests.test_grouping import scene  # noqa: E402


def _review(qtbot, tmp_path, groups, sensitivity=1.0):
    """``groups``: list of lists of QualityScores; one group each."""
    from myphotoworks.models.group_session import GroupSession
    from myphotoworks.models.photo_item import PhotoItem
    from myphotoworks.ui.group_review_window import GroupReviewWindow

    photos, indexes, n = [], [], 0
    for g, group_scores in enumerate(groups):
        idx = []
        for s in group_scores:
            p = tmp_path / f"g{g}_{n}.jpg"
            scene(n).save(p, "JPEG")
            item = PhotoItem(p)
            item.scores = s
            photos.append(item)
            idx.append(n)
            n += 1
        indexes.append(idx)
    session = GroupSession(photos, indexes, sensitivity)
    win = GroupReviewWindow(session, AppSettings())
    qtbot.addWidget(win)
    win.resize(1100, 720)
    win.show()
    qtbot.wait(50)
    return win, session


def _dialog_text(win):
    dialog = win._method_dialog
    return dialog.windowTitle(), "\n".join(
        lbl.text() for lbl in dialog.findChildren(QLabel) if lbl.text())


def test_button_is_next_to_the_reason_line(qtbot, tmp_path):
    win, _ = _review(qtbot, tmp_path, [[scores(71), scores(53)]])
    assert win._method_btn.text() == "추천 방식"
    assert win._method_btn.isVisibleTo(win)


def test_general_group_shows_the_general_chain(qtbot, tmp_path):
    win, _ = _review(qtbot, tmp_path, [[scores(71), scores(53)]])
    win._method_btn.click()
    title, text = _dialog_text(win)
    assert title == "일반 그룹의 추천 순서"
    assert "1. 주제 선명도 — 허용폭 10%" in text and "4. 색감 — 허용폭 10점" in text
    assert "끝까지 동점이면" in text


def test_person_group_shows_the_person_chain(qtbot, tmp_path):
    win, _ = _review(qtbot, tmp_path, [[person(closed=1), person(closed=0)]])
    win._method_btn.click()
    title, text = _dialog_text(win)
    assert title == "인물 그룹의 추천 순서"
    assert "2. 눈 감음 — 같은 값만 (적을수록 좋아요)" in text


def test_dialog_uses_the_sessions_sensitivity(qtbot, tmp_path):
    win, _ = _review(qtbot, tmp_path, [[scores(71), scores(53)]], sensitivity=1.5)
    win._method_btn.click()
    _, text = _dialog_text(win)
    assert "1. 주제 선명도 — 허용폭 15%" in text and "지금은 낮음이에요" in text


def test_dialog_follows_the_selected_group(qtbot, tmp_path):
    win, session = _review(qtbot, tmp_path, [[person(closed=1), person(closed=0)],
                                             [scores(71), scores(53)]])
    first, second = [g.id for g in session.groups()]
    win._select_group(first)
    win._method_btn.click()
    assert _dialog_text(win)[0] == "인물 그룹의 추천 순서"
    win._method_dialog.close()
    win._select_group(second)
    win._method_btn.click()
    assert _dialog_text(win)[0] == "일반 그룹의 추천 순서"


def test_an_open_dialog_follows_a_group_change(qtbot, tmp_path):
    win, session = _review(qtbot, tmp_path, [[person(closed=1), person(closed=0)],
                                             [scores(71), scores(53)]])
    first, second = [g.id for g in session.groups()]
    win._select_group(first)
    win._method_btn.click()
    dialog = win._method_dialog
    win._select_group(second)                         # the dialog stays open and follows
    assert win._method_dialog is dialog and dialog.isVisible()
    assert dialog.windowTitle() == "일반 그룹의 추천 순서"


def test_closing_the_review_window_closes_the_dialog(qtbot, tmp_path):
    win, _ = _review(qtbot, tmp_path, [[scores(71), scores(53)]])
    win._method_btn.click()
    dialog = win._method_dialog
    win.close()
    assert not dialog.isVisible()


def test_dialog_walks_through_the_selected_group(qtbot, tmp_path):
    win, _ = _review(qtbot, tmp_path, [[scores(71), scores(53)]])
    win._method_btn.click()
    _, text = _dialog_text(win)
    assert "이 그룹에서는" in text
    assert "1. 주제 선명도: 2장 중 1장 남음 (허용폭 10%) — g0_0" in text
    assert "→ 추천: g0_0" in text


def test_dialog_has_no_walkthrough_for_a_single_photo_group(qtbot, tmp_path):
    win, _ = _review(qtbot, tmp_path, [[scores(71)]])
    win._method_btn.click()
    _, text = _dialog_text(win)
    assert "이 그룹에서는" not in text
    assert "1. 주제 선명도 — 허용폭 10%" in text            # the chain itself is still shown


def test_an_open_dialog_follows_the_walkthrough_of_the_selected_group(qtbot, tmp_path):
    win, session = _review(qtbot, tmp_path, [[person(closed=1), person(closed=0)],
                                             [scores(71), scores(53)]])
    first, second = [g.id for g in session.groups()]
    win._select_group(first)
    win._method_btn.click()
    assert "→ 추천: g0_1" in _dialog_text(win)[1]
    win._select_group(second)
    _, text = _dialog_text(win)
    assert "→ 추천: g1_2" in text and "g0_1" not in text


def test_clicking_again_does_not_pile_up_dialogs(qtbot, tmp_path):
    win, _ = _review(qtbot, tmp_path, [[scores(71), scores(53)]])
    win._method_btn.click()
    first = win._method_dialog
    win._method_btn.click()
    assert win._method_dialog is first


def test_dialog_opens_the_online_guide(qtbot, tmp_path, monkeypatch):
    import myphotoworks.ui.method_dialog as md

    opened = []
    monkeypatch.setattr(md, "open_guide", lambda parent=None: opened.append(parent) or True)
    win, _ = _review(qtbot, tmp_path, [[scores(71), scores(53)]])
    win._method_btn.click()
    buttons = {b.text(): b for b in win._method_dialog.findChildren(QPushButton)}
    assert set(buttons) == {"설명서 열기", "닫기"}
    buttons["설명서 열기"].click()
    assert len(opened) == 1


def test_dialog_close_button_closes_it(qtbot, tmp_path):
    win, _ = _review(qtbot, tmp_path, [[scores(71), scores(53)]])
    win._method_btn.click()
    buttons = {b.text(): b for b in win._method_dialog.findChildren(QPushButton)}
    buttons["닫기"].click()
    assert not win._method_dialog.isVisible()
