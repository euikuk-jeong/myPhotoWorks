import piexif
from PIL import Image

from myphotoworks.core.grouping import (
    ExifHints,
    GroupingMode,
    GroupingParams,
    PhotoMeta,
    group_photos,
    hints_consistent,
    hints_mismatch,
)
from myphotoworks.core.similarity import compute_signature
from myphotoworks.utils.exif_reader import read_hints
from tests.test_grouping import as_names, meta, sec


def with_hints(m: PhotoMeta, focal=None, lens=None, aperture=None) -> PhotoMeta:
    return PhotoMeta(m.name, m.signature, m.taken, ExifHints(focal, lens, aperture))


SIM_ONLY = dict(mode=GroupingMode.SIMILARITY_ONLY)


# ---- global clustering ------------------------------------------------------


def test_sequential_misses_separated_same_scene_but_global_joins_it():
    # scan order shuffled: scene 1 ... scene 2 ... scene 1 again
    metas = [meta("s01.jpg", 1), meta("s02.jpg", 2), meta("s03.jpg", 3),
             meta("s04.jpg", 1, blur=1.0)]
    seq = group_photos(metas, GroupingParams(**SIM_ONLY))
    assert len(seq.groups) == 4
    glob = group_photos(metas, GroupingParams(**SIM_ONLY, global_clustering=True))
    assert as_names(glob, metas) == [["s01.jpg", "s04.jpg"], ["s02.jpg"], ["s03.jpg"]]
    assert "전체에서 비교" in glob.message


def test_global_keeps_every_photo_exactly_once():
    metas = [meta(f"p{i}.jpg", i % 3, blur=(i // 3) * 0.7) for i in range(9)]
    r = group_photos(metas, GroupingParams(**SIM_ONLY, global_clustering=True))
    assert sorted(i for g in r.groups for i in g) == list(range(9))
    assert len(r.groups) <= 4


def test_global_does_not_apply_to_time_first_mode():
    metas = [meta("a.jpg", 1, sec(0)), meta("b.jpg", 9, sec(1)), meta("c.jpg", 1, sec(30))]
    r = group_photos(metas, GroupingParams(mode=GroupingMode.TIME_FIRST, global_clustering=True))
    assert as_names(r, metas) == [["a.jpg", "b.jpg"], ["c.jpg"]]
    assert "전체에서 비교" not in r.message


def test_global_on_empty_input():
    assert group_photos([], GroupingParams(global_clustering=True)).groups == []


# ---- EXIF hints ---------------------------------------------------------------


def test_hints_mismatch_rules():
    a = ExifHints(50.0, "LensA", 2.8)
    assert not hints_mismatch(a, ExifHints(52.0, "LensA", 2.8))   # within 15%
    assert hints_mismatch(a, ExifHints(85.0, "LensA", 2.8))       # focal differs
    assert hints_mismatch(a, ExifHints(50.0, "LensB", 2.8))       # lens differs
    assert hints_mismatch(a, ExifHints(50.0, "LensA", 8.0))       # > 1 stop
    assert not hints_mismatch(a, ExifHints(None, None, None))     # nothing to compare
    assert not hints_mismatch(a, None)


def test_hints_only_used_when_consistently_filled():
    full = [with_hints(meta(f"a{i}.jpg", i), focal=50.0) for i in range(5)]
    assert hints_consistent(full)
    sparse = [with_hints(meta(f"b{i}.jpg", i), focal=50.0 if i == 0 else None) for i in range(5)]
    assert not hints_consistent(sparse)
    assert not hints_consistent([])


def test_exif_mismatch_splits_borderline_pair_only_when_enabled():
    base, near = meta("a1.jpg", 1), meta("a2.jpg", 1, blur=2.5)
    metas = [with_hints(base, 24.0, "W", 4.0), with_hints(near, 85.0, "T", 4.0)]
    filler = [with_hints(meta(f"z{i}.jpg", 20 + i), 50.0, "N", 4.0) for i in range(4)]
    metas += filler
    # pick a threshold just under the pair's similarity so the penalty flips the result
    from myphotoworks.core.similarity import similarity
    s = similarity(base.signature, near.signature)
    thr = s - 0.02
    off = group_photos(metas, GroupingParams(**SIM_ONLY, threshold=thr))
    on = group_photos(metas, GroupingParams(**SIM_ONLY, threshold=thr, use_exif_hints=True))
    assert off.groups[0][:2] == [0, 1]           # joined without hints
    assert on.hints_used and on.groups[0] == [0]  # split with hints
    assert "EXIF" in on.message


def test_hints_ignored_and_reported_when_data_is_sparse():
    metas = [meta("a1.jpg", 1), meta("a2.jpg", 1, blur=1.0), meta("b1.jpg", 2)]
    r = group_photos(metas, GroupingParams(**SIM_ONLY, use_exif_hints=True))
    assert not r.hints_used
    assert "일관되지 않아" in r.message


def test_read_hints_from_file_and_missing(tmp_path):
    p = tmp_path / "a.jpg"
    exif = piexif.dump({"Exif": {
        piexif.ExifIFD.FocalLength: (50, 1),
        piexif.ExifIFD.FNumber: (28, 10),
        piexif.ExifIFD.LensModel: b"Test Lens",
    }})
    Image.new("RGB", (10, 10)).save(p, "JPEG", exif=exif)
    h = read_hints(p)
    assert h.focal == 50.0 and h.aperture == 2.8 and h.lens == "Test Lens"
    q = tmp_path / "b.png"
    Image.new("RGB", (10, 10)).save(q)
    assert read_hints(q) == ExifHints()
    assert read_hints(tmp_path / "missing.jpg") == ExifHints()


def test_manual_lens_zero_focal_is_treated_as_missing(tmp_path):
    p = tmp_path / "m.jpg"
    exif = piexif.dump({"Exif": {piexif.ExifIFD.FocalLength: (0, 1)}})
    Image.new("RGB", (10, 10)).save(p, "JPEG", exif=exif)
    assert read_hints(p).focal is None


def test_signature_helper_import_smoke():
    assert compute_signature is not None
