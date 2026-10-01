"""Recommendation v2, stage 1 — subject-based scores (plan §4-2 .. §4-4).

New ``core/scoring.py`` API under test (gray arrays are float 0..255, ``region`` is a
``SubjectRegion``; scores are 0..100 unless noted):

    subject_sharpness(gray, region) -> float   top-percentile edge strength, grain tolerant
    motion_ratio(gray, region)      -> float   0..1, directional gradient energy ratio
    subject_exposure(gray, region)  -> float   subject-only mean + clipping, background ignored
    score_images(raw, corrected)    -> QualityScores(subject_sharpness, subject_exposure, color,
                                                     subject_source=..., motion_ratio=...)
    is_blurry(scores, group)        -> bool    redefined on ``subject_sharpness``

Thresholds are tuned later (plan §7), so these tests assert orderings, not magic numbers.
"""
import numpy as np
import pytest
from PIL import Image

from tests.synthetic import (
    PATCH,
    H,
    W,
    add_grain,
    backlit,
    blur,
    midtone_scene,
    motion_blur_x,
    scores,
    shallow_dof,
    texture,
    to_rgb_image,
)


def _full():
    from myphotoworks.core.subject import SubjectRegion

    return SubjectRegion(bbox=(0, 0, W, H), source="center", confidence=0.0)


def _patch():
    from myphotoworks.core.subject import SubjectRegion

    return SubjectRegion(bbox=PATCH, source="sharpest", confidence=1.0)


def _sharp(gray, region=None):
    from myphotoworks.core.scoring import subject_sharpness
    from myphotoworks.core.subject import detect_subject

    return subject_sharpness(gray, region or detect_subject(gray))


# ---- subject sharpness (§4-2) --------------------------------------------------


def test_sharpness_orders_sharp_over_mild_over_heavy_blur():
    base = texture(seed=2)
    sharp, mild, heavy = (_sharp(x, _full()) for x in (base, blur(base, 1.5), blur(base, 5.0)))
    assert sharp > mild > heavy


def test_shallow_dof_beats_uniform_mild_blur():
    """The old whole-frame metric ranked these the other way round."""
    shallow = _sharp(shallow_dof(seed=4))
    mild_everywhere = _sharp(blur(texture(seed=4), 2.0))
    assert shallow > mild_everywhere + 10


def test_background_blur_amount_does_not_change_subject_sharpness():
    a = _sharp(shallow_dof(seed=6, bg_sigma=3.0), _patch())
    b = _sharp(shallow_dof(seed=6, bg_sigma=8.0), _patch())
    assert abs(a - b) < 5


def test_grain_plus_defocus_is_not_sharper_than_clean_and_in_focus():
    """Film-scan case: grain inflates Laplacian variance, so out-of-focus looked sharp."""
    base = texture(seed=7)
    clean_in_focus = _sharp(base, _full())
    grainy_defocused = _sharp(add_grain(blur(base, 4.0), sigma=14.0), _full())
    assert grainy_defocused < clean_in_focus


def test_grain_does_not_hide_the_focus_difference():
    base = texture(seed=8)
    in_focus = _sharp(add_grain(base, sigma=14.0, seed=1), _full())
    defocused = _sharp(add_grain(blur(base, 4.0), sigma=14.0, seed=1), _full())
    assert in_focus > defocused + 10


def test_sharpness_is_within_zero_and_hundred():
    for img in (texture(), blur(texture(), 6.0), np.full((H, W), 100.0)):
        assert 0.0 <= _sharp(img, _full()) <= 100.0


def test_tiny_region_does_not_crash():
    from myphotoworks.core.scoring import subject_sharpness
    from myphotoworks.core.subject import SubjectRegion

    r = SubjectRegion(bbox=(10, 10, 12, 12), source="center", confidence=0.0)
    assert 0.0 <= subject_sharpness(texture(), r) <= 100.0


# ---- motion blur auxiliary metric (§4-2, stored only in stage 1) ---------------------


def test_motion_ratio_is_near_one_for_isotropic_texture():
    from myphotoworks.core.scoring import motion_ratio

    assert motion_ratio(texture(seed=9), _full()) >= 0.7


def test_horizontal_shake_lowers_motion_ratio():
    from myphotoworks.core.scoring import motion_ratio

    base = texture(seed=9)
    shaken = motion_ratio(motion_blur_x(base), _full())
    assert shaken < 0.5
    assert shaken < motion_ratio(base, _full())


def test_motion_ratio_is_within_zero_and_one_even_for_flat_input():
    from myphotoworks.core.scoring import motion_ratio

    for img in (texture(), np.full((H, W), 100.0)):
        assert 0.0 <= motion_ratio(img, _full()) <= 1.0


# ---- subject exposure (§4-3) ------------------------------------------------------------


def _exp(gray, region):
    from myphotoworks.core.scoring import subject_exposure

    return subject_exposure(gray, region)


def test_exposure_prefers_midtones_over_dark_and_blown_subject():
    mid, dark, bright = (np.full((H, W), v) for v in (118.0, 8.0, 252.0))
    assert _exp(mid, _full()) > 90
    assert _exp(mid, _full()) > _exp(dark, _full())
    assert _exp(mid, _full()) > _exp(bright, _full())


