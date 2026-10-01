"""Recommendation v2, stage 1 — priority chain with deadband (plan §4-5).

New ``core/ranking.py`` API under test:

    Criterion(name, key, deadband, relative=False, higher_is_better=True)
    Recommendation(index, deciding_criterion, tie)          frozen value
    select_best(items, criteria, tiebreak, deadband_scale=1.0) -> Recommendation   generic engine
    recommend(group: list[QualityScores], deadband_scale=1.0)  -> Recommendation   stage-1 chain
    reason_label(rec, group_size) -> str                                           badge text
    criterion_rows(group, index, rec, deadband_scale=1.0) -> list[CriterionRow]    detail panel data
    CriterionRow(name, label, value, relative, deciding, tied)

``deadband_scale`` multiplies every deadband (plan: low sensitivity 1.5, normal 1.0, high 0.6).
Constants are imported by name (``SHARPNESS_DEADBAND`` is a relative fraction, plan §7);
their values are tuned later, so the tests only rely on orderings.
"""
import pytest

from tests.synthetic import scores


def _select(items, criteria, tiebreak=lambda x: 0.0, scale=1.0):
    from myphotoworks.core.ranking import select_best

    return select_best(items, criteria, tiebreak, deadband_scale=scale)


def _crit(name, idx, deadband, **kw):
    from myphotoworks.core.ranking import Criterion

    return Criterion(name, lambda item, i=idx: item[i], deadband, **kw)


# ---- generic engine -------------------------------------------------------------------


def test_clear_winner_on_first_criterion_decides_it():
    rec = _select([(100, 0), (60, 99)], [_crit("a", 0, 10), _crit("b", 1, 5)])
    assert (rec.index, rec.deciding_criterion, rec.tie) == (0, "a", False)


def test_difference_inside_deadband_passes_to_the_next_criterion():
    rec = _select([(100, 10), (95, 50)], [_crit("a", 0, 10), _crit("b", 1, 5)])
    assert (rec.index, rec.deciding_criterion, rec.tie) == (1, "b", False)


def test_chain_stops_at_the_first_decisive_criterion():
    rec = _select([(100, 0), (50, 99)], [_crit("a", 0, 10), _crit("b", 1, 5)])
    assert rec.index == 0 and rec.deciding_criterion == "a"


def test_only_candidates_within_the_deadband_of_the_best_survive():
    items = [(100, 10), (95, 20), (60, 99)]       # third is best on b but out of the running
    rec = _select(items, [_crit("a", 0, 10), _crit("b", 1, 5)])
    assert rec.index == 1 and rec.deciding_criterion == "b"


def test_survivors_can_be_more_than_two_and_the_chain_keeps_narrowing():
    items = [(100, 50, 1), (98, 49, 9), (97, 10, 99)]
    rec = _select(items, [_crit("a", 0, 5), _crit("b", 1, 5), _crit("c", 2, 5)])
    # the third item drops out at "b"; between the first two "c" is the only difference
    assert rec.index == 1 and rec.deciding_criterion == "c"


def test_everything_inside_deadbands_is_a_tie_decided_by_the_tiebreak():
    items = [(100, 10, 1.0), (99, 11, 3.0)]
    rec = _select(items, [_crit("a", 0, 10), _crit("b", 1, 5)], tiebreak=lambda x: x[2])
    assert (rec.index, rec.deciding_criterion, rec.tie) == (1, None, True)


def test_tie_with_equal_tiebreak_prefers_the_first_item():
    items = [(100, 10), (100, 10), (100, 10)]
    rec = _select(items, [_crit("a", 0, 10)])
    assert (rec.index, rec.tie) == (0, True)


def test_relative_deadband_is_a_share_of_the_best_value():
    crit = [_crit("a", 0, 0.10, relative=True), _crit("b", 1, 1)]
    assert _select([(100, 0), (91, 9)], crit).deciding_criterion == "b"     # 9 % apart: tie on a
    assert _select([(100, 0), (85, 9)], crit).deciding_criterion == "a"     # 15 % apart: decided


def test_lower_is_better_criterion_with_zero_deadband_is_an_exact_integer_compare():
    crit = [_crit("closed_eyes", 0, 0, higher_is_better=False)]
    rec = _select([(2,), (0,), (1,)], crit)
    assert (rec.index, rec.deciding_criterion, rec.tie) == (1, "closed_eyes", False)
    assert _select([(1,), (1,)], crit).tie is True


