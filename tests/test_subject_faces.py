"""Recommendation v2, stage 2 — faces lead the subject chain (plan Q3, §4-1 "얼굴은 2단계").

``core/subject.detect_subject(gray, face_boxes=())`` gets the main-face boxes (analysis-copy
pixels). With boxes the subject is their union, ``source == "face"``; without boxes the stage-1
chain (sharpest area -> centre) runs unchanged. Faces become the subject, so the blur badge and
the subject exposure of a portrait describe the face and not the sharp background behind it.
"""
from tests.synthetic import PATCH, H, W, shallow_dof


def _detect(gray, boxes=()):
    from myphotoworks.core.subject import detect_subject

    return detect_subject(gray, face_boxes=boxes)


def test_a_face_box_wins_over_the_sharpest_area():
    gray = shallow_dof(seed=3)                       # sharpest area = PATCH (right side)
    face = (20, 20, 120, 140)                        # a blurry corner
    region = _detect(gray, [face])
    assert region.source == "face"
    assert region.bbox == face
    assert 0.0 < region.confidence <= 1.0


def test_several_faces_form_the_union_box():
    region = _detect(shallow_dof(seed=3), [(20, 20, 100, 100), (200, 60, 300, 180)])
    assert region.source == "face"
    assert region.bbox == (20, 20, 300, 180)


def test_face_boxes_are_clipped_to_the_image():
    region = _detect(shallow_dof(seed=3), [(-30, -10, 80, 90), (W - 40, H - 40, W + 50, H + 60)])
    x0, y0, x1, y1 = region.bbox
    assert (x0, y0) == (0, 0) and (x1, y1) == (W, H)


def test_without_face_boxes_the_stage_one_chain_is_unchanged():
    gray = shallow_dof(seed=3)
    for none in ((), None, []):
        region = _detect(gray, none)
        assert region.source == "sharpest"
        px0, py0, px1, py1 = PATCH
        x0, y0, x1, y1 = region.bbox
        assert x0 < px1 and x1 > px0 and y0 < py1 and y1 > py0       # overlaps the sharp patch
