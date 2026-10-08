"""Explainability, item 4 — "추천 방식": the chain of criteria, written from the real constants.

``explain.chain_overview(person, deadband_scale) -> Overview(title, steps, notes)`` is what the
review window's [추천 방식] dialog shows: the order the criteria are compared in with the
deadband of each (scaled by the sensitivity), and the rules around it (tie, failure gate, ...).
It is built from the same ``Criterion`` objects and constants ``recommend`` uses, so it cannot
drift from the algorithm.
"""
from myphotoworks.core.ranking import (
    COLOR_IGNORE_BELOW,
    EXPOSURE_FAIL,
    SHARPNESS_FAIL,
    SMILE_PRESENT_TH,
)


def _overview(person=False, scale=1.0):
    from myphotoworks.core.explain import chain_overview

    return chain_overview(person, scale)


def test_general_group_overview():
    ov = _overview(person=False)
    assert ov.title == "일반 그룹의 추천 순서"
    assert ov.steps == (
        "1. 주제 선명도 — 허용폭 10%",
        "2. 주제 노출 — 허용폭 10점",
        "3. 구도 — 허용폭 10점",
        "4. 색감 — 허용폭 10점",
    )


def test_person_group_overview():
    ov = _overview(person=True)
    assert ov.title == "인물 그룹의 추천 순서"
    assert ov.steps == (
        "1. 얼굴 인식 — 얼굴이 인식된 사진 우선",
        "2. 눈 감음 — 같은 값만 (적을수록 좋아요)",
        "3. 웃음 — 허용폭 15%",
        "4. 얼굴 선명도 — 허용폭 10%",
        "5. 얼굴 노출 — 허용폭 10점",
        "6. 구도 — 허용폭 10점",
    )


def test_deadbands_follow_the_sensitivity():
    low = _overview(person=False, scale=1.5).steps
    assert low[0] == "1. 주제 선명도 — 허용폭 15%" and low[1] == "2. 주제 노출 — 허용폭 15점"
    high = _overview(person=False, scale=0.6).steps
    assert high[0] == "1. 주제 선명도 — 허용폭 6%" and high[1] == "2. 주제 노출 — 허용폭 6점"
    assert _overview(person=True, scale=1.5).steps[2] == "3. 웃음 — 허용폭 22.5%"


def test_general_notes_are_written_from_the_constants():
    notes = _overview(person=False).notes
    assert notes == (
        "앞 기준에서 1등과의 차이가 허용폭 안이면 동점으로 보고 다음 기준으로 넘어가요. "
        "한 사진만 남는 기준이 그 사진을 추천한 이유예요.",
        "끝까지 동점이면 '차이 미미'로 보고, 선명도·노출·색감을 섞은 종합 점수가 가장 높은 "
        "사진을 추천해요.",
        f"주제가 너무 어둡거나 날아가거나(노출 {EXPOSURE_FAIL:g}점 미만) 디테일이 거의 없는"
        f"(선명도 {SHARPNESS_FAIL:g}점 미만) 사진은, 성한 사진이 있으면 후보에서 빼요.",
        f"색감이 {COLOR_IGNORE_BELOW:g}점 미만인 흑백에 가까운 그룹에서는 색감 기준을 건너뛰어요.",
        "허용폭은 '추천 민감도'로 조절해요. 지금은 보통이에요 (낮음은 넓게, 높음은 좁게).",
        "점수를 잰 영역은 '측정 영역 보기'로 사진 위에서 확인할 수 있어요.",
    )


def test_person_notes_talk_about_faces_and_smiles():
    notes = _overview(person=True).notes
    assert any("얼굴 선명도·얼굴 노출·웃음을 섞은 종합 점수" in n for n in notes)
    assert any(n.startswith("얼굴이 너무 어둡거나 날아가거나") for n in notes)
    assert any(f"웃음 {SMILE_PRESENT_TH * 100:g}% 이상인 사람이 있을 때만" in n for n in notes)
    assert not any("흑백" in n for n in notes)


def test_sensitivity_name_is_in_the_notes():
    assert any("지금은 낮음이에요" in n for n in _overview(scale=1.5).notes)
    assert any("지금은 높음이에요" in n for n in _overview(scale=0.6).notes)
    assert any("지금은 보통이에요" in n for n in _overview(scale=1.0).notes)


def test_overview_is_the_chain_the_algorithm_really_runs():
    """Same criteria and order as ``recommend`` (monochrome / smile aside, which the notes say)."""
    from myphotoworks.core.ranking import _chain, _person_chain
    from tests.synthetic import person, scores

    general = [c.name for c in _chain([scores(), scores()])]
    general_labels = [s.split(" — ")[0].split(". ", 1)[1] for s in _overview(False).steps]
    assert len(general) == len(general_labels)
    persons = [c.name for c in _person_chain([person(smile=0.9), person(smile=0.9)])]
    person_labels = [s.split(" — ")[0].split(". ", 1)[1] for s in _overview(True).steps]
    assert len(persons) == len(person_labels)
    from myphotoworks.core.ranking import _LABELS

    assert general_labels == [_LABELS[n] for n in general]
    assert person_labels == [_LABELS[n] for n in persons]
