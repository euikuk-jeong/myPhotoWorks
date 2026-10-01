"""Recommendation v2, stage 3 — composition penalty: horizon tilt and cut faces (plan §6-1).

New ``core/composition.py`` API under test (pure NumPy, no Qt):

    TILT_FREE_DEG, CUT_MARGIN_RATIO                        named tunables (plan §7)
    estimate_tilt(gray) -> float | None                    degrees from the nearest axis, or None
                                                           when there are no dominant straight lines
    cut_faces(boxes, image_size) -> int                    faces touching the frame edge
    composition_score(tilt, cut_faces=0) -> float          0..100, 100 = nothing to criticise

``QualityScores.tilt`` (degrees or ``None``) and ``FaceSummary.cut`` (int, default 0) carry the
raw measurements; ``score_images`` fills them. The score is derived, not stored. Values of the
tunables are tuned later, so inputs are built relative to the constants and only orderings are
asserted. The sign of a tilt is not part of the contract (the chain uses its magnitude); only
that opposite rotations give opposite signs.
"""
import numpy as np
import pytest

from tests.synthetic import FACE, rings, texture, tilted_stripes, to_rgb_image

# ---- estimate_tilt --------------------------------------------------------------------------


def _tilt(gray):
    from myphotoworks.core.composition import estimate_tilt

    return estimate_tilt(gray)


@pytest.mark.parametrize("angle", [3.0, 5.0, 12.0, -7.0])
def test_tilt_of_rotated_stripes_is_found_within_one_degree(angle):
    t = _tilt(tilted_stripes(angle))
    assert t is not None and abs(abs(t) - abs(angle)) < 1.0


def test_opposite_rotations_give_opposite_signs():
    plus, minus = _tilt(tilted_stripes(6.0)), _tilt(tilted_stripes(-6.0))
    assert plus * minus < 0


def test_level_lines_have_no_tilt():
    t = _tilt(tilted_stripes(0.0))
    assert t is not None and abs(t) < 0.7
    t = _tilt(texture(seed=3))                  # blocky noise: no clear lines, but never "tilted"
    assert t is None or abs(t) < 1.0


def test_the_tilt_is_the_distance_from_the_nearest_axis():
    """Lines at 90 + 5 degrees (a leaning building) are as tilted as lines at 5 degrees."""
    t = _tilt(np.rot90(tilted_stripes(5.0, 512, 384)).copy())
    assert t is not None and abs(abs(t) - 5.0) < 1.0


def test_no_dominant_lines_gives_none():
    rng = np.random.default_rng(0)
    for gray in (np.full((384, 512), 120.0), rng.random((384, 512)) * 255, rings()):
        assert _tilt(gray) is None                       # flat / noise / edges in all directions


def test_tiny_images_do_not_crash():
    for shape in ((1, 1), (3, 5), (8, 8)):
        assert _tilt(np.zeros(shape)) is None


# ---- cut_faces ------------------------------------------------------------------------------

SIZE = (1000, 800)


@pytest.mark.parametrize("box", [
    (0, 300, 200, 500), (800, 300, 1000, 500), (400, 0, 600, 200), (400, 600, 600, 800),
], ids=["left", "right", "top", "bottom"])
def test_a_face_touching_a_border_is_cut(box):
    from myphotoworks.core.composition import cut_faces

    assert cut_faces([box], SIZE) == 1


def test_a_face_well_inside_the_frame_is_not_cut():
    from myphotoworks.core.composition import cut_faces

    assert cut_faces([(300, 250, 500, 450)], SIZE) == 0
    assert cut_faces([], SIZE) == 0


def test_the_edge_margin_is_a_share_of_the_image_size():
    from myphotoworks.core.composition import CUT_MARGIN_RATIO, cut_faces

    near = round(SIZE[0] * CUT_MARGIN_RATIO * 0.5)
    far = round(SIZE[0] * CUT_MARGIN_RATIO * 3) + 1
    assert cut_faces([(near, 300, near + 200, 500)], SIZE) == 1       # just off the border
    assert cut_faces([(far, 300, far + 200, 500)], SIZE) == 0
    near_y = round(SIZE[1] * CUT_MARGIN_RATIO * 0.5)
    assert cut_faces([(400, 600 - near_y, 600, SIZE[1] - near_y)], SIZE) == 1   # bottom, in height


def test_every_cut_face_counts():
    from myphotoworks.core.composition import cut_faces

    boxes = [(0, 300, 200, 500), (400, 250, 600, 450), (800, 300, 1000, 500)]
    assert cut_faces(boxes, SIZE) == 2


# ---- composition_score ----------------------------------------------------------------------


def test_nothing_to_criticise_scores_100():
    from myphotoworks.core.composition import TILT_FREE_DEG, composition_score

    assert composition_score(None) == 100.0
    assert composition_score(0.0, 0) == 100.0
    assert composition_score(TILT_FREE_DEG, 0) == 100.0              # inside the free zone
    assert composition_score(-TILT_FREE_DEG, 0) == 100.0


def test_a_bigger_tilt_scores_lower_and_the_sign_does_not_matter():
    from myphotoworks.core.composition import TILT_FREE_DEG, composition_score

    a = composition_score(TILT_FREE_DEG + 1.0)
    b = composition_score(TILT_FREE_DEG + 2.0)
    assert 100.0 > a > b >= 0.0
    assert composition_score(5.0) == composition_score(-5.0)


def test_cut_faces_lower_the_score():
    from myphotoworks.core.composition import composition_score

    assert composition_score(None, 1) < composition_score(None, 0) == 100.0
    assert composition_score(None, 2) < composition_score(None, 1)


def test_tilt_and_cut_faces_add_up_and_the_score_stays_in_range():
    from myphotoworks.core.composition import composition_score

    both = composition_score(8.0, 1)
    assert both < composition_score(8.0, 0) and both < composition_score(None, 1)
    for tilt, cut in ((45.0, 20), (-30.0, 0), (None, 99)):
        assert 0.0 <= composition_score(tilt, cut) <= 100.0


# ---- scores ---------------------------------------------------------------------------------


def test_score_images_records_the_tilt_of_the_frame():
    from myphotoworks.core.scoring import score_images

    img = to_rgb_image(tilted_stripes(5.0))
    s = score_images(img, img)
    assert s.tilt is not None and abs(abs(s.tilt) - 5.0) < 1.0


def test_score_images_leaves_the_tilt_open_when_there_are_no_lines():
    from myphotoworks.core.scoring import score_images

    img = to_rgb_image(np.full((384, 512), 120.0))
    assert score_images(img, img).tilt is None


def test_score_images_counts_faces_cut_by_the_frame():
    from myphotoworks.core.scoring import score_images

    img = to_rgb_image(texture(seed=4))
    inside = score_images(img, img, faces=[(FACE, None)]).faces
    at_edge = score_images(img, img, faces=[((0, 80, 120, 200), None), (FACE, None)]).faces
    assert inside.cut == 0 and at_edge.cut == 1 and at_edge.count == 2


def test_a_correction_change_keeps_the_composition_measurements():
    from myphotoworks.core.scoring import rescore_corrected
    from tests.synthetic import face_summary, scores

    old = scores(60, 40, 50, tilt=4.5, faces=face_summary(cut=1, boxes=[FACE]))
    img = to_rgb_image(texture(seed=4))
    new = rescore_corrected(old, img, img)
    assert new.tilt == 4.5 and new.faces.cut == 1


def test_algorithm_version_marks_stage_three():
    from myphotoworks.core.scoring import ALGORITHM_VERSION

    assert ALGORITHM_VERSION.startswith("v2-stage3")
