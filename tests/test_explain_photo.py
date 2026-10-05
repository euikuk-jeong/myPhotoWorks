"""Explainability, item 2 — one sentence on why a photo is (not) recommended.

``explain_photo(group, index, names, scale) -> Explanation`` for the photo ``group[index]``:

* ``headline``    — the sentence ("~해요" style). For the recommended photo it names the deciding
  criterion with the photo's value and the runner-up's; for any other photo it names the step
  where the photo dropped out, against the recommended photo.
* ``trace_lines`` — one line per visible step of the chain (the tooltip).
* ``facts``       — facts about this photo (closed eyes, tilt, blur ...), shown on a second line.

Values are 0..100 points (closed eyes: people, smile: percent). ``names`` are the display names
of the photos of ``group``, in the same order.
"""
import pytest

from myphotoworks.core.composition import composition_score
from tests.synthetic import person, scores

NAMES = ["A", "B", "C"]


def _explain(group, index, scale=1.0):
    from myphotoworks.core.explain import explain_photo

    return explain_photo(group, index, NAMES[: len(group)], scale)


def _said(group, index, scale=1.0):
    return _explain(group, index, scale).headline


# ---- the recommended photo ----------------------------------------------------------------

def test_sharpness_decides():
    group = [scores(71), scores(53)]
    assert _said(group, 0) == "주제 선명도가 가장 높아요 — 71점, 다음 사진(B)은 53점"


def test_exposure_decides_after_a_similar_sharpness():
    group = [scores(70, 82), scores(68, 61)]
    assert _said(group, 0) == (
        "앞선 기준(주제 선명도)이 비슷해 주제 노출이 가장 적정해요 — 82점, 다음 사진(B)은 61점")


def test_composition_decides_and_reads_the_composition_points():
    group = [scores(tilt=0.0), scores(tilt=6.0)]
    best, worse = composition_score(0.0, 0), composition_score(6.0, 0)
    assert _said(group, 0) == (
        "앞선 기준(주제 선명도, 주제 노출)이 비슷해 구도 점수가 가장 높아요 — "
        f"{best:.0f}점, 다음 사진(B)은 {worse:.0f}점")


def test_colour_decides():
    group = [scores(color=60.0), scores(color=30.0)]
    assert _said(group, 0) == (
        "앞선 기준(주제 선명도, 주제 노출)이 비슷해 색감이 가장 풍부해요 — "
        "60점, 다음 사진(B)은 30점")


def test_runner_up_is_the_best_other_photo_still_in_the_race():
    group = [scores(90), scores(50), scores(70)]
    assert _said(group, 0) == "주제 선명도가 가장 높아요 — 90점, 다음 사진(C)은 70점"


def test_runner_up_skips_photos_that_dropped_out_earlier():
    group = [scores(70, 90), scores(68, 40), scores(30, 99)]       # C: best exposure, but blurry
    assert _said(group, 0) == (
        "앞선 기준(주제 선명도)이 비슷해 주제 노출이 가장 적정해요 — 90점, 다음 사진(B)은 40점")


def test_tie():
    group = [scores(), scores()]
    assert _said(group, 0) == (
        "모든 기준에서 차이가 작아요(차이 미미). 종합 점수가 가장 높은 사진이에요")


def test_single_photo():
    assert _said([scores()], 0) == "그룹에 이 사진 하나뿐이에요"


def test_gate_leaves_one_photo():
    group = [scores(70, 70), scores(70, 2)]
    assert _said(group, 0) == "나머지 사진은 주제가 너무 어둡거나 흐려서 이 사진을 추천해요"


# ---- the recommended photo of a person group -------------------------------------------------

def test_faces_decide_when_only_one_photo_has_one():
    assert _said([person(), scores()], 0) == "얼굴이 인식된 사진은 이것뿐이에요"


def test_closed_eyes_decide():
    group = [person(closed=0), person(closed=2)]
    assert _said(group, 0) == "눈 감은 사람이 가장 적어요 — 0명, 다음 사진(B)은 2명"


