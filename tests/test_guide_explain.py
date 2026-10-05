"""Explainability — the published algorithm guide explains how to read the review window.

Static page: text checks like ``test_guide.py``. The example sentences in the guide must be what
the program really says (``explain.explain_photo``), so the page cannot drift.
"""
from pathlib import Path

import pytest

from tests.synthetic import scores

GUIDE = Path(__file__).resolve().parents[1] / "guide" / "algorithm_guide.html"


@pytest.fixture(scope="module")
def html():
    return GUIDE.read_text(encoding="utf-8")


def test_guide_has_a_section_on_reading_the_reasons(html):
    assert 'id="reading"' in html
    assert "리뷰 창에서 “왜 이 사진?” 읽는 법" in html


def test_guide_example_sentences_are_what_the_program_says(html):
    from myphotoworks.core.explain import explain_photo

    names = ["DSCF9026", "DSCF9025"]
    best = explain_photo([scores(71), scores(53)], 0, names)
    assert best.headline in html
    other = explain_photo([scores(70, 82), scores(68, 61)], 1, names)
    assert other.headline in html


def test_guide_explains_the_measured_area_boxes(html):
    for word in ("측정 영역 보기", "얼굴", "AF 포인트", "가장 선명한 영역", "파랑", "노랑",
                 "초록", "회색 점선", "얼굴 2명"):
        assert word in html


def test_guide_explains_the_fact_badges_and_the_second_line(html):
    for word in ("눈 감음", "얼굴 잘림", "기울어짐", "흐림", "+N", "추천 이유 표시"):
        assert word in html


def test_guide_points_to_the_method_button(html):
    assert "[추천 방식]" in html


def test_guide_describes_the_diverging_bars(html):
    assert "추천 사진을 가운데 선" in html
    for word in ("오른쪽(초록)", "왼쪽(주황)", "회색", "④ 점수 막대"):
        assert word in html
    assert "그룹 최고를 100으로 본 막대" not in html          # the old bars are gone


def test_guide_mentions_the_walkthrough_of_the_group(html):
    assert "“이 그룹에서는”" in html


def test_guide_mentions_the_tooltip_with_the_steps(html):
    assert "단계별" in html and "남음" in html
