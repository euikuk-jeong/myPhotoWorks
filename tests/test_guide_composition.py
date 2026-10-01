"""Recommendation v2, stage 3 — the published algorithm guide explains composition, the AF point
and the selection log (plan §1 rule 10). Static page: text checks like ``test_guide.py``; the
numbers must match the real constants.

Stage 2's limitation note "(구도 검사는 앞으로 추가할 계획입니다.)" becomes false and must go
(eye contact / 시선 is still not looked at).
"""
from pathlib import Path

import pytest

GUIDE = Path(__file__).resolve().parents[1] / "guide" / "algorithm_guide.html"


@pytest.fixture(scope="module")
def html():
    return GUIDE.read_text(encoding="utf-8")


def test_guide_covers_the_stage_three_topics(html):
    for topic in ("구도", "수평", "얼굴 잘림", "AF 포인트", "후지필름", "선택 기록", "예제 7"):
        assert topic in html, topic


def test_guide_no_longer_promises_a_composition_check_for_later(html):
    assert "구도 검사는 앞으로 추가할 계획입니다" not in html
    assert "시선" in html                      # still not looked at, and the guide says so


def test_guide_composition_and_af_numbers_match_the_real_constants(html):
    from myphotoworks.core.composition import CUT_MARGIN_RATIO, TILT_FREE_DEG
    from myphotoworks.core.ranking import COMPOSITION_DEADBAND
    from myphotoworks.core.subject import AF_REGION_FRACTION

    assert f"{TILT_FREE_DEG:g}° 이하" in html
    assert f"가장자리에서 사진 크기의 {round(CUT_MARGIN_RATIO * 100)}% 이내" in html
    assert f"짧은 변의 {round(AF_REGION_FRACTION * 100)}%" in html
    assert f"구도 <b>{round(COMPOSITION_DEADBAND)}점</b> 이내" in html


def test_guide_example_7_picks_the_level_photo_by_composition(html):
    from myphotoworks.core.ranking import reason_label, recommend
    from tests.synthetic import scores

    group = [scores(80, 70, 60, tilt=6.2), scores(80, 70, 60, tilt=0.4)]
    rec = recommend(group)
    assert (rec.index, rec.deciding_criterion, rec.tie) == (1, "composition", False)
    assert reason_label(rec, 2) == "구도 우세"
    assert "6.2°" in html and "0.4°" in html
