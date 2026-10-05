"""Explainability, item 3 — facts about a photo as badges on its card.

``PhotoItem.facts`` (filled by ``GroupSession`` from the same ``explain.photo_facts`` the review
window's second line uses) lists what is notable about one photo: "눈 감음 N명", "얼굴 잘림 N명",
"기울어짐", "얼굴 없음", "흐림". On a card the badges sit in the bottom-right corner of the photo,
stacked upwards, in the same style as the existing "흐림" badge (which keeps its own spot at the
bottom-left and is not repeated). They follow "추천 이유 표시". At most ``MAX_FACT_BADGES`` are
drawn, the rest is counted ("+2"); the tooltip still lists everything.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path  # noqa: E402

from PIL import Image  # noqa: E402
from PyQt6.QtCore import QRect  # noqa: E402

from myphotoworks.models.photo_item import PhotoItem  # noqa: E402
from tests.synthetic import person, scores  # noqa: E402

PHOTO = QRect(10, 20, 168, 112)


# ---- which badges ---------------------------------------------------------------------------

def test_facts_default_to_empty():
    assert PhotoItem(Path("x.jpg")).facts == ()


def test_blur_keeps_its_own_badge_and_is_not_repeated():
    from myphotoworks.ui.thumbnail_panel import visible_fact_badges

    assert visible_fact_badges(("눈 감음 1명", "기울어짐", "흐림")) == ["눈 감음 1명", "기울어짐"]
    assert visible_fact_badges(("흐림",)) == []


def test_no_facts_no_badges():
    from myphotoworks.ui.thumbnail_panel import visible_fact_badges

    assert visible_fact_badges(()) == []


def test_badges_are_capped_and_the_rest_is_counted():
    from myphotoworks.ui.thumbnail_panel import MAX_FACT_BADGES, visible_fact_badges

    assert MAX_FACT_BADGES == 2
    assert visible_fact_badges(("가", "나", "다", "라")) == ["가", "나", "+2"]
    assert visible_fact_badges(("가", "나")) == ["가", "나"]


# ---- where they sit -------------------------------------------------------------------------

def test_first_badge_sits_bottom_right_on_the_blur_row():
    from myphotoworks.ui.thumbnail_panel import fact_badge_rects

    (r,) = fact_badge_rects(PHOTO, [60])
    assert (r.width(), r.height()) == (60, 16)
    assert r.right() == PHOTO.right() - 5
    assert r.top() == PHOTO.bottom() - 21              # the row of the blur / status badge


def test_badges_stack_upwards_right_aligned_with_a_gap():
    from myphotoworks.ui.thumbnail_panel import fact_badge_rects

    first, second = fact_badge_rects(PHOTO, [60, 50])
    assert second.bottom() < first.top()
    assert first.top() - second.bottom() == 3          # 2 px gap
    assert first.right() == second.right()


def test_badge_is_never_wider_than_the_photo_minus_margins():
    from myphotoworks.ui.thumbnail_panel import fact_badge_rects

    narrow = QRect(0, 0, 75, 112)                      # a portrait photo
    (r,) = fact_badge_rects(narrow, [200])
    assert r.width() == 75 - 10 and narrow.contains(r)


def test_badge_moves_up_out_of_the_way_of_left_badges():
    from myphotoworks.ui.thumbnail_panel import fact_badge_rects

    narrow = QRect(0, 0, 75, 112)
    blur = QRect(narrow.left() + 5, narrow.bottom() - 21, 32, 16)
    status = QRect(narrow.left() + 5, narrow.bottom() - 39, 36, 16)
    rects = fact_badge_rects(narrow, [60, 40], avoid=[blur, status])
    placed = [r for r in rects if r is not None]
    assert placed
    for r in placed:
        assert narrow.contains(r)
        assert not r.intersects(blur) and not r.intersects(status)
    for i, a in enumerate(placed):
        assert all(not a.intersects(b) for b in placed[i + 1:])


def test_badges_keep_clear_of_the_star_and_checkbox_and_drop_out_when_there_is_no_room():
    from myphotoworks.ui.thumbnail_panel import fact_badge_rects

    short = QRect(0, 0, 168, 60)
    rects = fact_badge_rects(short, [60, 60, 60])
    placed = [r for r in rects if r is not None]
    assert len(placed) == 1 and rects[-1] is None
    assert all(r.top() >= short.top() + 26 for r in placed)   # below the star / checkbox row


# ---- the session fills the facts --------------------------------------------------------------

def _session(group_scores):
    from myphotoworks.models.group_session import GroupSession

    photos = []
    for i, s in enumerate(group_scores):
        item = PhotoItem(Path(f"p{i}.jpg"))
        item.scores = s
        photos.append(item)
    return GroupSession(photos, [list(range(len(photos)))], 1.0), photos


def test_session_fills_facts_and_the_reason_text_from_the_same_source():
    _, photos = _session([person(closed=1, tilt=4.0), person(closed=0)])
    assert photos[0].facts == ("눈 감음 1명", "기울어짐")
    assert "눈 감음 1명 · 기울어짐" in photos[0].reason
    assert photos[1].facts == ()
    assert photos[1].reason == "눈 감음 적음"           # the recommended photo: the decision only


def test_blur_is_one_of_the_facts():
    _, photos = _session([scores(80), scores(40)])
    assert photos[1].facts == ("흐림",)
    assert "흐림" in photos[1].reason


def test_facts_follow_group_edits():
    from myphotoworks.models.group_session import GroupSession

    photos = []
    for i, s in enumerate([person(closed=1), person(closed=0), person(closed=0)]):
        item = PhotoItem(Path(f"p{i}.jpg"))
        item.scores = s
        photos.append(item)
    session = GroupSession(photos, [[0, 1, 2]], 1.0)
    assert photos[0].facts == ("눈 감음 1명",)
    session.split_from(photos[1])                      # the blinking photo stays alone
    assert photos[0].facts == ()                       # alone in a group: nothing to compare
    session.merge(photos[0].group_id, photos[1].group_id)
    assert photos[0].facts == ("눈 감음 1명",)           # back in a group of three


def test_photos_that_were_not_analysed_have_no_facts():
    _, photos = _session([scores(80), scores(79)])
    assert photos[0].facts == ()
    unscored = PhotoItem(Path("u.jpg"))
    assert unscored.facts == ()


# ---- painting ---------------------------------------------------------------------------------

def test_card_paints_the_badges_only_while_reasons_are_shown(qtbot, tmp_path):
    from myphotoworks.models.group_session import GroupSession
    from myphotoworks.ui.thumbnail_panel import ThumbnailPanel, fact_badge_rects

    paths = []
    for i in range(2):
        path = tmp_path / f"c{i}.jpg"
        Image.new("RGB", (600, 400), (120, 140, 160)).save(path)
        paths.append(path)
    panel = ThumbnailPanel()
    qtbot.addWidget(panel)
    panel.resize(700, 400)
    panel.show()
    panel.add_photos(paths)
    photos = panel.all_photos()
    for photo, s in zip(photos, [person(closed=1), person(closed=0)], strict=True):
        photo.scores = s
    session = GroupSession(photos, [[0, 1]], 1.0)
    panel.set_session(session)
    panel.set_view(True, False)
    qtbot.waitUntil(lambda: all(panel.image_size(p) is not None for p in photos), timeout=5000)

    def badge_pixel(photo, shown):
        panel.set_options(shown)
        qtbot.wait(30)
        row = next(i for i, p in enumerate(panel._rows) if p is photo)
        item = panel.item(row)
        photo_rect = panel.itemDelegate().photo_rect(
            panel.visualItemRect(item), panel.indexFromItem(item))
        (rect,) = fact_badge_rects(photo_rect, [40])
        image = panel.viewport().grab().toImage()
        return image.pixel(rect.right() - 3, rect.center().y())

    assert badge_pixel(photos[0], True) != badge_pixel(photos[0], False)      # closed eyes: badge
    assert badge_pixel(photos[1], True) == badge_pixel(photos[1], False)      # nothing to say
