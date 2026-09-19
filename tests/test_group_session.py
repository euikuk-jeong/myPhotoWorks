from pathlib import Path

from myphotoworks.core.scoring import QualityScores
from myphotoworks.models.group_session import (
    TAG_EDITED,
    TAG_REVIEWED,
    TAG_TODO,
    GroupSession,
)
from myphotoworks.models.photo_item import PhotoItem

W = (0.5, 0.3, 0.2)


def photo(name, sharp, exp=70, col=60):
    p = PhotoItem(Path(name))
    p.scores = QualityScores(sharp, exp, col)
    return p


def make():
    """Group 0: a(90) b(70) c(30 blurry); group 1: d(60) e(80); group 2: f."""
    ps = [photo("a", 90), photo("b", 70), photo("c", 30),
          photo("d", 60), photo("e", 80), photo("f", 50)]
    s = GroupSession(ps, [[0, 1, 2], [3, 4], [5]], W)
    return s, ps


def adopted(ps):
    return [p.source_path.name for p in ps if p.is_adopted]


def test_initial_recommendation_is_adopted_and_counts():
    s, ps = make()
    assert adopted(ps) == ["a", "e", "f"]
    assert s.group_count() == 3 and s.single_count() == 1 and s.adopted_count() == 3
    assert [p.is_recommended for p in ps] == [True, False, False, False, True, True]
    assert "흐림" in ps[2].reason


def test_multi_adopt_and_single_undo_only_touches_that_photo():
    s, ps = make()
    s.set_adopted(ps[1], True)      # extra pick in group 0
    s.set_adopted(ps[3], True)      # extra pick in group 1
    assert adopted(ps) == ["a", "b", "d", "e", "f"]
    assert s.undo()
    assert adopted(ps) == ["a", "b", "e", "f"]   # only d reverted
    assert s.undo()
    assert adopted(ps) == ["a", "e", "f"]
    assert not s.undo()


def test_batch_buttons_are_single_undo_entries():
    s, ps = make()
    gid = ps[0].group_id
    s.adopt_all(gid)
    assert adopted(ps) == ["a", "b", "c", "e", "f"]
    s.clear_all(gid)
    assert adopted(ps) == ["e", "f"]
    s.adopt_recommended(gid)
    assert adopted(ps) == ["a", "e", "f"]
    s.undo()
    assert adopted(ps) == ["e", "f"]
    s.undo()
    assert adopted(ps) == ["a", "b", "c", "e", "f"]


def test_noop_operations_do_not_create_undo_entries():
    s, ps = make()
    s.set_adopted(ps[0], True)          # already adopted
    s.adopt_recommended(ps[0].group_id)  # already matches
    assert not s.can_undo


def test_move_photo_updates_membership_and_undo_restores():
    s, ps = make()
    src, dst = ps[2].group_id, ps[3].group_id
    s.move_photo(ps[2], dst)
    assert ps[2].group_id == dst
    assert [p.source_path.name for p in s.group(dst).photos] == ["d", "e", "c"]
    assert s.tag(dst) == TAG_EDITED and s.tag(src) == TAG_EDITED
    s.undo()
    assert ps[2].group_id == src
    assert [p.source_path.name for p in s.group(src).photos] == ["a", "b", "c"]
    assert s.tag(dst) == TAG_TODO


def test_moving_last_photo_removes_empty_group():
    s, ps = make()
    s.move_photo(ps[5], ps[0].group_id)
    assert s.group_count() == 2
    s.undo()
    assert s.group_count() == 3


def test_merge_absorbs_group_and_undo_restores_order():
    s, ps = make()
    g0, g1 = ps[0].group_id, ps[3].group_id
    order_before = [g.id for g in s.groups()]
    s.merge(g0, g1)
    assert s.group_count() == 2
    assert {p.source_path.name for p in s.group(g0).photos} == {"a", "b", "c", "d", "e"}
    assert s.undo()
    assert [g.id for g in s.groups()] == order_before
    assert ps[3].group_id == g1


