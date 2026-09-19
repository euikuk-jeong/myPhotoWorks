import numpy as np
from PIL import Image, ImageFilter

from myphotoworks.core.similarity import compute_signature, similarity


def scene(seed: int, size=(320, 240)) -> Image.Image:
    """Blocky pseudo-scene: smooth-ish random colour blocks."""
    rng = np.random.default_rng(seed)
    blocks = (rng.random((6, 8, 3)) * 255).astype("uint8")
    return Image.fromarray(blocks).resize(size, Image.Resampling.BICUBIC)


def test_identical_images_have_similarity_one():
    a = compute_signature(scene(1))
    assert similarity(a, compute_signature(scene(1))) == 1.0


def test_similar_scene_scores_higher_than_different_scene():
    base = scene(1)
    slight = base.filter(ImageFilter.GaussianBlur(1.5))
    other = scene(2)
    s_same = similarity(compute_signature(base), compute_signature(slight))
    s_diff = similarity(compute_signature(base), compute_signature(other))
    assert s_same > s_diff
    assert s_same > 0.85
    assert s_diff < 0.75


def test_stable_across_resolution_and_aspect_crop():
    small = scene(3, (160, 120))
    large = scene(3, (1600, 1200))
    assert similarity(compute_signature(small), compute_signature(large)) > 0.95


def test_symmetric_and_bounded():
    a, b = compute_signature(scene(4)), compute_signature(scene(5))
    assert similarity(a, b) == similarity(b, a)
    assert 0.0 <= similarity(a, b) <= 1.0


def test_brightness_shift_keeps_scene_more_similar_than_other_scene():
    base = scene(6)
    brighter = Image.eval(base, lambda v: min(255, v + 25))
    a = compute_signature(base)
    assert similarity(a, compute_signature(brighter)) > similarity(a, compute_signature(scene(7)))
