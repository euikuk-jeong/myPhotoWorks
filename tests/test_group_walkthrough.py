"""Explainability, item 6 — "이 그룹에서는": how the chain went through the selected group.

``explain.group_walkthrough(group, names, deadband_scale) -> tuple[str, ...]`` — the lines the
[추천 방식] dialog shows under the chain: one line per visible step with the photos that stayed in
the race, then the result. It reads the same ``chain_trace`` as the sentence and the tooltip.
Empty for a single photo.
"""
from tests.synthetic import person, scores

NAMES = ["A", "B", "C", "D", "E", "F"]


def _walk(group, scale=1.0):
    from myphotoworks.core.explain import group_walkthrough

    return group_walkthrough(group, NAMES[: len(group)], scale)


def test_one_step_decides():
    assert _walk([scores(71), scores(53)]) == (
        "1. 주제 선명도: 2장 중 1장 남음 (허용폭 10%) — A",
        "→ 추천: A",
    )


def test_two_steps_name_the_photos_that_stayed():
    group = [scores(70, 90), scores(68, 40), scores(30, 99)]
    assert _walk(group) == (
        "1. 주제 선명도: 3장 중 2장 남음 (허용폭 10%) — A, B",
        "2. 주제 노출: 2장 중 1장 남음 (허용폭 10점) — A",
        "→ 추천: A",
    )


def test_a_tie_ends_with_the_total_score():
    assert _walk([scores(), scores()]) == (
        "1. 주제 선명도: 2장 중 2장 남음 (허용폭 10%) — A, B",
        "2. 주제 노출: 2장 중 2장 남음 (허용폭 10점) — A, B",
        "3. 색감: 2장 중 2장 남음 (허용폭 10점) — A, B",
        "→ 추천: A (종합 점수)",
    )


def test_many_photos_are_cut_after_four_names():
    lines = _walk([scores()] * 6)
    assert lines[0] == "1. 주제 선명도: 6장 중 6장 남음 (허용폭 10%) — A, B, C, D 외 2장"


def test_the_failure_gate_names_the_photos_it_removed():
    assert _walk([scores(70, 70), scores(70, 2)]) == (
        "실패 사진 제외: 주제가 너무 어둡거나 흐린 사진 1장 — B",
        "→ 추천: A (나머지는 후보에서 제외)",
    )


def test_person_group_walkthrough():
    assert _walk([person(closed=0), person(closed=2)]) == (
        "1. 눈 감음: 2장 중 1장 남음 (같은 값만) — A",
        "→ 추천: A",
    )


def test_the_walkthrough_follows_the_sensitivity():
    lines = _walk([scores(70, 90), scores(68, 40)], scale=1.5)
    assert lines[0] == "1. 주제 선명도: 2장 중 2장 남음 (허용폭 15%) — A, B"


def test_a_single_photo_has_no_walkthrough():
    assert _walk([scores()]) == ()