def test_smile_decides():
    group = [person(smile=0.8), person(smile=0.2)]
    assert _said(group, 0) == (
        "앞선 기준(눈 감음)이 비슷해 웃음이 가장 뚜렷해요 — 80%, 다음 사진(B)은 20%")


def test_face_sharpness_decides():
    group = [person(face_sharp=80), person(face_sharp=40)]
    assert _said(group, 0) == (
        "앞선 기준(눈 감음)이 비슷해 얼굴 선명도가 가장 높아요 — 80점, 다음 사진(B)은 40점")


def test_face_exposure_decides():
    group = [person(face_exposure=85), person(face_exposure=55)]
    assert _said(group, 0) == (
        "앞선 기준(눈 감음, 얼굴 선명도)이 비슷해 얼굴 노출이 가장 적정해요 — "
        "85점, 다음 사진(B)은 55점")


def test_person_gate_leaves_one_photo():
    group = [person(face_exposure=70, face_sharp=70), person(face_exposure=2)]
    assert _said(group, 0) == "나머지 사진은 얼굴이 너무 어둡거나 흐려서 이 사진을 추천해요"


# ---- the other photos --------------------------------------------------------------------

def test_dropped_out_on_sharpness():
    group = [scores(71), scores(53)]
    assert _said(group, 1) == "추천 사진(A)보다 주제 선명도가 낮아요 — 53점 vs 71점"


def test_dropped_out_on_exposure():
    group = [scores(70, 82), scores(68, 61)]
    assert _said(group, 1) == "추천 사진(A)보다 주제 노출 점수가 낮아요 — 61점 vs 82점"


def test_dropped_out_on_composition():
    group = [scores(tilt=0.0), scores(tilt=6.0)]
    best, worse = composition_score(0.0, 0), composition_score(6.0, 0)
    assert _said(group, 1) == f"추천 사진(A)보다 구도 점수가 낮아요 — {worse:.0f}점 vs {best:.0f}점"


def test_dropped_out_on_colour():
    group = [scores(color=60.0), scores(color=30.0)]
    assert _said(group, 1) == "추천 사진(A)보다 색감이 덜 풍부해요 — 30점 vs 60점"


def test_the_step_where_a_photo_dropped_out_is_named_not_the_deciding_one():
    group = [scores(70, 90), scores(68, 40), scores(30, 99)]
    assert _said(group, 2) == "추천 사진(A)보다 주제 선명도가 낮아요 — 30점 vs 70점"
    assert _said(group, 1) == "추천 사진(A)보다 주제 노출 점수가 낮아요 — 40점 vs 90점"


def test_loses_the_tiebreak():
    group = [scores(), scores()]                       # equal photos: the first one is recommended
    assert _said(group, 1) == "차이는 작지만 종합 점수가 추천 사진(A)보다 낮아요"


def test_removed_by_the_gate():
    group = [scores(70, 70), scores(70, 2)]
    assert _said(group, 1) == "주제가 너무 어둡거나 디테일이 없어 후보에서 제외됐어요"


def test_dropped_out_on_closed_eyes():
    group = [person(closed=0), person(closed=2)]
    assert _said(group, 1) == "눈 감은 사람이 2명이라 추천 사진(A, 0명)보다 밀려요"


def test_dropped_out_on_smile():
    group = [person(smile=0.8), person(smile=0.2)]
    assert _said(group, 1) == "추천 사진(A)보다 웃음이 약해요 — 20% vs 80%"


def test_dropped_out_on_face_sharpness():
    group = [person(face_sharp=80), person(face_sharp=40)]
    assert _said(group, 1) == "추천 사진(A)보다 얼굴 선명도가 낮아요 — 40점 vs 80점"


def test_dropped_out_on_face_exposure():
    group = [person(face_exposure=85), person(face_exposure=55)]
    assert _said(group, 1) == "추천 사진(A)보다 얼굴 노출 점수가 낮아요 — 55점 vs 85점"


def test_faceless_photo_of_a_person_group():
    assert _said([person(), scores()], 1) == "얼굴이 인식되지 않아 얼굴이 인식된 사진보다 밀려요"


