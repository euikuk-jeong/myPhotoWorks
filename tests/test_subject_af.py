"""Recommendation v2, stage 3 — the AF point in the subject chain (plan Q3, §6-2).

``core/subject.detect_subject(gray, face_boxes=None, af_point=None)``: ``af_point`` is
``(x, y)`` as shares (0..1) of the frame. Chain: faces -> AF point -> sharpest area -> centre.
The AF subject is a square of ``AF_REGION_FRACTION`` of the shorter side around the point,
``source == "af"``, clipped to the image. A point outside the frame is ignored.
"""
from tests.synthetic import FACE, H, W, shallow_dof

BLURRY_CORNER = (0.2, 0.25)          # the sharp patch of ``shallow_dof`` is on the right


def _detect(gray, **kw):
    from myphotoworks.core.subject import detect_subject

    return detect_subject(gray, **kw)


def test_the_af_point_beats_the_sharpest_area():
    from myphotoworks.core.subject import AF_REGION_FRACTION

    region = _detect(shallow_dof(seed=3), af_point=BLURRY_CORNER)
    assert region.source == "af" and 0.0 < region.confidence <= 1.0
    x0, y0, x1, y1 = region.bbox
    cx, cy = BLURRY_CORNER[0] * W, BLURRY_CORNER[1] * H
    assert x0 <= cx < x1 and y0 <= cy < y1
    side = AF_REGION_FRACTION * min(W, H)
    assert abs((x1 - x0) - side) <= 3 and abs((y1 - y0) - side) <= 3
    assert abs((x0 + x1) / 2 - cx) <= 2 and abs((y0 + y1) / 2 - cy) <= 2


def test_a_face_beats_the_af_point():
    region = _detect(shallow_dof(seed=3), face_boxes=[FACE], af_point=BLURRY_CORNER)
    assert region.source == "face" and region.bbox == FACE


def test_an_af_point_near_the_border_is_clipped_to_the_image():
    region = _detect(shallow_dof(seed=3), af_point=(0.01, 0.02))
    x0, y0, x1, y1 = region.bbox
    assert region.source == "af"
    assert 0 <= x0 < x1 <= W and 0 <= y0 < y1 <= H
    assert x0 <= 0.01 * W < x1 and y0 <= 0.02 * H < y1


def test_an_af_point_outside_the_frame_is_ignored():
    for point in ((1.5, 0.5), (-0.1, 0.5), (0.5, 1.2), (0.5, -0.3)):
        assert _detect(shallow_dof(seed=3), af_point=point).source == "sharpest"


def test_without_an_af_point_the_stage_two_chain_is_unchanged():
    gray = shallow_dof(seed=3)
    assert _detect(gray, af_point=None).source == "sharpest"
    assert _detect(gray, face_boxes=[FACE], af_point=None).source == "face"
