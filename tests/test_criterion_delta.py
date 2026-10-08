"""Explainability, item 5 — the score panel's bars compare a photo with the *recommended* photo.

``CriterionRow`` gets two fields: ``delta`` (-1..1, positive = better than the recommended photo)
and ``verdict`` ("better" / "worse" / "same" within the criterion's deadband / "none" when there
is nothing to compare, e.g. a photo without a face in a person group). The bar of a photo is
drawn from the centre: right = better, left = worse. The recommended photo is the centre line.

``delta`` is the difference in the criterion's own unit divided by a full-scale span: sharpness
(subject and face) 50 % of the recommended photo's value, exposure / colour / composition 40
points, smile 50 percentage points, closed eyes 2 people.
"""
import pytest

from tests.synthetic import person, scores


def _rows(group, index, scale=1.0):
    from myphotoworks.core.ranking import criterion_rows, recommend

    return criterion_rows(group, index, recommend(group, scale), scale)


def _by_name(rows):
    return {row.name: row for row in rows}


def test_new_fields_default_to_a_neutral_row():
    from myphotoworks.core.ranking import CriterionRow

    row = CriterionRow("subject_sharpness", "주제 선명도", 70.0, 1.0, False, False)
    assert row.delta == 0.0 and row.verdict == "same"


def test_the_recommended_photo_is_the_centre_line():
    group = [scores(80, 40, 60), scores(40, 80, 30)]
    for row in _rows(group, 0):
        assert row.delta == 0.0 and row.verdict == "same"


def test_another_photo_is_compared_with_the_recommended_one():
    group = [scores(80, 40, 60), scores(40, 80, 30)]        # photo 0 is recommended (sharpness)
    rows = _by_name(_rows(group, 1))
    sharp, exposure, color = (rows[n] for n in ("subject_sharpness", "subject_exposure", "color"))
    assert (sharp.delta, sharp.verdict) == (pytest.approx(-1.0), "worse")      # -50 %: full span
    assert (exposure.delta, exposure.verdict) == (pytest.approx(1.0), "better")   # +40 points
    assert (color.delta, color.verdict) == (pytest.approx(-0.75), "worse")        # -30 of 40


def test_a_difference_inside_the_deadband_is_the_same_but_still_drawn_a_little():
    group = [scores(80, 70, 60), scores(76, 70, 60)]        # a tie: the first wins the tiebreak
    row = _by_name(_rows(group, 1))["subject_sharpness"]
    assert row.verdict == "same"
    assert row.delta == pytest.approx(-0.1)                 # -5 % of 80, span 50 %


def test_the_sensitivity_moves_the_line_between_same_and_worse():
    group = [scores(80), scores(70)]
    assert _by_name(_rows(group, 1, scale=1.0))["subject_sharpness"].verdict == "worse"
    assert _by_name(_rows(group, 1, scale=1.5))["subject_sharpness"].verdict == "same"


def test_delta_is_clipped_to_the_bar():
    group = [scores(90, 90, 90), scores(10, 0, 0)]
    for row in _rows(group, 1):
        assert -1.0 <= row.delta <= 1.0
    assert _by_name(_rows(group, 1))["subject_exposure"].delta == -1.0


def test_fewer_closed_eyes_is_better():
    group = [person(closed=0), person(closed=1), person(closed=2)]
    one = _by_name(_rows(group, 1))["closed_eyes"]
    two = _by_name(_rows(group, 2))["closed_eyes"]
    assert (one.delta, one.verdict) == (pytest.approx(-0.5), "worse")      # one more: 1 of 2
    assert (two.delta, two.verdict) == (pytest.approx(-1.0), "worse")


def test_person_rows_use_their_own_spans():
    group = [person(smile=0.8, face_sharp=80, face_exposure=40),
             person(smile=0.4, face_sharp=40, face_exposure=80)]
    rows = _by_name(_rows(group, 1))
    assert rows["closed_eyes"].delta == 0.0 and rows["closed_eyes"].verdict == "same"
    assert rows["smile"].delta == pytest.approx(-0.8)                       # -0.4 of 0.5
    assert rows["face_sharpness"].delta == pytest.approx(-1.0)
    assert (rows["face_exposure"].delta, rows["face_exposure"].verdict) == (
        pytest.approx(1.0), "better")


def test_a_photo_without_a_face_has_nothing_to_compare():
    group = [person(), scores(90, 90, 90)]
    for row in _rows(group, 1):
        assert row.delta == 0.0 and row.verdict == "none"


def test_composition_row_follows_the_same_rule():
    group = [scores(tilt=0.0), scores(tilt=6.0)]
    row = _by_name(_rows(group, 1))["composition"]
    assert row.verdict == "worse" and row.delta == pytest.approx(-30 / 40)
