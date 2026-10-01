"""Recommendation v2, stage 3 — GroupSession badges for composition (plan §6-1).

``PhotoItem.reason`` stays ``" · "``-joined. Order: deciding criterion (recommended photo only),
then the person-group face facts of stage 2 ("얼굴 없음" / "눈 감음 N명"), then

    "얼굴 잘림 N명"   person-group photo with N > 0 main faces touching the frame edge
    "기울어짐"        |tilt| >= ``composition.TILT_BADGE_DEG`` (any group of two or more)

and last the blur flag ("흐림", which the thumbnail looks for). Single photos keep exactly
"단독 사진".
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


def _badge_tilt(extra=3.0):
    from myphotoworks.core.composition import TILT_BADGE_DEG

    return TILT_BADGE_DEG + extra


def test_a_tilted_photo_is_badged_and_the_level_one_wins_on_composition():
    _, ps = make([("a", scores(80, 70, 60, tilt=_badge_tilt(8.0))),
                  ("b", scores(80, 70, 60, tilt=0.0))], [[0, 1]])
    assert ps[1].is_recommended and ps[1].reason == "구도 우세"
    assert ps[0].reason == "기울어짐"


def test_the_direction_of_the_tilt_does_not_matter_for_the_badge():
    _, ps = make([("a", scores(tilt=-_badge_tilt())), ("b", scores(tilt=_badge_tilt()))],
                 [[0, 1]])
    assert "기울어짐" in ps[0].reason and "기울어짐" in ps[1].reason


def test_a_slight_or_unknown_tilt_is_not_badged():
    from myphotoworks.core.composition import TILT_BADGE_DEG

    _, ps = make([("a", scores(tilt=max(0.0, TILT_BADGE_DEG - 1.0))), ("b", scores(tilt=None)),
                  ("c", scores(tilt=0.0))], [[0, 1, 2]])
    assert not any("기울어짐" in p.reason for p in ps)


def test_the_tilt_badge_follows_the_reason_on_the_recommended_photo():
    _, ps = make([("a", scores(80.0, 70.0, 60.0, tilt=_badge_tilt())),
                  ("b", scores(79.9, 70.0, 60.0, tilt=_badge_tilt()))], [[0, 1]])
    winner = next(p for p in ps if p.is_recommended)
    assert winner.reason == "차이 미미 · 기울어짐"


def test_a_cut_face_is_badged_with_the_number_of_cut_people():
    _, ps = make([("a", person(n=3, cut=2)), ("b", person(n=3, cut=0))], [[0, 1]])
    assert ps[1].is_recommended and ps[1].reason == "구도 우세"
    assert ps[0].reason == "얼굴 잘림 2명"


def test_all_badges_come_in_a_fixed_order():
    _, ps = make([("a", person(closed=0, face_sharp=90, subject_sharp=90)),
                  ("b", person(closed=1, n=2, cut=1, face_sharp=40, subject_sharp=10,
                               tilt=_badge_tilt()))], [[0, 1]])
    assert ps[0].reason == "눈 감음 적음"
    assert ps[1].reason == "눈 감음 1명 · 얼굴 잘림 1명 · 기울어짐 · 흐림"


def test_a_faceless_photo_of_a_person_group_can_be_tilted_too():
    _, ps = make([("a", scores(95, 90, 80, tilt=_badge_tilt())), ("b", person(face_sharp=40))],
                 [[0, 1]])
    assert ps[0].reason == "얼굴 없음 · 기울어짐"


def test_single_photos_get_no_composition_badges():
    _, ps = make([("a", person(n=2, cut=2, tilt=_badge_tilt(8.0))),
                  ("b", scores(tilt=_badge_tilt(8.0)))], [[0], [1]])
    assert ps[0].reason == "단독 사진" and ps[1].reason == "단독 사진"


def test_groups_without_composition_problems_keep_the_earlier_texts():
    """Regression guard (passes today)."""
    _, ps = make([("a", scores(90)), ("b", scores(30))], [[0, 1]])
    assert ps[0].reason.startswith("주제 선명도 우세") and ps[1].reason == "흐림"
    _, ps = make([("c", person(closed=1, face_sharp=90)), ("d", person(closed=0, face_sharp=60))],
                 [[0, 1]])
    assert ps[0].reason == "눈 감음 1명" and ps[1].reason == "눈 감음 적음"