def test_backlit_background_is_not_penalised():
    """Blown-out background + well exposed subject must score like a mid-tone scene."""
    lit = _exp(backlit(), _patch())
    reference = _exp(midtone_scene(), _patch())
    assert lit >= 90
    assert abs(lit - reference) <= 5


def test_clipping_inside_the_subject_is_penalised():
    clean = midtone_scene()
    burnt = clean.copy()
    x0, y0, x1, y1 = PATCH
    burnt[y0:y1, x0:x0 + (x1 - x0) * 2 // 5] = 255.0      # 40 % of the subject blown out
    assert _exp(burnt, _patch()) < _exp(clean, _patch()) - 15


def test_clipping_outside_the_subject_is_ignored():
    clean = midtone_scene()
    background_burnt = clean.copy()
    background_burnt[:100, :] = 255.0                     # sky, well clear of PATCH
    assert abs(_exp(background_burnt, _patch()) - _exp(clean, _patch())) <= 1


def test_completely_black_or_white_subject_scores_at_the_floor():
    """These are the 'obvious failure' cases the ranking gate looks at."""
    assert _exp(np.zeros((H, W)), _full()) <= 10
    assert _exp(np.full((H, W), 255.0), _full()) <= 10


def test_exposure_is_within_zero_and_hundred():
    for img in (texture(), np.zeros((H, W)), np.full((H, W), 255.0), backlit()):
        assert 0.0 <= _exp(img, _full()) <= 100.0


# ---- score_images (pipeline entry) ------------------------------------------------------


def test_score_images_fills_all_v2_fields_and_finds_the_subject():
    from myphotoworks.core.scoring import QualityScores, score_images

    raw = to_rgb_image(shallow_dof(seed=10))
    s = score_images(raw, raw)
    assert isinstance(s, QualityScores)
    assert s.subject_source == "sharpest"
    assert 0.0 <= s.subject_sharpness <= 100.0
    assert 0.0 <= s.subject_exposure <= 100.0
    assert 0.0 <= s.color <= 100.0
    assert 0.0 <= s.motion_ratio <= 1.0


def test_sharpness_comes_from_raw_and_exposure_from_corrected():
    from myphotoworks.core.scoring import score_images

    raw = to_rgb_image(shallow_dof(seed=11))
    dark = Image.new("RGB", raw.size, (4, 4, 4))
    s_raw = score_images(raw, raw)
    s_dark = score_images(raw, dark)
    assert s_dark.subject_sharpness == s_raw.subject_sharpness
    assert s_dark.subject_exposure < s_raw.subject_exposure - 30
    assert s_dark.subject_source == s_raw.subject_source


# ---- blur flag (§4-2 last bullet) -------------------------------------------------------


def test_blur_flag_uses_subject_sharpness_relative_and_absolute():
    from myphotoworks.core.scoring import BLUR_ABS, BLUR_REL, is_blurry

    best = scores(90)
    relative = scores(90 * BLUR_REL * 0.9)           # clearly below the group's best share
    absolute = scores(BLUR_ABS * 0.5)
    group = [best, relative, absolute]
    assert not is_blurry(best, group)
    assert is_blurry(relative, group)
    assert is_blurry(absolute, group)


def test_single_photo_is_blurry_only_below_the_absolute_floor():
    from myphotoworks.core.scoring import BLUR_ABS, is_blurry

    ok, bad = scores(BLUR_ABS + 10), scores(BLUR_ABS - 10)
    assert not is_blurry(ok, [ok])
    assert is_blurry(bad, [bad])


# ---- tiny inputs and re-scoring (code review follow-ups) -----------------------------------


def test_one_pixel_subject_scores_zero_sharpness_without_crashing():
    from myphotoworks.core.scoring import motion_ratio, subject_sharpness
    from myphotoworks.core.subject import SubjectRegion

    r = SubjectRegion(bbox=(10, 10, 11, 11), source="center", confidence=0.0)
    assert subject_sharpness(texture(), r) == 0.0
    assert motion_ratio(texture(), r) == 1.0


def test_score_images_survives_tiny_images():
    from myphotoworks.core.scoring import score_images

    for size in ((1, 1), (2, 2), (3, 3), (4, 3), (3, 200)):
        s = score_images(Image.new("RGB", size, (90, 90, 90)), Image.new("RGB", size, (90, 90, 90)))
        assert 0.0 <= s.subject_sharpness <= 100.0 and 0.0 <= s.subject_exposure <= 100.0


def test_rescore_corrected_agrees_with_scoring_the_corrected_image_from_scratch():
    """Also for photos above the pixel budget, where the analysis grid is a resized copy."""
    from myphotoworks.core.scoring import rescore_corrected, score_images

    big = to_rgb_image(shallow_dof(seed=13)).resize((900, 700), Image.Resampling.BICUBIC)
    dark = Image.eval(big, lambda v: v // 3)
    first = score_images(big, big)
    again = rescore_corrected(first, big, dark)
    fresh = score_images(big, dark)
    assert again.subject_exposure == pytest.approx(fresh.subject_exposure, abs=1.0)
    assert again.color == pytest.approx(fresh.color)
    assert again.subject_sharpness == first.subject_sharpness
    assert again.subject_bbox == first.subject_bbox
