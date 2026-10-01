"""Stage-3 refinement — diagonal scenes are not "tilted" (code review of PR #44).

``core/composition.TILT_SEARCH_DEG`` (15 degrees): only lines within this distance of an axis vote
for the tilt. A staircase, a roof edge or a leading line at 20-45 degrees is a deliberate diagonal,
not a horizon the photographer failed to level, so it must not cost composition points. Lines
beyond the search range still count in the coherence test (they dilute it), so a scene dominated
by diagonals - or with level and diagonal lines in equal measure - gives ``None`` (no penalty)
instead of a tilt read from its few near-axis edges.

``estimate_tilt`` keeps its stage-3 contract inside the range (see ``test_composition.py``).
"""
import numpy as np
import pytest

from tests.synthetic import rings, tilted_stripes


def _tilt(gray):
    from myphotoworks.core.composition import estimate_tilt

    return estimate_tilt(gray)


def test_the_search_range_is_a_named_tunable_wider_than_the_free_zone():
    from myphotoworks.core.composition import TILT_BADGE_DEG, TILT_FREE_DEG, TILT_SEARCH_DEG

    assert TILT_SEARCH_DEG > TILT_BADGE_DEG > TILT_FREE_DEG > 0


@pytest.mark.parametrize("angle", [20.0, 25.0, 30.0, 40.0, 45.0])
def test_lines_far_from_both_axes_are_a_diagonal_composition_not_a_tilt(angle):
    assert _tilt(tilted_stripes(angle)) is None
    assert _tilt(tilted_stripes(-angle)) is None


def test_the_largest_tilt_inside_the_range_is_still_measured():
    from myphotoworks.core.composition import TILT_SEARCH_DEG

    angle = TILT_SEARCH_DEG - 2.0
    t = _tilt(tilted_stripes(angle))
    assert t is not None and abs(abs(t) - angle) < 1.0


def test_a_scene_level_and_diagonal_in_about_equal_measure_has_no_clear_tilt():
    level, diagonal = tilted_stripes(0.0), tilted_stripes(25.0)
    mixed = level.copy()
    mixed[:, 220:] = diagonal[:, 220:]                       # 43 % level, 57 % diagonal
    assert _tilt(mixed) is None


def test_a_few_level_lines_in_a_diagonal_scene_do_not_decide_the_tilt():
    level, diagonal = tilted_stripes(0.0), tilted_stripes(25.0)
    mostly_diagonal = level.copy()
    mostly_diagonal[:, 100:] = diagonal[:, 100:]
    assert _tilt(mostly_diagonal) is None


def test_slightly_tilted_lines_beside_a_few_diagonals_still_read_as_tilted():
    """The horizon is the dominant structure: 5 degrees over most of the frame."""
    tilted, diagonal = tilted_stripes(5.0), tilted_stripes(25.0)
    scene = tilted.copy()
    scene[:, 440:] = diagonal[:, 440:]                       # a small diagonal corner
    t = _tilt(scene)
    assert t is not None and abs(abs(t) - 5.0) < 1.0


def test_round_and_noisy_scenes_are_still_none():
    rng = np.random.default_rng(0)
    for gray in (rings(), rng.random((384, 512)) * 255):
        assert _tilt(gray) is None


def test_a_diagonal_scene_costs_no_composition_points_end_to_end():
    """From pixels to the score: the stripes at 25 degrees leave the photo unpenalised."""
    from myphotoworks.core.composition import composition_score
    from myphotoworks.core.scoring import score_images
    from tests.synthetic import to_rgb_image

    img = to_rgb_image(tilted_stripes(25.0))
    s = score_images(img, img)
    assert s.tilt is None and composition_score(s.tilt) == 100.0
