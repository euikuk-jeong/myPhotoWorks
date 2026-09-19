import numpy as np
from PIL import Image, ImageFilter

from myphotoworks.core.scoring import (
    QualityScores,
    color_score,
    composite,
    explain,
    exposure_score,
    is_blurry,
    normalize_weights,
    recommend,
    score_images,
    sharpness_score,
)


def textured(size=(800, 600), seed=0) -> Image.Image:
    rng = np.random.default_rng(seed)
    a = (rng.random((size[1] // 4, size[0] // 4, 3)) * 255).astype("uint8")
    return Image.fromarray(a).resize(size, Image.Resampling.NEAREST)


def test_sharp_beats_blurred():
    sharp = textured()
    blurred = sharp.filter(ImageFilter.GaussianBlur(4))
    assert sharpness_score(sharp) > sharpness_score(blurred) + 20


def test_sharpness_consistent_across_resolution():
    big = textured((2000, 1500))
    small = big.resize((500, 375), Image.Resampling.LANCZOS)
    assert abs(sharpness_score(big) - sharpness_score(small)) < 20


def test_sharpness_consistent_across_aspect_ratio():
    wide = textured((1600, 600))
    square = textured((980, 980))
    assert abs(sharpness_score(wide) - sharpness_score(square)) < 15


def test_exposure_prefers_midtones_over_dark_and_blown():
    mid = Image.new("RGB", (100, 100), (118, 118, 118))
    dark = Image.new("RGB", (100, 100), (8, 8, 8))
    bright = Image.new("RGB", (100, 100), (252, 252, 252))
    assert exposure_score(mid) > 90
    assert exposure_score(mid) > exposure_score(dark)
    assert exposure_score(mid) > exposure_score(bright)


def test_color_score_gray_lower_than_saturated():
    gray = Image.new("RGB", (100, 100), (120, 120, 120))
    rng = np.random.default_rng(1)
    vivid = Image.fromarray((rng.random((100, 100, 3)) * 255).astype("uint8"))
    assert color_score(vivid) > color_score(gray)
    assert color_score(gray) == 0.0


def test_exposure_color_use_corrected_image_but_sharpness_uses_raw():
    raw = textured()
    dark = Image.new("RGB", raw.size, (5, 5, 5))
    s = score_images(raw, dark)
    assert s.sharpness == sharpness_score(raw)
    assert s.exposure == exposure_score(dark)


def test_weights_normalise_and_zero_falls_back_to_default():
    assert abs(sum(normalize_weights((2, 1, 1))) - 1.0) < 1e-9
    assert normalize_weights((0, 0, 0)) == (0.5, 0.3, 0.2)


def test_recommend_follows_weights_without_any_image():
    sharp_dull = QualityScores(90, 40, 40)
    soft_vivid = QualityScores(40, 90, 90)
    group = [sharp_dull, soft_vivid]
    assert recommend(group, (1, 0, 0)) == 0
    assert recommend(group, (0, 0.5, 0.5)) == 1
    assert composite(sharp_dull, (1, 0, 0)) == 90


def test_recommend_tie_prefers_first():
    s = QualityScores(50, 50, 50)
    assert recommend([s, s, s], (0.5, 0.3, 0.2)) == 0


def test_blur_flag_and_explain_labels():
    g = [QualityScores(85, 80, 70), QualityScores(45, 80, 70), QualityScores(20, 80, 70)]
    assert not is_blurry(g[0], g)
    assert is_blurry(g[1], g)   # < 60% of the group's best
    assert is_blurry(g[2], g)   # absolute floor
    w = (0.5, 0.3, 0.2)
    assert "선명도 1위" in explain(0, g, w)
    assert "흐림" in explain(2, g, w)
    assert explain(0, [g[0]], w).startswith("단독 사진")