def test_deadband_scale_multiplies_absolute_deadbands():
    items = [(100, 0), (92, 9)]                   # 8 apart on "a"
    crit = [_crit("a", 0, 10), _crit("b", 1, 1)]
    assert _select(items, crit, scale=1.0).deciding_criterion == "b"        # inside 10
    assert _select(items, crit, scale=0.6).deciding_criterion == "a"        # 8 > 6: decided
    assert _select(items, crit, scale=1.5).deciding_criterion == "b"        # inside 15


def test_deadband_scale_multiplies_relative_deadbands_too():
    items = [(100, 0), (92, 9)]
    crit = [_crit("a", 0, 0.10, relative=True), _crit("b", 1, 1)]
    assert _select(items, crit, scale=1.0).deciding_criterion == "b"
    assert _select(items, crit, scale=0.5).deciding_criterion == "a"


def test_single_item_is_returned_without_a_deciding_criterion():
    rec = _select([(5, 5)], [_crit("a", 0, 10)])
    assert (rec.index, rec.deciding_criterion, rec.tie) == (0, None, False)


def test_recommendation_is_an_immutable_value():
    from dataclasses import FrozenInstanceError

    from myphotoworks.core.ranking import Recommendation

    rec = Recommendation(index=1, deciding_criterion="a", tie=False)
    with pytest.raises(FrozenInstanceError):
        rec.index = 2


# ---- stage-1 chain on QualityScores ---------------------------------------------------------


def _rec(group, scale=1.0):
    from myphotoworks.core.ranking import recommend

    return recommend(group, deadband_scale=scale)


def test_single_photo_group():
    from myphotoworks.core.ranking import reason_label

    rec = _rec([scores()])
    assert (rec.index, rec.tie) == (0, False)
    assert reason_label(rec, 1) == "단독 사진"


def test_subject_sharpness_has_priority_over_exposure_and_colour():
    a = scores(90, 45, 10)
    b = scores(60, 90, 90)
    rec = _rec([b, a])
    assert (rec.index, rec.deciding_criterion) == (1, "subject_sharpness")


def test_exposure_decides_when_sharpness_is_within_the_deadband():
    a = scores(80.0, 40, 60)
    b = scores(79.5, 85, 60)
    rec = _rec([a, b])
    assert (rec.index, rec.deciding_criterion, rec.tie) == (1, "subject_exposure", False)


def test_colour_decides_when_sharpness_and_exposure_are_equal():
    a = scores(80, 70, 10)
    b = scores(80, 70, 90)
    rec = _rec([a, b])
    assert (rec.index, rec.deciding_criterion) == (1, "color")


def test_noise_level_differences_in_a_pair_are_reported_as_a_tie():
    """Plan §4 completion criterion: a 2-photo group that differs only by noise."""
    from myphotoworks.core.ranking import reason_label

    a = scores(80.0, 70.0, 60.0)
    b = scores(80.4, 70.3, 60.2)
    rec = _rec([a, b])
    assert rec.tie is True and rec.deciding_criterion is None
    assert rec.index == 1                      # weighted tiebreak still picks the larger sum
    assert reason_label(rec, 2) == "차이 미미"


def test_identical_scores_pick_the_first_photo():
    s = scores(50, 50, 50)
    rec = _rec([s, s, s])
    assert (rec.index, rec.tie) == (0, True)


def test_sharpness_deadband_is_relative_and_scaled_by_sensitivity():
    from myphotoworks.core import ranking

    d = ranking.SHARPNESS_DEADBAND
    best = scores(100.0, 70, 60)
    near = scores(100.0 * (1 - 0.8 * d), 70, 60)        # 0.8 deadbands behind
    far = scores(100.0 * (1 - 1.4 * d), 70, 60)         # 1.4 deadbands behind
    assert _rec([best, near], 1.0).tie is True
    assert _rec([best, near], 0.5).deciding_criterion == "subject_sharpness"
    assert _rec([best, far], 1.0).deciding_criterion == "subject_sharpness"
    assert _rec([best, far], 1.5).tie is True


def test_failed_subject_exposure_is_gated_even_if_it_is_the_sharpest():
    """Obvious failure (subject all black / blown) never beats a usable photo."""
    sharp_but_black = scores(95, 0, 60)
    usable = scores(55, 80, 60)
    rec = _rec([sharp_but_black, usable])
    assert rec.index == 1


def test_gate_is_ignored_when_every_photo_fails_it():
    rec = _rec([scores(95, 0, 60), scores(55, 0, 60)])
    assert (rec.index, rec.deciding_criterion) == (0, "subject_sharpness")


def test_colour_is_ignored_for_a_black_and_white_group():
    from myphotoworks.core.ranking import COLOR_IGNORE_BELOW

    a = scores(80, 70, 0.0)
    b = scores(80, 70, COLOR_IGNORE_BELOW * 0.9)
    rec = _rec([a, b])
    assert rec.tie is True and rec.deciding_criterion != "color"


