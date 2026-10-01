"""Recommendation v2, stage 2 — GroupSession badges for person groups (plan §5-4).

``PhotoItem.reason`` is ``" · "``-joined: the deciding criterion (recommended photo only, text
from ``ranking.reason_label``), then per-photo face facts, then the blur flag (the thumbnail
looks for "흐림" in it):

    "눈 감음 N명"   photo of a person group with N > 0 closed-eye main faces
    "얼굴 없음"      photo of a person group without a main face
    "흐림"           unchanged

Single-photo groups keep exactly "단독 사진"; groups without any face keep the stage-1 texts.
"""
from pathlib import Path

from myphotoworks.models.photo_item import PhotoItem
from tests.synthetic import person, scores


def photo(name, s):
    p = PhotoItem(Path(name))
    p.scores = s
    return p


def make(items, groups, sensitivity=1.0):
    from myphotoworks.models.group_session import GroupSession

    ps = [photo(n, s) for n, s in items]
    return GroupSession(ps, groups, sensitivity), ps


def test_the_winner_of_a_person_group_shows_the_deciding_face_criterion():
    s, ps = make([("a", person(closed=1, face_sharp=90)), ("b", person(closed=0, face_sharp=60))],
                 [[0, 1]])
    assert [p.is_recommended for p in ps] == [False, True]
    assert ps[1].reason == "눈 감음 적음"
    assert s.adopted_count() == 1 and ps[1].is_adopted


def test_photos_with_closed_eyes_show_how_many_people_blinked():
    _, ps = make([("a", person(n=3, closed=2)), ("b", person(n=3, closed=1)),
                  ("c", person(n=3, closed=0))], [[0, 1, 2]])
    assert ps[2].is_recommended and ps[2].reason == "눈 감음 적음"      # nobody blinks: no count
    assert ps[1].reason == "눈 감음 1명"
    assert ps[0].reason == "눈 감음 2명"


def test_a_faceless_photo_in_a_person_group_is_badged():
    _, ps = make([("a", scores(95, 90, 80)), ("b", person(face_sharp=40))], [[0, 1]])
    assert ps[1].is_recommended and ps[1].reason == "얼굴 인식 우세"
    assert ps[0].reason == "얼굴 없음"


def test_the_blur_badge_stays_next_to_the_face_badges():
    _, ps = make([("a", person(closed=0, face_sharp=90, subject_sharp=90)),
                  ("b", person(closed=1, face_sharp=40, subject_sharp=10))], [[0, 1]])
    assert ps[0].reason == "눈 감음 적음"
    assert ps[1].reason == "눈 감음 1명 · 흐림"
    assert "흐림" in ps[1].reason


def test_a_tied_person_group_says_negligible_difference():
    _, ps = make([("a", person(face_sharp=80.0, face_exposure=70.0)),
                  ("b", person(face_sharp=80.4, face_exposure=70.3))], [[0, 1]])
    assert ps[1].is_recommended and ps[1].reason == "차이 미미"


def test_single_photos_keep_the_single_badge_even_with_faces_and_blinks():
    _, ps = make([("a", person(closed=1)), ("b", scores())], [[0], [1]])
    assert ps[0].reason == "단독 사진" and ps[1].reason == "단독 사진"


def test_groups_without_faces_keep_the_stage_one_texts():
    """Regression guard (passes today)."""
    _, ps = make([("a", scores(90)), ("b", scores(30))], [[0, 1]])
    assert ps[0].reason.startswith("주제 선명도 우세")
    assert ps[1].reason == "흐림"


def test_a_new_sensitivity_flips_a_person_group_and_refreshes_the_reason():
    from myphotoworks.core.ranking import SHARPNESS_DEADBAND

    d = SHARPNESS_DEADBAND
    best = person(face_sharp=100.0, face_exposure=40)
    near = person(face_sharp=100.0 * (1 - 0.8 * d), face_exposure=90)     # 0.8 deadbands behind
    s, ps = make([("a", best), ("b", near)], [[0, 1]], sensitivity=1.0)
    assert ps[1].is_recommended and ps[1].reason.startswith("얼굴 노출 우세")
    s.rescore(0.5)
    assert ps[0].is_recommended and ps[0].is_adopted and not ps[1].is_adopted
    assert ps[0].reason.startswith("얼굴 선명도 우세")


def test_recommendation_is_refreshed_when_a_faceless_photo_joins_a_person_group():
    s, ps = make([("a", person(face_sharp=60)), ("b", person(face_sharp=90)),
                  ("c", scores(99, 99, 99))], [[0, 1], [2]])
    assert ps[1].is_recommended
    s.merge(0, 1)                                    # c joins: it is faceless and ranks last
    assert ps[1].is_recommended and not ps[2].is_recommended
    assert ps[2].reason == "얼굴 없음"


def test_blur_in_a_person_group_compares_faces_with_faces_and_the_rest_with_the_rest():
    """A faceless photo measures its sharpest area, a face photo its face: those numbers are not
    comparable, so a sharp background elsewhere must not make the face photos "흐림"."""
    _, ps = make([("a", person(face_sharp=80, subject_sharp=50)),
                  ("b", person(face_sharp=78, subject_sharp=50)),
                  ("c", scores(95, 90, 80))], [[0, 1, 2]])
    assert "흐림" not in ps[0].reason and "흐림" not in ps[1].reason
    assert "흐림" not in ps[2].reason
