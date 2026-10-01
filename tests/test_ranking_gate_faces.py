"""Stage-3 refinement — the failure gate in the person chain (code review of PR #44).

Stage 1 keeps photos with a (nearly) black / blown-out subject or no detail at all out of the race
while a usable photo exists. The person chain had no such gate, so a face with destroyed exposure
could still win on one fewer blink. Now, in a person group:

    * a photo with a face is *failed* when its face exposure is below ``EXPOSURE_FAIL`` or its
      face sharpness below ``SHARPNESS_FAIL`` (the stage-1 limits, applied to the face values)
    * failed photos only compete when no photo with a face passed
    * photos without a face are never "failed" (the face chain already ranks them last)
    * when the gate leaves exactly one photo *with a face*, ``deciding_criterion == "gate"``
      (badge "다른 사진은 사용 어려움"), like in the subject chain

``criterion_rows`` judges ties among the photos that competed, as before.
"""
import pytest

from tests.synthetic import person, scores


def _rec(group, scale=1.0):
    from myphotoworks.core.ranking import recommend

    return recommend(group, deadband_scale=scale)


def _dark():
    from myphotoworks.core.ranking import EXPOSURE_FAIL

    return EXPOSURE_FAIL - 5.0


def _smeared():
    from myphotoworks.core.ranking import SHARPNESS_FAIL

    return SHARPNESS_FAIL - 5.0


def test_a_usable_face_photo_beats_a_destroyed_one_even_with_more_blinks():
    blinking_but_usable = person(closed=1, face_exposure=80)
    open_eyes_but_black = person(closed=0, face_exposure=_dark())
    rec = _rec([blinking_but_usable, open_eyes_but_black])
    assert (rec.index, rec.deciding_criterion, rec.tie) == (0, "gate", False)


def test_a_face_without_detail_is_gated_too():
    rec = _rec([person(closed=0, face_sharp=_smeared()), person(closed=1, face_sharp=70)])
    assert (rec.index, rec.deciding_criterion) == (1, "gate")


def test_failed_photos_do_not_take_part_in_the_chain_when_several_photos_pass():
    group = [person(closed=0, face_exposure=_dark()),       # failed: out
             person(closed=2, face_exposure=80),
             person(closed=1, face_exposure=80)]
    rec = _rec(group)
    assert (rec.index, rec.deciding_criterion) == (2, "closed_eyes")


def test_when_every_face_photo_fails_the_chain_runs_on_all_of_them():
    rec = _rec([person(closed=1, face_exposure=2), person(closed=0, face_exposure=3)])
    assert (rec.index, rec.deciding_criterion) == (1, "closed_eyes")


def test_a_faceless_photo_is_never_failed_and_never_preferred_over_a_face():
    """The face photos all fail the gate: nobody is gated, and the face still beats no face."""
    group = [scores(95, 90, 80), person(face_exposure=_dark())]
    rec = _rec(group)
    assert (rec.index, rec.deciding_criterion) == (1, "face_detected")


def test_a_failed_face_photo_next_to_a_faceless_one_leaves_the_usable_face_photo_the_winner():
    group = [scores(95, 90, 80), person(face_exposure=_dark()), person(face_exposure=80)]
    rec = _rec(group)
    assert rec.index == 2 and rec.deciding_criterion == "gate"


def test_the_gate_uses_the_face_values_not_the_subject_values():
    """A black subject measurement (face source) is the face; a sharp background is irrelevant."""
    group = [person(face_exposure=80, subject_exposure=0, subject_sharp=0),
             person(face_exposure=_dark(), subject_exposure=90, subject_sharp=95)]
    assert _rec(group).index == 0


def test_a_group_where_nobody_fails_decides_as_before():
    """Regression guard (passes today)."""
    rec = _rec([person(closed=1), person(closed=0)])
    assert (rec.index, rec.deciding_criterion) == (1, "closed_eyes")


@pytest.mark.parametrize("scale", [0.6, 1.0, 1.5])
def test_the_gate_does_not_depend_on_the_sensitivity(scale):
    rec = _rec([person(closed=1, face_exposure=80), person(closed=0, face_exposure=_dark())], scale)
    assert (rec.index, rec.deciding_criterion) == (0, "gate")


def test_ties_are_judged_among_the_photos_that_competed():
    """A destroyed photo is out of the race and must not stop its rivals from reading as tied."""
    from myphotoworks.core.ranking import criterion_rows

    group = [person(face_sharp=80, face_exposure=40), person(face_sharp=78, face_exposure=85),
             person(face_sharp=50, face_exposure=_dark())]      # failed, and far less sharp
    rec = _rec(group)
    assert (rec.index, rec.deciding_criterion) == (1, "face_exposure")
    rows = criterion_rows(group, 1, rec)
    assert [r.tied for r in rows] == [True, True, True, False]
    assert rows[3].relative == pytest.approx(85 / 85) and rows[2].relative == pytest.approx(78 / 80)


def test_the_gate_badge_in_a_person_group():
    from myphotoworks.models.group_session import GroupSession
    from tests.test_group_session_faces import photo

    ps = [photo("a", person(closed=1, face_exposure=80, face_sharp=70)),
          photo("b", person(closed=0, face_exposure=_dark(), face_sharp=70))]
    GroupSession(ps, [[0, 1]], 1.0)
    assert ps[0].is_recommended and ps[0].reason.startswith("다른 사진은 사용 어려움")


def test_a_gated_out_photo_does_not_set_the_bars_of_the_photos_that_competed():
    """A photo whose face is destroyed (the landmarker sees nothing: 0 closed eyes) cannot win, so
    it must not make the winner's closed-eyes bar look short."""
    from myphotoworks.core.ranking import criterion_rows

    group = [person(closed=0, face_exposure=_dark()),          # gated out
             person(n=2, closed=1, face_exposure=80),          # the winner
             person(n=2, closed=2, face_exposure=80)]
    rec = _rec(group)
    assert (rec.index, rec.deciding_criterion) == (1, "closed_eyes")
    winner_rows = criterion_rows(group, 1, rec)
    assert winner_rows[0].relative == pytest.approx(1.0)       # fewest closed eyes among the field
    gated_rows = criterion_rows(group, 0, rec)
    assert all(0.0 <= r.relative <= 1.0 for r in gated_rows)