def test_colour_counts_once_any_photo_in_the_group_has_real_colour():
    from myphotoworks.core.ranking import COLOR_IGNORE_BELOW

    a = scores(80, 70, 0.0)
    b = scores(80, 70, COLOR_IGNORE_BELOW + 60)
    assert _rec([a, b]).deciding_criterion == "color"


def test_recommend_returns_a_valid_index_for_larger_groups():
    group = [scores(20 + 15 * i, 90 - 3 * i, 50) for i in range(6)]
    rec = _rec(group)
    assert 0 <= rec.index < len(group)
    assert rec.index == 5                       # sharpest, and exposure still usable


# ---- badge text (plan §4-7) -------------------------------------------------------------


@pytest.mark.parametrize(
    ("criterion", "text"),
    [("subject_sharpness", "주제 선명도 우세"), ("subject_exposure", "주제 노출 우세")],
)
def test_reason_label_names_the_deciding_criterion(criterion, text):
    from myphotoworks.core.ranking import Recommendation, reason_label

    assert reason_label(Recommendation(1, criterion, False), 3) == text


def test_reason_label_for_colour_mentions_colour():
    from myphotoworks.core.ranking import Recommendation, reason_label

    assert "색감" in reason_label(Recommendation(0, "color", False), 2)


def test_reason_label_for_tie_and_single():
    from myphotoworks.core.ranking import Recommendation, reason_label

    assert reason_label(Recommendation(0, None, True), 4) == "차이 미미"
    assert reason_label(Recommendation(0, None, False), 1) == "단독 사진"


# ---- detail-panel data (plan §4-7 "표시 데이터 함수") -------------------------------------------


def _rows(group, index, scale=1.0):
    from myphotoworks.core.ranking import criterion_rows

    return criterion_rows(group, index, _rec(group, scale), deadband_scale=scale)


def test_rows_follow_chain_order_with_korean_labels():
    rows = _rows([scores(80, 70, 60), scores(40, 70, 60)], 0)
    assert [r.name for r in rows] == ["subject_sharpness", "subject_exposure", "color"]
    assert "주제 선명도" in rows[0].label
    assert "주제 노출" in rows[1].label
    assert "색감" in rows[2].label


def test_row_values_are_relative_to_the_group_best():
    group = [scores(80, 40, 60), scores(40, 80, 30)]
    first, second = _rows(group, 0), _rows(group, 1)
    assert first[0].relative == pytest.approx(1.0) and second[0].relative == pytest.approx(0.5)
    assert first[1].relative == pytest.approx(0.5) and second[1].relative == pytest.approx(1.0)
    assert first[0].value == 80 and second[2].value == 30


def test_deciding_row_is_flagged_exactly_once_and_tied_rows_are_marked():
    group = [scores(80.0, 40, 60), scores(79.5, 85, 60)]    # sharpness tied, exposure decides
    rows = _rows(group, 1)
    assert [r.deciding for r in rows] == [False, True, False]
    assert rows[0].tied is True                              # "≈" in the panel
    assert rows[1].tied is False


def test_all_tied_group_marks_every_row_tied_and_none_deciding():
    group = [scores(80.0, 70.0, 60.0), scores(80.4, 70.3, 60.2)]
    for index in (0, 1):
        rows = _rows(group, index)
        assert all(r.tied for r in rows)
        assert not any(r.deciding for r in rows)


def test_rows_survive_all_zero_scores():
    rows = _rows([scores(0, 0, 0), scores(0, 0, 0)], 0)
    assert all(0.0 <= r.relative <= 1.0 for r in rows)


def test_rows_judge_ties_among_the_photos_that_actually_competed():
    """A failed photo is out of the race, so it must not stop its rivals from reading as tied."""
    group = [scores(80, 40, 60), scores(78, 85, 60), scores(10, 70, 60)]   # third: no detail
    rec = _rec(group)
    assert (rec.index, rec.deciding_criterion) == (1, "subject_exposure")
    rows = _rows(group, 1)
    assert [r.tied for r in rows] == [True, False, True]
    assert [r.deciding for r in rows] == [False, True, False]
    assert rows[0].relative == pytest.approx(78 / 80)       # bars still use the whole group


def test_monochrome_is_judged_among_the_photos_that_competed():
    group = [scores(80, 70, 0.0), scores(80, 70, 0.0), scores(80, 0, 90)]  # colourful one failed
    rec = _rec(group)
    assert rec.deciding_criterion != "color"
    assert _rows(group, 0)[2].tied is True
