"""Recommendation v2, stage 1 — subject region detection (plan §4-1).

``detect_subject(gray)`` takes a 2-D float array (0..255, the 512 px analysis copy) and
returns ``SubjectRegion(bbox=(x0, y0, x1, y1), source, confidence)``; ``bbox`` is in pixels
with x1/y1 exclusive. Stage 1 chain: sharpest area -> centre.
"""
import numpy as np

from tests.synthetic import PATCH, H, W, add_grain, blur, shallow_dof, texture


def _iou(a, b) -> float:
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union


def _detect(gray):
    from myphotoworks.core.subject import detect_subject

    return detect_subject(gray)


def test_region_is_a_frozen_value_with_bbox_source_confidence():
    from dataclasses import FrozenInstanceError

    from myphotoworks.core.subject import SubjectRegion

    r = SubjectRegion(bbox=(1, 2, 30, 40), source="sharpest", confidence=0.8)
    assert (r.bbox, r.source, r.confidence) == ((1, 2, 30, 40), "sharpest", 0.8)
    try:
        r.source = "center"
    except FrozenInstanceError:
        pass
    else:
        raise AssertionError("SubjectRegion must be immutable")


def test_shallow_dof_finds_the_sharp_patch():
    r = _detect(shallow_dof())
    assert r.source == "sharpest"
    assert _iou(r.bbox, PATCH) >= 0.5
    cx, cy = (PATCH[0] + PATCH[2]) // 2, (PATCH[1] + PATCH[3]) // 2
    assert r.bbox[0] <= cx < r.bbox[2] and r.bbox[1] <= cy < r.bbox[3]


def test_sharp_patch_in_a_corner_is_not_pulled_to_the_centre():
    base = texture(seed=3)
    img = blur(base, 6.0)
    patch = (20, 20, 160, 150)
    img[patch[1]:patch[3], patch[0]:patch[2]] = base[patch[1]:patch[3], patch[0]:patch[2]]
    r = _detect(img)
    assert r.source == "sharpest"
    assert _iou(r.bbox, patch) >= 0.4


def test_bbox_is_valid_and_inside_the_image():
    for img in (shallow_dof(), texture(), np.full((H, W), 90.0)):
        x0, y0, x1, y1 = _detect(img).bbox
        assert 0 <= x0 < x1 <= W and 0 <= y0 < y1 <= H


def test_grain_does_not_move_the_subject():
    r = _detect(add_grain(shallow_dof(), sigma=14.0))
    assert _iou(r.bbox, PATCH) >= 0.4


def test_uniformly_sharp_scene_has_low_confidence_and_falls_back_to_centre():
    focused = _detect(shallow_dof())
    even = _detect(texture(seed=5))              # pan-focus landscape: sharp everywhere
    assert even.source == "center"
    assert even.confidence < focused.confidence
    x0, y0, x1, y1 = even.bbox
    assert x0 <= W // 2 < x1 and y0 <= H // 2 < y1


def test_flat_image_does_not_crash_and_uses_centre():
    r = _detect(np.full((H, W), 120.0))
    assert r.source == "center"
    assert 0.0 <= r.confidence <= 1.0


def test_tiny_image_does_not_crash():
    r = _detect(np.arange(16, dtype=np.float64).reshape(4, 4))
    x0, y0, x1, y1 = r.bbox
    assert 0 <= x0 < x1 <= 4 and 0 <= y0 < y1 <= 4


def test_confidence_is_within_zero_and_one():
    for img in (shallow_dof(), texture(), np.full((H, W), 90.0)):
        assert 0.0 <= _detect(img).confidence <= 1.0
