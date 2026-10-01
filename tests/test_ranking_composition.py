"""Recommendation v2, stage 3 — the composition criterion in both chains (plan §2, §6-1).

``ranking.COMPOSITION_DEADBAND`` (absolute points of ``composition_score``) and the criterion
name ``"composition"``. The criterion reads ``QualityScores.tilt`` and ``FaceSummary.cut``:

    subject chain: subject_sharpness -> subject_exposure -> composition -> color -> tie
    person chain:  face_detected -> closed_eyes -> smile -> face_sharpness -> face_exposure
                   -> composition -> tie

``reason_label`` names it "구도 우세". ``criterion_rows`` shows a "구도" row only when someone
in the group has something to criticise (a group of level, uncut photos keeps the three / four
rows of the earlier stages), placed in chain order (before "색감" / after "얼굴 노출"). Its value
is the composition score, its bar the share of the group best like the other higher-is-better rows.
"""
import pytest

from tests.synthetic import person, scores


def _rec(group, scale=1.0):
    from myphotoworks.core.ranking import recommend

    return recommend(group, deadband_scale=scale)


def _tilt_costing(points: float) -> float:
    """A tilt whose composition score is ``points`` below 100 (bisection: the score is
    monotonic in the tilt, so the tests do not depend on the formula)."""
    from myphotoworks.core.composition import composition_score

    lo, hi = 0.0, 45.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if 100.0 - composition_score(mid) < points:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def _deadband() -> float:
    from myphotoworks.core.ranking import COMPOSITION_DEADBAND

    return COMPOSITION_DEADBAND


# ---- subject chain --------------------------------------------------------------------------


def test_composition_decides_when_sharpness_and_exposure_tie():
    level, tilted = scores(80, 70, 60, tilt=0.0), scores(80, 70, 60, tilt=_tilt_costing(40))
    rec = _rec([tilted, level])
    assert (rec.index, rec.deciding_criterion, rec.tie) == (1, "composition", False)


def test_sharpness_and_exposure_have_priority_over_composition():
    level = scores(60, 70, 60, tilt=0.0)
    tilted_but_sharper = scores(95, 70, 60, tilt=_tilt_costing(40))
    assert _rec([level, tilted_but_sharper]).deciding_criterion == "subject_sharpness"
    tilted_but_better_exposed = scores(80, 90, 60, tilt=_tilt_costing(40))
    rec = _rec([scores(80, 60, 60, tilt=0.0), tilted_but_better_exposed])
    assert (rec.index, rec.deciding_criterion) == (1, "subject_exposure")


def test_composition_is_checked_before_colour():
    tilted_colourful = scores(80, 70, 90, tilt=_tilt_costing(40))
    level_dull = scores(80, 70, 20, tilt=0.0)
    rec = _rec([tilted_colourful, level_dull])
    assert (rec.index, rec.deciding_criterion) == (1, "composition")


def test_a_composition_gap_inside_the_deadband_passes_on_to_colour():
    small = scores(80, 70, 20, tilt=_tilt_costing(0.4 * _deadband()))
    level_colourful = scores(80, 70, 90, tilt=0.0)
    rec = _rec([level_colourful, small])
    assert (rec.index, rec.deciding_criterion) == (0, "color")


def test_the_composition_deadband_is_scaled_by_the_sensitivity():
    d = _deadband()
    level = scores(80, 70, 60, tilt=0.0)
    near = scores(80, 70, 60, tilt=_tilt_costing(0.8 * d))       # 0.8 deadbands behind
    far = scores(80, 70, 60, tilt=_tilt_costing(1.4 * d))        # 1.4 deadbands behind
    assert _rec([level, near], 1.0).tie is True
    assert _rec([level, near], 0.5).deciding_criterion == "composition"
    assert _rec([level, far], 1.0).deciding_criterion == "composition"
    assert _rec([level, far], 1.5).tie is True


def test_an_unknown_tilt_is_not_a_penalty():
    level, unknown = scores(tilt=0.0), scores(tilt=None)
    assert _rec([level, unknown]).tie is True
    rec = _rec([scores(tilt=_tilt_costing(40)), unknown])
    assert (rec.index, rec.deciding_criterion) == (1, "composition")


def test_the_sign_of_the_tilt_does_not_matter():
    a, b = scores(tilt=6.0), scores(tilt=-6.0)
    assert _rec([a, b]).tie is True


# ---- person chain ---------------------------------------------------------------------------


def test_a_cut_face_loses_when_everything_before_composition_ties():
    cut, whole = person(cut=1), person(cut=0)
    rec = _rec([cut, whole])
    assert (rec.index, rec.deciding_criterion, rec.tie) == (1, "composition", False)


