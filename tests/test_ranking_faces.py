"""Recommendation v2, stage 2 — person chain on ``QualityScores.faces`` (plan §2, §5-3, §5-4).

``QualityScores.faces`` is ``None`` (no main face) or a ``core.faces.FaceSummary``.

New / changed ``core/ranking.py`` API under test:

    SMILE_DEADBAND (absolute, 0..1), SMILE_PRESENT_TH      tunables (plan §7)
    is_person_group(group) -> bool                         any photo has a main face
    recommend(group, deadband_scale=1.0)                   person group -> person chain:
        face_detected -> closed_eyes (fewer is better, exact integer compare) -> smile
        (only when someone in the group smiles) -> face_sharpness (relative deadband) ->
        face_exposure -> tie ("차이 미미") decided by a weighted sum
    reason_label(rec, group_size)                          + the four face criteria
    criterion_rows(group, index, rec, deadband_scale)      person group -> four person rows

A group without any main face runs the stage-1 chain unchanged (regression guard).
"""
import pytest

from tests.synthetic import person, scores


def _rec(group, scale=1.0):
    from myphotoworks.core.ranking import recommend

    return recommend(group, deadband_scale=scale)


def _smile_gap():
    """(low, high) smile values far enough apart to decide, high >= SMILE_PRESENT_TH."""
    from myphotoworks.core.ranking import SMILE_DEADBAND, SMILE_PRESENT_TH

    return 0.0, min(1.0, SMILE_PRESENT_TH + 2 * SMILE_DEADBAND)


# ---- person group detection -----------------------------------------------------------------


def test_a_group_is_a_person_group_when_any_photo_has_a_main_face():
    from myphotoworks.core.ranking import is_person_group

    assert is_person_group([scores(), person()]) is True
    assert is_person_group([person(), person()]) is True
    assert is_person_group([scores(), scores()]) is False


def test_a_group_without_faces_runs_the_stage_one_chain_unchanged():
    """Regression guard: faces are optional; nothing changes for landscapes (passes today)."""
    group = [scores(90, 45, 10), scores(60, 90, 90)]
    rec = _rec(group)
    assert (rec.index, rec.deciding_criterion, rec.tie) == (0, "subject_sharpness", False)


# ---- chain order ----------------------------------------------------------------------------


def test_a_photo_with_a_face_beats_a_faceless_photo_even_if_that_one_is_sharper():
    rec = _rec([scores(95, 90, 80), person(face_sharp=40)])
    assert (rec.index, rec.deciding_criterion, rec.tie) == (1, "face_detected", False)


def test_faceless_photos_drop_out_before_the_other_face_criteria():
    group = [scores(95, 90, 80), person(closed=2), person(closed=1), scores(99, 99, 99)]
    rec = _rec(group)
    assert (rec.index, rec.deciding_criterion) == (2, "closed_eyes")


def test_fewer_closed_eyes_beats_a_sharper_and_smiling_photo():
    sharp_smiling_but_blinking = person(closed=1, smile=0.9, face_sharp=95, face_exposure=90)
    plain_but_eyes_open = person(closed=0, smile=0.1, face_sharp=60, face_exposure=60)
    rec = _rec([sharp_smiling_but_blinking, plain_but_eyes_open])
    assert (rec.index, rec.deciding_criterion, rec.tie) == (1, "closed_eyes", False)


@pytest.mark.parametrize("scale", [0.6, 1.0, 1.5])
def test_closed_eyes_is_an_exact_integer_compare_whatever_the_sensitivity(scale):
    rec = _rec([person(closed=2), person(closed=1)], scale)
    assert (rec.index, rec.deciding_criterion) == (1, "closed_eyes")


def test_closed_eyes_compare_raw_counts_even_when_the_face_counts_differ():
    """Plan Q5': the count is the criterion, not a share. A photo that found only one of three
    people (the others turned away) with eyes open therefore beats one that found all three
    with one blink. Pinned on purpose - see the report's open decisions."""
    all_three_one_blink = person(n=3, closed=1)
    one_person_open = person(n=1, closed=0)
    assert _rec([all_three_one_blink, one_person_open]).index == 1


def test_equal_closed_eyes_pass_on_to_smile_when_someone_smiles():
    low, high = _smile_gap()
    a = person(closed=1, smile=low, face_sharp=90)
    b = person(closed=1, smile=high, face_sharp=60)
    rec = _rec([a, b])
    assert (rec.index, rec.deciding_criterion) == (1, "smile")


