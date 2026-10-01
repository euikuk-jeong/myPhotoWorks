"""Recommendation v2, stage 1 — GroupSession on the priority chain (plan §4-6).

``GroupSession(photos, groups, sensitivity)`` and ``rescore(sensitivity)`` now take the
deadband multiplier (a float, normal = 1.0) instead of the three weights. Badge text
(``PhotoItem.reason``) comes from ``ranking.reason_label`` plus the blur flag.
"""
from pathlib import Path

from myphotoworks.models.photo_item import PhotoItem
from tests.synthetic import scores


def photo(name, sharp, exp=70, col=60):
    p = PhotoItem(Path(name))
    p.scores = scores(sharp, exp, col)
    return p


def make(sensitivity=1.0):
    """Group 0: a(90) b(70) c(30 blurry); group 1: d(60) e(80); group 2: f."""
    from myphotoworks.models.group_session import GroupSession

    ps = [photo("a", 90), photo("b", 70), photo("c", 30),
          photo("d", 60), photo("e", 80), photo("f", 50)]
    return GroupSession(ps, [[0, 1, 2], [3, 4], [5]], sensitivity), ps


def adopted(ps):
    return [p.source_path.name for p in ps if p.is_adopted]


def test_initial_recommendation_follows_the_chain_and_is_adopted():
    s, ps = make()
    assert [p.is_recommended for p in ps] == [True, False, False, False, True, True]
    assert adopted(ps) == ["a", "e", "f"]
    assert s.group_count() == 3 and s.single_count() == 1


def test_recommended_photo_shows_the_deciding_criterion_and_not_a_total():
    _, ps = make()
    assert ps[0].reason.startswith("주제 선명도 우세")
    assert ps[4].reason.startswith("주제 선명도 우세")
    assert ps[5].reason == "단독 사진"


def test_other_photos_no_longer_carry_a_composite_score_text():
    _, ps = make()
    assert "점" not in ps[1].reason and "종합" not in ps[1].reason
    assert "우세" not in ps[1].reason            # only the winner is "ahead"


def test_blur_badge_is_kept_alongside_the_reason():
    _, ps = make()
    assert "흐림" in ps[2].reason


def test_tied_group_is_badged_as_negligible_difference():
    from myphotoworks.models.group_session import GroupSession

    a, b = photo("a", 80.0, 70.0, 60.0), photo("b", 80.4, 70.3, 60.2)
    GroupSession([a, b], [[0, 1]], 1.0)
    assert a.is_recommended != b.is_recommended
    winner = a if a.is_recommended else b
    assert winner.reason.startswith("차이 미미")


def test_recommendation_refreshed_after_move_adoption_kept():
    s, ps = make()
    s.move_photo(ps[3], ps[0].group_id)        # d(60) joins a(90) group
    assert not ps[3].is_adopted                 # adoption unchanged
    assert ps[0].is_recommended and not ps[3].is_recommended
    assert ps[4].is_recommended                 # e is now alone in its old group
    assert ps[4].reason == "단독 사진"


def test_rescore_with_a_new_sensitivity_changes_only_untouched_groups_adoption():
    """Same contract as the old weight change: edited groups keep the user's choice."""
    from myphotoworks.core.ranking import SHARPNESS_DEADBAND

    from myphotoworks.models.group_session import GroupSession

    soft = 100.0 * (1 - 0.8 * SHARPNESS_DEADBAND)     # inside the deadband at 1.0, outside at 0.5
    a, b = photo("a", 100, 20), photo("b", soft, 90)
    c, d = photo("c", 100, 20), photo("d", soft, 90)
    s = GroupSession([a, b, c, d], [[0, 1], [2, 3]], 1.0)
    assert b.is_recommended and d.is_recommended        # sharpness tied -> exposure decides
    s.set_adopted(c, True)
    s.set_adopted(d, False)                              # group 1 is user-edited
    s.rescore(0.5)
    assert a.is_recommended and a.is_adopted and not b.is_adopted   # followed the new pick
    assert c.is_recommended                                          # badge updated
    assert c.is_adopted and not d.is_adopted                         # user choice kept


def test_rescore_refreshes_the_reason_text():
    from myphotoworks.core.ranking import SHARPNESS_DEADBAND

    from myphotoworks.models.group_session import GroupSession

    a = photo("a", 100.0, 70.0, 60.0)
    b = photo("b", 100.0 * (1 - 0.8 * SHARPNESS_DEADBAND), 70.0, 60.0)
    s = GroupSession([a, b], [[0, 1]], 1.0)
    assert a.reason.startswith("차이 미미")
    s.rescore(0.5)
    assert a.reason.startswith("주제 선명도 우세")


def test_photos_without_scores_stay_adopted_after_rescore():
    from myphotoworks.models.group_session import GroupSession

    ok, bad = photo("ok", 80), PhotoItem(Path("bad"))
    s = GroupSession([ok, bad], [[0], [1]], 1.0)
    s.rescore(0.6)
    assert bad.is_adopted and bad.scores is None


def test_label_records_the_sensitivity_used():
    s, _ = make(sensitivity=0.6)
    label = s.to_label_dict(Path("/r"))
    assert label["sensitivity"] == 0.6
    assert label["algorithm"] != "baseline"             # v2 labels must not claim "baseline"
