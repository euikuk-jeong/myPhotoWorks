from datetime import datetime, timedelta

import numpy as np
from PIL import Image, ImageFilter

from myphotoworks.core.grouping import (
    GroupingMode,
    GroupingParams,
    PhotoMeta,
    group_photos,
    judge_time_trust,
    natural_key,
    slider_from_threshold,
    threshold_from_slider,
)
from myphotoworks.core.similarity import compute_signature

T0 = datetime(2026, 1, 1, 12, 0, 0)


def scene(seed: int) -> Image.Image:
    rng = np.random.default_rng(seed)
    blocks = (rng.random((6, 8, 3)) * 255).astype("uint8")
    return Image.fromarray(blocks).resize((320, 240), Image.Resampling.BICUBIC)


def meta(name, seed, taken=None, blur=0.0):
    img = scene(seed)
    if blur:
        img = img.filter(ImageFilter.GaussianBlur(blur))
    return PhotoMeta(name, compute_signature(img), taken)


def sec(n):
    return T0 + timedelta(seconds=n)


def as_names(result, metas):
    return [[metas[i].name for i in g] for g in result.groups]


# ---- trust judgement ------------------------------------------------------


def test_trust_burst_with_varied_times_is_trusted():
    times = [sec(0), sec(0), sec(1), sec(30), sec(31), sec(60), sec(61), sec(90)]
    assert judge_time_trust(times).trusted


def test_trust_all_same_time_is_untrusted_film_scan():
    assert not judge_time_trust([sec(0)] * 10).trusted


def test_trust_missing_times_untrusted():
    assert not judge_time_trust([None, None, sec(0), None]).trusted
    assert not judge_time_trust([]).trusted


def test_trust_mostly_one_timestamp_untrusted():
    times = [sec(0)] * 8 + [sec(5), sec(9)]
    assert not judge_time_trust(times).trusted


# ---- grouping -------------------------------------------------------------


def test_burst_same_second_groups_together():
    metas = [meta("a1.jpg", 1, sec(0)), meta("a2.jpg", 1, sec(0), 1.0),
             meta("a3.jpg", 1, sec(1), 1.5), meta("b1.jpg", 2, sec(40)),
             meta("b2.jpg", 2, sec(41), 1.0), meta("c1.jpg", 3, sec(90)),
             meta("c2.jpg", 3, sec(91), 1.0)]
    r = group_photos(metas, GroupingParams())
    assert r.time_trusted
    assert as_names(r, metas) == [["a1.jpg", "a2.jpg", "a3.jpg"],
                                  ["b1.jpg", "b2.jpg"], ["c1.jpg", "c2.jpg"]]


def test_film_scan_identical_times_falls_back_to_similarity():
    metas = [meta("s01.jpg", 1, sec(0)), meta("s02.jpg", 1, sec(0), 1.0),
             meta("s03.jpg", 2, sec(0)), meta("s04.jpg", 2, sec(0), 1.0),
             meta("s05.jpg", 3, sec(0))]
    r = group_photos(metas, GroupingParams())
    assert not r.time_trusted
    assert "신뢰되지 않아" in r.message
    assert as_names(r, metas) == [["s01.jpg", "s02.jpg"], ["s03.jpg", "s04.jpg"], ["s05.jpg"]]


def test_no_exif_time_uses_filename_order():
    metas = [meta("img10.png", 2), meta("img2.png", 1), meta("img1.png", 1, blur=1.0),
             meta("img11.png", 2, blur=1.0)]
    r = group_photos(metas, GroupingParams())
    assert r.no_time_count == 4
    assert as_names(r, metas) == [["img1.png", "img2.png"], ["img10.png", "img11.png"]]


def test_close_time_but_different_scene_is_split():
    metas = [meta("a.jpg", 1, sec(0)), meta("b.jpg", 9, sec(1)),
             meta("c.jpg", 3, sec(20)), meta("d.jpg", 4, sec(40))]
    r = group_photos(metas, GroupingParams())
    assert r.time_trusted
    assert all(len(g) == 1 for g in r.groups)


def test_far_time_but_same_scene_is_joined():
    metas = [meta("a.jpg", 1, sec(0)), meta("b.jpg", 1, sec(120), 1.0),
             meta("c.jpg", 5, sec(200)), meta("d.jpg", 6, sec(300))]
    r = group_photos(metas, GroupingParams())
    assert r.time_trusted
    assert as_names(r, metas)[0] == ["a.jpg", "b.jpg"]


def test_drift_is_stopped_by_representative_check():
    # a~b and b~c look alike (progressive blur) but c has drifted far from a.
    metas = [meta("a.jpg", 1), meta("b.jpg", 1, blur=2.5), meta("c.jpg", 1, blur=12.0)]
    strict = GroupingParams(mode=GroupingMode.SIMILARITY_ONLY, threshold=0.93)
    r = group_photos(metas, strict)
    assert sum(len(g) for g in r.groups) == 3
    assert len(r.groups) >= 2


def test_time_first_mode_forces_split_by_gap_without_similarity():
    metas = [meta("a.jpg", 1, sec(0)), meta("b.jpg", 9, sec(1)), meta("c.jpg", 1, sec(30))]
    r = group_photos(metas, GroupingParams(mode=GroupingMode.TIME_FIRST, time_gap=2.0))
    assert as_names(r, metas) == [["a.jpg", "b.jpg"], ["c.jpg"]]


def test_similarity_only_ignores_time():
    metas = [meta("a.jpg", 1, sec(0)), meta("b.jpg", 1, sec(500), 1.0)]
    r = group_photos(metas, GroupingParams(mode=GroupingMode.SIMILARITY_ONLY))
    assert not r.time_trusted
    assert len(r.groups) == 1


def test_stricter_threshold_never_merges_more():
    metas = [meta(f"p{i}.jpg", 1, blur=i * 0.8) for i in range(6)]
    loose = group_photos(metas, GroupingParams(mode=GroupingMode.SIMILARITY_ONLY, threshold=0.6))
    strict = group_photos(metas, GroupingParams(mode=GroupingMode.SIMILARITY_ONLY, threshold=0.99))
    assert len(strict.groups) >= len(loose.groups)


def test_every_photo_assigned_exactly_once_and_empty_input():
    metas = [meta(f"p{i}.jpg", i, sec(i * 10)) for i in range(7)]
    r = group_photos(metas, GroupingParams())
    assert sorted(i for g in r.groups for i in g) == list(range(7))
    assert group_photos([], GroupingParams()).groups == []


def test_natural_key_and_slider_mapping():
    assert sorted(["img10", "img2", "img1"], key=natural_key) == ["img1", "img2", "img10"]
    assert threshold_from_slider(0) > threshold_from_slider(100)
    assert slider_from_threshold(threshold_from_slider(50)) == 50
