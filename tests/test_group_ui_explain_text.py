"""Explainability, item 2 — the review window says why the selected photo is (not) recommended.

Under the preview: line 1 is ``[채택 · 추천] <sentence>`` (``_reason_label``, its tooltip is the
step-by-step trace), line 2 (``_facts_label``, muted) lists facts about the photo and is hidden
when there are none. The sentence uses the photos' file names without extension.
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
        p = tmp_path / f"f_{i}.jpg"
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


def test_recommended_photo_shows_state_and_sentence(qtbot, tmp_path):
    win = _review(qtbot, tmp_path, [scores(71), scores(53)])
    win._strip.setCurrentRow(0)
    assert win._reason_label.text() == (
        "[채택 · 추천] 주제 선명도가 가장 높아요 — 71점, 다음 사진(f_1)은 53점")


def test_other_photo_says_where_it_dropped_out(qtbot, tmp_path):
    win = _review(qtbot, tmp_path, [scores(71), scores(53)])
    win._strip.setCurrentRow(1)
    assert win._reason_label.text() == (
        "[제외] 추천 사진(f_0)보다 주제 선명도가 낮아요 — 53점 vs 71점")


def test_sentence_follows_the_selected_photo(qtbot, tmp_path):
    win = _review(qtbot, tmp_path, [scores(71), scores(53)])
    win._strip.setCurrentRow(1)
    win._strip.setCurrentRow(0)
    assert "가장 높아요" in win._reason_label.text()


def test_tooltip_is_the_step_by_step_trace(qtbot, tmp_path):
    win = _review(qtbot, tmp_path, [scores(70, 90), scores(68, 40), scores(30, 99)])
    win._strip.setCurrentRow(0)
    assert win._reason_label.toolTip() == (
        "1. 주제 선명도: 3장 중 2장 남음 (허용폭 10%)\n"
        "2. 주제 노출: 2장 중 1장 남음 (허용폭 10점)")


def test_trace_uses_the_sessions_sensitivity(qtbot, tmp_path):
    win = _review(qtbot, tmp_path, [scores(70, 90), scores(68, 40)], sensitivity=1.5)
    win._strip.setCurrentRow(0)
    assert "허용폭 15%" in win._reason_label.toolTip()


def test_single_photo_group_has_no_tooltip(qtbot, tmp_path):
    win = _review(qtbot, tmp_path, [scores()])
    assert win._reason_label.text() == "[채택 · 추천] 그룹에 이 사진 하나뿐이에요"
    assert win._reason_label.toolTip() == ""


def test_facts_line_lists_facts_about_the_photo(qtbot, tmp_path):
    win = _review(qtbot, tmp_path, [person(closed=1, tilt=4.0), person(closed=0)])
    win._strip.setCurrentRow(0)
    assert win._facts_label.text() == "눈 감음 1명 · 기울어짐"
    assert win._facts_label.isVisibleTo(win)


def test_facts_line_is_hidden_without_facts(qtbot, tmp_path):
    win = _review(qtbot, tmp_path, [scores(80), scores(79)])
    win._strip.setCurrentRow(0)
    assert win._facts_label.text() == "" and not win._facts_label.isVisibleTo(win)


def test_facts_line_follows_the_selected_photo(qtbot, tmp_path):
    win = _review(qtbot, tmp_path, [person(closed=1), person(closed=0)])
    win._strip.setCurrentRow(0)
    assert win._facts_label.text() == "눈 감음 1명"
    win._strip.setCurrentRow(1)
    assert not win._facts_label.isVisibleTo(win)


def test_photo_without_scores_says_it_was_not_analysed(qtbot, tmp_path):
    win = _review(qtbot, tmp_path, [scores(71), None])
    win._strip.setCurrentRow(1)
    # a photo that could not be analysed is kept (adopted) by default
    assert win._reason_label.text() == "[채택] 분석하지 못한 사진이에요"
    assert win._reason_label.toolTip() == "" and not win._facts_label.isVisibleTo(win)


def test_adoption_state_stays_in_the_prefix(qtbot, tmp_path):
    win = _review(qtbot, tmp_path, [scores(71), scores(53)])
    win._strip.setCurrentRow(1)
    photo = win._strip.current_photo()
    win._session.set_adopted(photo, True)
    win.refresh()
    assert win._reason_label.text().startswith("[채택] 추천 사진(f_0)")
