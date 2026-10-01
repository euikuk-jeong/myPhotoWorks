"""Recommendation v2, stage 3 — AF point through analysis and the group runner (plan §6-2).

``analyze_photo(..., hints=ExifHints(af_point=(x, y)))`` makes the AF region the subject
(``subject_source == "af"``, ``subject_bbox`` around the point, sharpness / exposure measured
there) unless a face is found, which wins. ``run_grouping`` gets the point from the file's own
EXIF through ``read_hints``; manual focus, scans, other makers and cropped files fall back to
the sharpest area on their own.
"""
from datetime import datetime

from myphotoworks.models.photo_item import PhotoItem
from myphotoworks.models.settings import AppSettings
from myphotoworks.processing.group_runner import run_grouping
from tests.synthetic import (
    FACE,
    PATCH,
    FakeFaceEngine,
    blend,
    fuji_jpeg,
    shallow_dof,
    to_rgb_image,
)

NOW = datetime(2026, 1, 1)
ON_PATCH = ((PATCH[0] + PATCH[2]) / 2 / 512, (PATCH[1] + PATCH[3]) / 2 / 384)   # the sharp part
ON_BLUR = (0.2, 0.25)


def _jpeg(tmp_path, name="p.jpg"):
    path = tmp_path / name
    to_rgb_image(shallow_dof(seed=5)).save(path, "JPEG", quality=95)
    return path


def _analyze(path, af=None, engine=None):
    from myphotoworks.core.grouping import ExifHints
    from myphotoworks.core.pipeline import analyze_photo

    hints = ExifHints(af_point=af) if af is not None else None
    return analyze_photo(path, NOW, hints=hints, face_engine=engine)


def test_the_af_region_becomes_the_subject(tmp_path):
    s = _analyze(_jpeg(tmp_path), af=ON_BLUR).scores
    assert s.subject_source == "af"
    x0, y0, x1, y1 = s.subject_bbox
    assert x0 <= ON_BLUR[0] * 512 < x1 and y0 <= ON_BLUR[1] * 384 < y1


def test_sharpness_is_measured_at_the_af_point(tmp_path):
    path = _jpeg(tmp_path)
    on_patch = _analyze(path, af=ON_PATCH).scores
    on_blur = _analyze(path, af=ON_BLUR).scores
    assert on_patch.subject_sharpness > on_blur.subject_sharpness + 10


def test_without_hints_or_an_af_point_the_subject_is_the_sharpest_area(tmp_path):
    path = _jpeg(tmp_path)
    assert _analyze(path).scores.subject_source == "sharpest"
    from myphotoworks.core.grouping import ExifHints
    from myphotoworks.core.pipeline import analyze_photo

    assert analyze_photo(path, NOW, hints=ExifHints()).scores.subject_source == "sharpest"


def test_a_face_beats_the_af_point(tmp_path):
    engine = FakeFaceEngine(boxes=[FACE], shapes=[blend()])
    s = _analyze(_jpeg(tmp_path), af=ON_BLUR, engine=engine).scores
    assert s.subject_source == "face" and s.subject_bbox == FACE


# ---- end to end through the file's EXIF -------------------------------------------------------


def _fuji_photo(tmp_path, name, **kw):
    px = (round(ON_BLUR[0] * 4000), round(ON_BLUR[1] * 3000))
    return PhotoItem(fuji_jpeg(tmp_path / name, shallow_dof(seed=5), focus_pixel=px, **kw))


def test_run_grouping_reads_the_af_point_from_the_file(tmp_path):
    photos = [_fuji_photo(tmp_path, "af.jpg"), _fuji_photo(tmp_path, "mf.jpg", focus_mode=1),
              _fuji_photo(tmp_path, "canon.jpg", make=b"Canon"),
              PhotoItem(_jpeg(tmp_path, "scan.jpg"))]
    run_grouping(photos, AppSettings(), face_engine_factory=lambda: None)
    sources = {p.source_path.name: p.scores.subject_source for p in photos}
    assert sources == {"af.jpg": "af", "mf.jpg": "sharpest", "canon.jpg": "sharpest",
                       "scan.jpg": "sharpest"}
    assert photos[0].analysis.hints.af_point is not None


def test_run_grouping_prefers_a_face_over_the_af_point(tmp_path):
    photos = [_fuji_photo(tmp_path, "af.jpg")]
    engine = FakeFaceEngine(boxes=[FACE], shapes=[blend()])
    run_grouping(photos, AppSettings(), face_engine_factory=lambda: engine)
    assert photos[0].scores.subject_source == "face"