def test_detach_creates_new_group_right_after_source():
    s, ps = make()
    g0 = ps[0].group_id
    new = s.detach_photo(ps[1])
    ids = [g.id for g in s.groups()]
    assert ids.index(new) == ids.index(g0) + 1
    assert [p.source_path.name for p in s.group(new).photos] == ["b"]
    assert s.detach_photo(ps[5]) is None       # already single
    s.undo()
    assert ps[1].group_id == g0


def test_recommendation_refreshed_after_move_adoption_kept():
    s, ps = make()
    s.move_photo(ps[4], ps[0].group_id)        # e(80) joins a(90) group
    assert ps[4].is_adopted                     # adoption unchanged
    assert ps[0].is_recommended and not ps[4].is_recommended
    assert ps[3].is_recommended                 # d is now alone in its old group


def test_rescore_follows_weights_only_for_untouched_groups():
    a = photo("a", 90, 20, 20)     # sharp, poor exposure
    b = photo("b", 40, 95, 95)     # soft, great exposure/colour
    c = photo("c", 90, 20, 20)
    d = photo("d", 40, 95, 95)
    s = GroupSession([a, b, c, d], [[0, 1], [2, 3]], (1, 0, 0))
    assert a.is_adopted and c.is_adopted
    s.set_adopted(c, False)
    s.set_adopted(d, True)                       # group 1 is user-edited
    s.rescore((0, 0.5, 0.5))
    assert b.is_recommended and b.is_adopted and not a.is_adopted    # followed
    assert d.is_recommended                                           # badge updated
    assert d.is_adopted and not c.is_adopted                          # user choice kept


def test_visible_photos_filter_and_tags():
    s, ps = make()
    assert len(s.visible_photos(False)) == 6
    assert [p.source_path.name for p in s.visible_photos(True)] == ["a", "e", "f"]
    g = ps[0].group_id
    assert s.tag(g) == TAG_TODO
    s.mark_reviewed(g)
    assert s.tag(g) == TAG_REVIEWED and s.reviewed_count() == 1
    s.set_adopted(ps[1], True)
    assert s.tag(g) == TAG_EDITED


def test_split_from_moves_selected_and_following_photos():
    s, ps = make()
    g0 = ps[0].group_id
    new = s.split_from(ps[1])              # b, c leave group 0
    assert [p.source_path.name for p in s.group(g0).photos] == ["a"]
    assert [p.source_path.name for p in s.group(new).photos] == ["b", "c"]
    ids = [g.id for g in s.groups()]
    assert ids.index(new) == ids.index(g0) + 1
    assert s.split_from(ps[0]) is None      # first photo: nothing to split off
    s.undo()
    assert [p.source_path.name for p in s.group(g0).photos] == ["a", "b", "c"]
    assert s.group_count() == 3


def test_add_photos_become_adopted_singles_and_clear_undo():
    s, ps = make()
    s.set_adopted(ps[1], True)
    assert s.can_undo
    new = PhotoItem(Path("new"))
    s.add_photos([new])
    assert s.group_count() == 4 and s.added_count() == 1
    assert new.is_adopted and not new.is_recommended and new.scores is None
    assert s.group(new.group_id).is_single
    assert not s.can_undo
    s.rescore(W)
    assert new.is_adopted            # unanalysed photos stay adopted


def test_remove_photos_deletes_empty_groups_and_rescores_untouched_groups():
    s, ps = make()
    s.remove_photos([ps[0]])                  # removes the recommended photo of group 0
    assert [p.source_path.name for p in s.group(ps[1].group_id).photos] == ["b", "c"]
    assert ps[1].is_recommended and ps[1].is_adopted   # untouched group follows new pick
    s.remove_photos([ps[5]])                  # last photo of the single group
    assert s.group_count() == 2
    assert len(s.photos_flat()) == 4
