"""Explainability, item 1 — the measured subject area, as boxes in shares of the frame.

``QualityScores.analysis_size`` is the ``(width, height)`` of the analysis copy that
``subject_bbox`` and the face boxes live in. ``core.explain.subject_overlay`` turns the scores of
one photo into ``OverlayBox`` es whose ``rect`` is ``(x0, y0, x1, y1)`` in shares of the frame
(0..1), so the review preview can draw them at any display size, zoom and pan. No Qt here.
"""
import pytest
from PIL import Image

from tests.synthetic import face_summary, scores


def _img(w: int, h: int) -> Image.Image:
    return Image.new("RGB", (w, h), (120, 120, 120))


def _s(**kw):
    """A photo whose subject box is the middle half of a 400 x 200 analysis copy."""
    kw.setdefault("subject_source", "sharpest")
    return scores(subject_bbox=(100, 50, 300, 150), analysis_size=(400, 200), **kw)


# ---- analysis size is recorded by the pipeline ------------------------------------------------

def test_analysis_size_defaults_to_none():
    assert scores().analysis_size is None


def test_score_images_records_the_analysis_copy_size():
    from myphotoworks.core.scoring import _normalized_size, score_images

    raw = _img(2000, 1500)
    result = score_images(raw, raw)
    assert tuple(result.analysis_size) == tuple(_normalized_size(raw.size))
    w, h = result.analysis_size
    assert w * h <= 200_000 * 1.01 and w > h


def test_small_photo_is_analysed_at_its_own_size():
    from myphotoworks.core.scoring import score_images

    assert tuple(score_images(_img(400, 300), _img(400, 300)).analysis_size) == (400, 300)


def test_portrait_photo_analysis_copy_is_taller_than_wide():
    from myphotoworks.core.scoring import score_images

    w, h = score_images(_img(1500, 2000), _img(1500, 2000)).analysis_size
    assert h > w


def test_rescore_corrected_keeps_the_analysis_size():
    from myphotoworks.core.scoring import rescore_corrected, score_images

    raw = _img(2000, 1500)
    old = score_images(raw, raw)
    assert rescore_corrected(old, raw, raw).analysis_size == old.analysis_size


# ---- subject_overlay --------------------------------------------------------------------------

def test_no_scores_or_no_geometry_gives_no_boxes():
    from myphotoworks.core.explain import subject_overlay

    assert subject_overlay(None) == []
    assert subject_overlay(scores()) == []                                   # nothing measured
    assert subject_overlay(scores(subject_bbox=(1, 1, 9, 9))) == []          # no analysis size
    assert subject_overlay(scores(analysis_size=(400, 200))) == []           # no box


def test_box_is_given_in_shares_of_the_frame():
    from myphotoworks.core.explain import subject_overlay

    (box,) = subject_overlay(_s())
    assert box.rect == pytest.approx((0.25, 0.25, 0.75, 0.75))
    assert box.source == "sharpest"           # the view picks colour and line style from this


@pytest.mark.parametrize("source, label", [
    ("sharpest", "가장 선명한 영역"),
    ("af", "AF 포인트"),
])
def test_label_names_where_the_area_came_from(source, label):
    from myphotoworks.core.explain import subject_overlay

    (box,) = subject_overlay(_s(subject_source=source))
    assert box.label == label


def test_centre_fallback_says_that_no_subject_was_found():
    from myphotoworks.core.explain import subject_overlay

    (box,) = subject_overlay(_s(subject_source="center"))
    assert "중앙" in box.label and "찾지 못" in box.label


def test_unknown_source_gets_a_plain_label():
    from myphotoworks.core.explain import subject_overlay

    (box,) = subject_overlay(_s(subject_source="something-new"))
    assert box.label == "측정 영역" and box.source == "something-new"


def test_face_source_draws_each_face_not_their_union():
    from myphotoworks.core.explain import subject_overlay

    faces = face_summary(boxes=[(20, 40, 120, 140), (250, 60, 350, 160)])
    boxes = subject_overlay(scores(subject_bbox=(20, 40, 350, 160), analysis_size=(400, 200),
                                   subject_source="face", faces=faces))
    assert [b.source for b in boxes] == ["face", "face"]
    assert boxes[0].rect == pytest.approx((0.05, 0.2, 0.3, 0.7))
    assert boxes[1].rect == pytest.approx((0.625, 0.3, 0.875, 0.8))


def test_one_label_per_photo_on_the_first_face_box():
    """Colour tells the source apart; the text is said once, so several faces stay quiet."""
    from myphotoworks.core.explain import subject_overlay

    two = face_summary(boxes=[(20, 40, 120, 140), (250, 60, 350, 160)])
    boxes = subject_overlay(scores(subject_bbox=(20, 40, 350, 160), analysis_size=(400, 200),
                                   subject_source="face", faces=two))
    assert [b.label for b in boxes] == ["얼굴 2명", ""]

    one = face_summary(boxes=[(20, 40, 120, 140)])
    (box,) = subject_overlay(scores(subject_bbox=(20, 40, 120, 140), analysis_size=(400, 200),
                                    subject_source="face", faces=one))
    assert box.label == "얼굴"


def test_face_source_without_a_face_summary_falls_back_to_the_subject_box():
    from myphotoworks.core.explain import subject_overlay

    (box,) = subject_overlay(_s(subject_source="face"))
    assert box.label == "얼굴" and box.source == "face"


def test_boxes_are_clamped_to_the_frame():
    from myphotoworks.core.explain import subject_overlay

    s = scores(subject_bbox=(-20, -10, 500, 250), analysis_size=(400, 200),
               subject_source="sharpest")
    (box,) = subject_overlay(s)
    assert box.rect == (0.0, 0.0, 1.0, 1.0)


def test_boxes_without_area_are_dropped():
    from myphotoworks.core.explain import subject_overlay

    s = scores(subject_bbox=(100, 50, 100, 150), analysis_size=(400, 200),
               subject_source="sharpest")
    assert subject_overlay(s) == []


# ---- the coordinates survive the real pipeline ------------------------------------------------

def test_scored_landscape_photo_puts_the_face_where_it_is_in_the_original():
    from myphotoworks.core.explain import subject_overlay
    from myphotoworks.core.scoring import score_images

    raw = _img(2000, 1500)
    face = (1000, 300, 1400, 750)
    boxes = subject_overlay(score_images(raw, raw, faces=[(face, None)]))
    assert [b.source for b in boxes] == ["face"]
    assert boxes[0].rect == pytest.approx((0.5, 0.2, 0.7, 0.5), abs=0.01)


def test_scored_portrait_photo_puts_the_face_where_it_is_in_the_original():
    from myphotoworks.core.explain import subject_overlay
    from myphotoworks.core.scoring import score_images

    raw = _img(1500, 2000)
    face = (300, 1000, 700, 1400)
    boxes = subject_overlay(score_images(raw, raw, faces=[(face, None)]))
    assert boxes[0].rect == pytest.approx((0.2, 0.5, 700 / 1500, 0.7), abs=0.01)
