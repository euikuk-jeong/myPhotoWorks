"""Stage-3 refinement — the algorithm guide mentions what changed (text checks like
``test_guide.py``; numbers must match the real constants).

* diagonals: lines more than ``TILT_SEARCH_DEG`` off both axes are not measured as a tilt
* the person chain also keeps photos whose face is black / blown out / without detail out of the
  race while a usable one exists
* a review session keeps one selection-log file that is updated, not one per close
"""
from pathlib import Path

import pytest

GUIDE = Path(__file__).resolve().parents[1] / "guide" / "algorithm_guide.html"


@pytest.fixture(scope="module")
def html():
    return GUIDE.read_text(encoding="utf-8")


def test_guide_explains_that_diagonals_are_not_tilt(html):
    from myphotoworks.core.composition import TILT_SEARCH_DEG

    assert f"{TILT_SEARCH_DEG:g}° 넘게 기울어진 직선" in html
    assert "대각선" in html


def test_guide_says_the_person_chain_has_a_failure_gate_too(html):
    assert "얼굴이 거의 새까맣거나" in html


def test_guide_says_a_review_updates_one_log_file(html):
    assert "기록 파일 하나를 갱신" in html