def test_tilt_counts_in_a_person_group():
    rec = _rec([person(tilt=_tilt_costing(40)), person(tilt=0.0)])
    assert (rec.index, rec.deciding_criterion) == (1, "composition")


def test_face_exposure_has_priority_over_composition():
    cut_but_better_exposed = person(face_exposure=90, cut=1)
    whole_but_dark = person(face_exposure=50, cut=0)
    rec = _rec([whole_but_dark, cut_but_better_exposed])
    assert (rec.index, rec.deciding_criterion) == (1, "face_exposure")


def test_eyes_and_smile_and_sharpness_come_before_composition_too():
    rec = _rec([person(closed=1, cut=0), person(closed=0, n=2, cut=2)])
    assert rec.deciding_criterion == "closed_eyes" and rec.index == 1
    rec = _rec([person(face_sharp=95, n=2, cut=2), person(face_sharp=50, cut=0)])
    assert rec.deciding_criterion == "face_sharpness" and rec.index == 0


def test_a_person_group_without_penalties_decides_as_before():
    """Regression guard (passes today): composition ties when nobody is tilted or cut."""
    rec = _rec([person(face_sharp=90, face_exposure=40), person(face_sharp=50, face_exposure=90)])
    assert (rec.index, rec.deciding_criterion) == (0, "face_sharpness")


def test_a_cut_face_and_a_clearly_tilted_horizon_are_each_worth_more_than_the_deadband():
    """Otherwise the criterion could never decide anything (tuning guard for the constants)."""
    from myphotoworks.core.composition import composition_score

    assert 100.0 - composition_score(None, 1) > _deadband()
    assert 100.0 - composition_score(10.0) > _deadband()


# ---- badge text -----------------------------------------------------------------------------


def test_reason_label_names_composition():
    from myphotoworks.core.ranking import Recommendation, reason_label

    assert reason_label(Recommendation(1, "composition", False), 3) == "구도 우세"


# ---- detail-panel rows ----------------------------------------------------------------------


def _rows(group, index, scale=1.0):
    from myphotoworks.core.ranking import criterion_rows

    return criterion_rows(group, index, _rec(group, scale), deadband_scale=scale)


def test_a_group_without_penalties_keeps_the_rows_of_the_earlier_stages():
    """Regression guard (passes today)."""
    assert [r.name for r in _rows([scores(80), scores(60)], 0)] == [
        "subject_sharpness", "subject_exposure", "color"]
    assert [r.name for r in _rows([person(), person(face_sharp=50)], 0)] == [
        "closed_eyes", "smile", "face_sharpness", "face_exposure"]


def test_a_tilted_photo_adds_a_composition_row_before_colour():
    rows = _rows([scores(80, 70, 60, tilt=0.0), scores(80, 70, 60, tilt=_tilt_costing(40))], 0)
    assert [r.name for r in rows] == [
        "subject_sharpness", "subject_exposure", "composition", "color"]
    assert "구도" in rows[2].label


def test_a_penalised_person_group_adds_a_composition_row_last():
    rows = _rows([person(cut=1), person(cut=0)], 0)
    assert [r.name for r in rows] == [
        "closed_eyes", "smile", "face_sharpness", "face_exposure", "composition"]


def test_the_composition_row_shows_the_score_and_the_share_of_the_best():
    from myphotoworks.core.composition import composition_score

    tilt = _tilt_costing(40)
    group = [scores(80, 70, 60, tilt=0.0), scores(80, 70, 60, tilt=tilt)]
    level_row, tilted_row = _rows(group, 0)[2], _rows(group, 1)[2]
    assert level_row.value == pytest.approx(100.0) and level_row.relative == pytest.approx(1.0)
    assert tilted_row.value == pytest.approx(composition_score(tilt))
    assert tilted_row.relative == pytest.approx(composition_score(tilt) / 100.0)


def test_the_composition_row_is_the_deciding_one_and_tied_rows_read_as_tied():
    group = [scores(80.0, 70.0, 60.0, tilt=0.0), scores(80.0, 70.0, 60.0, tilt=_tilt_costing(40))]
    rows = _rows(group, 0)
    assert [r.deciding for r in rows] == [False, False, True, False]
    assert [r.tied for r in rows] == [True, True, False, True]


def test_a_cut_face_counts_in_the_composition_row():
    group = [person(cut=1), person(cut=0)]
    cut_row, whole_row = _rows(group, 0)[4], _rows(group, 1)[4]
    assert cut_row.relative < whole_row.relative == pytest.approx(1.0)