def test_person_gate_removed_photo():
    group = [person(face_exposure=70, face_sharp=70), person(face_exposure=2)]
    assert _said(group, 1) == "얼굴이 너무 어둡거나 디테일이 없어 후보에서 제외됐어요"


# ---- the tooltip: one line per visible step ---------------------------------------------------

def test_trace_lines_show_how_many_photos_each_step_kept():
    group = [scores(70, 90), scores(68, 40), scores(30, 99)]
    assert _explain(group, 0).trace_lines == (
        "1. 주제 선명도: 3장 중 2장 남음 (허용폭 10%)",
        "2. 주제 노출: 2장 중 1장 남음 (허용폭 10점)",
    )


def test_trace_lines_follow_the_sensitivity():
    group = [scores(70, 90), scores(68, 40), scores(30, 99)]
    assert _explain(group, 0, scale=1.5).trace_lines == (
        "1. 주제 선명도: 3장 중 2장 남음 (허용폭 15%)",
        "2. 주제 노출: 2장 중 1장 남음 (허용폭 15점)",
    )


def test_trace_is_the_same_for_every_photo_of_the_group():
    group = [scores(70, 90), scores(68, 40)]
    assert _explain(group, 0).trace_lines == _explain(group, 1).trace_lines


def test_tie_trace_ends_with_the_tiebreak_line_and_hides_a_composition_nobody_loses_points_on():
    lines = _explain([scores(), scores()], 0).trace_lines
    assert lines == (
        "1. 주제 선명도: 2장 중 2장 남음 (허용폭 10%)",
        "2. 주제 노출: 2장 중 2장 남음 (허용폭 10점)",
        "3. 색감: 2장 중 2장 남음 (허용폭 10점)",
        "모든 기준이 동점이라 종합 점수로 정했어요",
    )


def test_composition_step_is_shown_once_somebody_loses_points():
    lines = _explain([scores(tilt=0.0), scores(tilt=6.0)], 0).trace_lines
    assert [line.split(":")[0] for line in lines] == ["1. 주제 선명도", "2. 주제 노출", "3. 구도"]


def test_gate_line_names_the_removed_photos():
    lines = _explain([scores(70, 70), scores(70, 2)], 0).trace_lines
    assert lines == ("실패 사진 제외: 주제가 너무 어둡거나 흐린 사진 1장",)
    person_lines = _explain([person(face_sharp=70), person(face_exposure=2)], 0).trace_lines
    assert person_lines[0] == "실패 사진 제외: 얼굴이 너무 어둡거나 흐린 사진 1장"


def test_person_trace_hides_face_detection_when_everybody_has_a_face():
    lines = _explain([person(closed=0), person(closed=2)], 0).trace_lines
    assert lines == ("1. 눈 감음: 2장 중 1장 남음 (같은 값만)",)


def test_single_photo_has_no_trace():
    assert _explain([scores()], 0).trace_lines == ()


# ---- facts about the photo ------------------------------------------------------------------

def test_facts_of_a_clean_photo_are_empty():
    assert _explain([scores(80), scores(79)], 0).facts == ()


def test_facts_name_closed_eyes_and_tilt():
    group = [person(closed=1, tilt=4.0), person(closed=0)]
    assert _explain(group, 0).facts == ("눈 감음 1명", "기울어짐")


def test_facts_name_a_blurry_photo():
    group = [scores(80), scores(40)]
    assert _explain(group, 1).facts == ("흐림",)
    assert _explain(group, 0).facts == ()


def test_facts_name_a_faceless_photo_in_a_person_group():
    assert _explain([person(), scores()], 1).facts == ("얼굴 없음",)


def test_facts_name_cut_faces():
    group = [person(cut=1), person()]
    assert _explain(group, 0).facts == ("얼굴 잘림 1명",)


def test_tilt_is_not_a_fact_of_a_single_photo():
    assert _explain([scores(tilt=9.0)], 0).facts == ()


@pytest.mark.parametrize("index", [0, 1])
def test_explanation_never_fails_on_a_two_photo_group(index):
    assert _explain([scores(55, 55, 55), scores(54, 56, 54)], index).headline
