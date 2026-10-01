"""Recommendation v2, stage 2 — the published algorithm guide explains the face criteria
(plan §5-5, §1 rule 10). ``guide/algorithm_guide.html`` is a static page, so these are text
checks like the stage-1 ones in ``test_guide.py``; numbers must match the real constants.

The stage-1 limitation notes ("얼굴이나 인물을 따로 찾지는 않습니다", "구도·표정·눈 감음은 보지
않아요") become false with this stage and must go. ``test_guide.py`` still expects the phrase
``가장 선명한 영역”으로 추정`` (no face -> stage-1 subject), so keep it when rewording the note.
"""
from pathlib import Path

import pytest

GUIDE = Path(__file__).resolve().parents[1] / "guide" / "algorithm_guide.html"


@pytest.fixture(scope="module")
def html():
    return GUIDE.read_text(encoding="utf-8")


def test_guide_covers_the_face_topics(html):
    for topic in ("MediaPipe", "인물 그룹", "주요 인물", "눈 감음", "웃음", "얼굴 선명도",
                  "얼굴 노출", "예제 6"):
        assert topic in html, topic


def test_guide_no_longer_says_faces_and_closed_eyes_are_ignored(html):
    assert "얼굴이나 인물을 따로 찾지는 않습니다" not in html
    assert "구도·표정·눈 감음은 보지 않아요" not in html


def test_guide_face_numbers_match_the_real_constants(html):
    from myphotoworks.core.faces import MAIN_FACE_REL_AREA, MIN_FACE_WIDTH_RATIO

    assert f"가장 큰 얼굴 면적의 {round(MAIN_FACE_REL_AREA * 100)}%" in html
    assert f"사진 폭의 {round(MIN_FACE_WIDTH_RATIO * 100)}%" in html


def test_guide_eye_and_smile_numbers_match_the_real_constants(html):
    from myphotoworks.core.faces import EYE_CLOSED_TH
    from myphotoworks.core.ranking import PERSON_TIEBREAK_WEIGHTS, SMILE_DEADBAND, SMILE_PRESENT_TH

    assert f"<b>{EYE_CLOSED_TH:.2f} 이상</b>" in html
    assert f"<b>{round(SMILE_DEADBAND * 100)}%</b> 이내" in html
    assert f"웃음 {round(SMILE_PRESENT_TH * 100)}% 이상" in html
    ws, we, wm = (round(w * 100) for w in PERSON_TIEBREAK_WEIGHTS)
    assert f"얼굴 선명도 {ws} · 얼굴 노출 {we} · 웃음 {wm}" in html


def test_guide_example_6_picks_the_scored_winner_by_closed_eyes():
    from myphotoworks.core.ranking import criterion_rows, reason_label, recommend
    from tests.synthetic import person, scores

    group = [person(n=3, closed=1, smile=0.85, face_sharp=90, face_exposure=82),
             person(n=3, closed=0, smile=0.40, face_sharp=80, face_exposure=78),
             scores(70, 70, 60)]                              # everybody turned away
    rec = recommend(group)
    assert (rec.index, rec.deciding_criterion, rec.tie) == (1, "closed_eyes", False)
    assert reason_label(rec, 3) == "눈 감음 적음"
    bars = [[round(r.relative * 100) for r in criterion_rows(group, i, rec)] for i in (0, 1)]
    assert bars == [[50, 100, 100, 100], [100, 47, 89, 95]]