def test_a_smile_difference_inside_the_deadband_passes_on_to_face_sharpness():
    from myphotoworks.core.ranking import SMILE_DEADBAND, SMILE_PRESENT_TH

    top = SMILE_PRESENT_TH + 0.3
    a = person(smile=top, face_sharp=60)
    b = person(smile=top - 0.3 * SMILE_DEADBAND, face_sharp=90)
    rec = _rec([a, b])
    assert (rec.index, rec.deciding_criterion) == (1, "face_sharpness")


def test_smile_is_skipped_when_nobody_in_the_group_smiles():
    """Everybody below ``SMILE_PRESENT_TH``: the smile gap is noise. The tiny scale removes the
    deadband, so only the skip rule can keep smile from deciding."""
    from myphotoworks.core.ranking import SMILE_PRESENT_TH

    a = person(smile=0.0, face_sharp=60)
    b = person(smile=SMILE_PRESENT_TH * 0.9, face_sharp=90)
    rec = _rec([a, b], scale=0.01)
    assert (rec.index, rec.deciding_criterion) == (1, "face_sharpness")
    rec = _rec([b, a], scale=0.01)
    assert rec.deciding_criterion == "face_sharpness"


def test_face_sharpness_decides_when_eyes_and_smile_tie():
    rec = _rec([person(face_sharp=90, face_exposure=40), person(face_sharp=50, face_exposure=90)])
    assert (rec.index, rec.deciding_criterion) == (0, "face_sharpness")


def test_face_exposure_decides_when_everything_before_it_ties():
    a = person(face_sharp=80.0, face_exposure=40)
    b = person(face_sharp=79.5, face_exposure=85)
    rec = _rec([a, b])
    assert (rec.index, rec.deciding_criterion, rec.tie) == (1, "face_exposure", False)


def test_face_sharpness_deadband_is_relative_and_scaled_by_sensitivity():
    from myphotoworks.core import ranking

    d = ranking.SHARPNESS_DEADBAND
    best = person(face_sharp=100.0)
    near = person(face_sharp=100.0 * (1 - 0.8 * d))     # 0.8 deadbands behind
    far = person(face_sharp=100.0 * (1 - 1.4 * d))      # 1.4 deadbands behind
    assert _rec([best, near], 1.0).tie is True
    assert _rec([best, near], 0.5).deciding_criterion == "face_sharpness"
    assert _rec([best, far], 1.0).deciding_criterion == "face_sharpness"
    assert _rec([best, far], 1.5).tie is True


def test_the_person_chain_reads_face_values_not_subject_values():
    a = person(face_sharp=40, subject_sharp=95)
    b = person(face_sharp=90, subject_sharp=30)
    assert _rec([a, b]).index == 1


def test_the_chain_narrows_step_by_step_over_several_photos():
    low, high = _smile_gap()
    group = [scores(99, 99, 99),                                  # faceless: out at step 1
             person(closed=1, smile=high, face_sharp=95),         # blinks: out at step 2
             person(closed=0, smile=low, face_sharp=95),          # no smile: out at step 3
             person(closed=0, smile=high, face_sharp=40)]
    rec = _rec(group)
    assert (rec.index, rec.deciding_criterion) == (3, "smile")


# ---- ties and single photos -----------------------------------------------------------------


def test_everything_inside_the_deadbands_is_a_tie_decided_by_the_tiebreak():
    from myphotoworks.core.ranking import reason_label

    a = person(face_sharp=80.0, face_exposure=70.0)
    b = person(face_sharp=80.4, face_exposure=70.3)
    rec = _rec([a, b])
    assert rec.tie is True and rec.deciding_criterion is None
    assert rec.index == 1                       # the weighted tiebreak still picks the larger sum
    assert reason_label(rec, 2) == "차이 미미"


def test_identical_person_photos_pick_the_first():
    s = person()
    rec = _rec([s, s, s])
    assert (rec.index, rec.tie) == (0, True)


def test_a_single_person_photo_is_a_single_photo():
    from myphotoworks.core.ranking import reason_label

    rec = _rec([person(closed=1)])
    assert (rec.index, rec.deciding_criterion, rec.tie) == (0, None, False)
    assert reason_label(rec, 1) == "단독 사진"


# ---- badge text (plan §5-4) -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("criterion", "text"),
    [("closed_eyes", "눈 감음 적음"), ("smile", "웃음 우세"),
     ("face_sharpness", "얼굴 선명도 우세"), ("face_exposure", "얼굴 노출 우세"),
     ("face_detected", "얼굴 인식 우세")],
)
def test_reason_label_names_the_deciding_face_criterion(criterion, text):
    from myphotoworks.core.ranking import Recommendation, reason_label

    assert reason_label(Recommendation(1, criterion, False), 3) == text


# ---- detail-panel rows (plan §4-7, §5-4) ----------------------------------------------------


def _rows(group, index, scale=1.0):
    from myphotoworks.core.ranking import criterion_rows

    return criterion_rows(group, index, _rec(group, scale), deadband_scale=scale)


def test_person_group_rows_are_the_four_person_criteria_with_korean_labels():
    rows = _rows([person(), person()], 0)
    assert [r.name for r in rows] == ["closed_eyes", "smile", "face_sharpness", "face_exposure"]
    for row, word in zip(rows, ("눈 감음", "웃음", "얼굴 선명도", "얼굴 노출"), strict=True):
        assert word in row.label


def test_group_without_faces_keeps_the_three_stage_one_rows():
    """Regression guard (passes today)."""
    rows = _rows([scores(80, 70, 60), scores(40, 70, 60)], 0)
    assert [r.name for r in rows] == ["subject_sharpness", "subject_exposure", "color"]


def test_person_rows_are_relative_to_the_group_best():
    group = [person(smile=0.8, face_sharp=80, face_exposure=40),
             person(smile=0.4, face_sharp=40, face_exposure=80)]
    first, second = _rows(group, 0), _rows(group, 1)
    assert [r.relative for r in first[1:]] == pytest.approx([1.0, 1.0, 0.5])
    assert [r.relative for r in second[1:]] == pytest.approx([0.5, 0.5, 1.0])
    assert first[2].value == 80 and second[1].value == pytest.approx(0.4)


def test_closed_eyes_row_shows_the_count_and_is_best_for_the_fewest():
    group = [person(n=3, closed=2), person(n=3, closed=0), person(n=3, closed=1)]
    rows = [_rows(group, i)[0] for i in range(3)]
    assert [r.value for r in rows] == [2, 0, 1]
    assert rows[1].relative == pytest.approx(1.0)               # fewest closed eyes = full bar
    assert 0.0 <= rows[0].relative < rows[2].relative < 1.0     # more closed eyes = shorter bar


def test_closed_eyes_row_is_full_for_everybody_when_nobody_blinks():
    group = [person(closed=0), person(closed=0)]
    assert [_rows(group, i)[0].relative for i in (0, 1)] == [1.0, 1.0]


def test_deciding_row_is_flagged_once_and_undecided_rows_read_as_tied():
    group = [person(face_sharp=80.0, face_exposure=40), person(face_sharp=79.5, face_exposure=85)]
    rows = _rows(group, 1)
    assert [r.deciding for r in rows] == [False, False, False, True]
    assert [r.tied for r in rows] == [True, True, True, False]   # eyes equal, smile skipped, sharp


def test_closed_eyes_row_is_the_deciding_one_when_eyes_decide():
    rows = _rows([person(closed=1), person(closed=0)], 1)
    assert [r.deciding for r in rows] == [True, False, False, False]
    assert rows[0].tied is False


def test_a_faceless_photo_shows_empty_bars_and_decides_nothing():
    group = [person(smile=0.5, face_sharp=80), scores(90, 90, 90)]
    rows = _rows(group, 1)
    assert [r.relative for r in rows] == [0.0, 0.0, 0.0, 0.0]
    assert not any(r.deciding for r in rows)


def test_ties_are_judged_among_the_photos_that_competed():
    """A faceless photo is out of the race and must not stop its rivals from reading as tied."""
    group = [person(smile=0.5, face_sharp=80), person(smile=0.5, face_sharp=60), scores()]
    rec = _rec(group)
    assert (rec.index, rec.deciding_criterion) == (0, "face_sharpness")
    rows = _rows(group, 0)
    assert [r.tied for r in rows] == [True, True, False, True]
    assert rows[2].deciding is True
