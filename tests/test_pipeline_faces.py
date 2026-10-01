"""Recommendation v2, stage 2 — analysis pipeline and group runner with faces (plan §5-2).

Seams under test (the real MediaPipe engine is never loaded; ``tests.synthetic.FakeFaceEngine``
stands in with the two-method engine protocol ``detect(rgb) -> boxes`` and
``blendshapes(face_crop_rgb) -> dict | None``):

    analyze_photo(path, taken, hints=None, correct=None, long_side=512, face_engine=None)
        512 px copy -> ``engine.detect`` -> main faces -> per main face a crop re-decoded from the
        original (``load_face_crop``) -> ``engine.blendshapes`` -> ``scores.faces``. Face
        sharpness comes from the uncorrected copy, face exposure from the corrected copy, both
        inside the face box of the analysis grid. A photo with faces gets
        ``subject_source == "face"`` and the union of its main faces as ``subject_bbox``.
        Any engine failure means "no faces" for that photo; analysis never raises because of it.
    run_grouping(photos, settings, progress=None, is_cancelled=None, face_engine_factory=...)
        builds the engine once per run through ``face_engine_factory()`` (default
        ``core.faces.get_face_engine``); ``None`` or an exception from the factory means no faces.
    refresh_correction_scores(photos, settings)      re-measures face exposure from cached boxes
    GroupSession.rescore(sensitivity)                never decodes, never detects
"""
import logging
from datetime import datetime

import piexif
import pytest
from PIL import Image, ImageFilter

from myphotoworks.models.photo_item import PhotoItem
from myphotoworks.models.settings import AppSettings, CorrectionMode
from myphotoworks.processing.group_runner import run_grouping
from tests.synthetic import (
    FACE,
    PATCH,
    FakeFaceEngine,
    backlit,
    blend,
    blur,
    box_with_area,
    shallow_dof,
    texture,
    to_rgb_image,
)
from tests.test_pipeline_v2 import detailed_scene

NOW = datetime(2026, 1, 1)
FACE_320 = (80, 60, 200, 180)       # a face inside the 320 x 240 scenes of ``detailed_scene``


def _jpeg(tmp_path, gray, name="p.jpg"):
    path = tmp_path / name
    to_rgb_image(gray).save(path, "JPEG", quality=95)
    return path


def _big_jpeg(tmp_path):
    path = tmp_path / "big.jpg"
    Image.fromarray(texture(1536, 2048, cell=16).astype("uint8")).convert("RGB").save(path, "JPEG")
    return path


def _analyze(path, engine, correct=None):
    from myphotoworks.core.pipeline import analyze_photo

    return analyze_photo(path, NOW, correct=correct, face_engine=engine)


# ---- single photo: when is the landmarker used --------------------------------------------


def test_without_an_engine_a_photo_has_no_faces(tmp_path):
    s = _analyze(_jpeg(tmp_path, shallow_dof(seed=5)), None).scores
    assert s.faces is None and s.subject_source == "sharpest"


def test_no_detection_means_no_faces_and_the_landmarker_is_never_called(tmp_path):
    engine = FakeFaceEngine(boxes=[])
    s = _analyze(_jpeg(tmp_path, shallow_dof(seed=5)), engine).scores
    assert s.faces is None and s.subject_source == "sharpest"
    assert len(engine.detect_shapes) == 1 and engine.crop_sizes == []


def test_the_detector_sees_the_512px_analysis_copy(tmp_path):
    engine = FakeFaceEngine(boxes=[])
    _analyze(_big_jpeg(tmp_path), engine)
    assert engine.detect_shapes == [(384, 512, 3)]            # an RGB array, long side 512
    assert engine.detect_dtypes == ["uint8"]


def test_the_landmarker_gets_a_crop_decoded_at_higher_resolution_than_the_512px_copy(tmp_path):
    engine = FakeFaceEngine(boxes=[FACE], shapes=[blend()])
    s = _analyze(_big_jpeg(tmp_path), engine).scores
    assert s.faces is not None and s.faces.count == 1
    (w, h), = engine.crop_sizes
    assert w >= 1.5 * (FACE[2] - FACE[0]) and h >= 1.5 * (FACE[3] - FACE[1])


# ---- single photo: what is measured ---------------------------------------------------------


def test_only_main_faces_reach_the_landmarker(tmp_path):
    from myphotoworks.core.faces import MAIN_FACE_REL_AREA

    area = (FACE[2] - FACE[0]) * (FACE[3] - FACE[1]) * MAIN_FACE_REL_AREA * 0.5
    minor = box_with_area(area, x0=300, y0=250)
    engine = FakeFaceEngine(boxes=[FACE, minor], shapes=[blend()])
    s = _analyze(_jpeg(tmp_path, shallow_dof(seed=5)), engine).scores
    assert len(engine.crop_sizes) == 1 and s.faces.count == 1
    assert s.faces.boxes == (FACE,)


def test_closed_count_and_smile_come_from_the_blendshapes(tmp_path):
    from myphotoworks.core.faces import EYE_CLOSED_TH

    left, right = (60, 60, 160, 160), (300, 60, 400, 160)         # same size
    shapes = [blend(blink_l=EYE_CLOSED_TH + 0.2),
              blend(smile_l=0.8, smile_r=0.8)]
    engine = FakeFaceEngine(boxes=[left, right], shapes=shapes)
    f = _analyze(_jpeg(tmp_path, shallow_dof(seed=5)), engine).scores.faces
    assert f.count == 2 and f.closed_eyes == 1
    assert f.smile == pytest.approx(0.4, abs=0.01)                # equal areas: plain mean


def test_a_wink_counts_as_closed(tmp_path):
    from myphotoworks.core.faces import EYE_CLOSED_TH

    engine = FakeFaceEngine(boxes=[FACE], shapes=[blend(blink_r=EYE_CLOSED_TH + 0.2)])
    assert _analyze(_jpeg(tmp_path, shallow_dof(seed=5)), engine).scores.faces.closed_eyes == 1


def test_tiny_faces_make_a_photo_faceless(tmp_path):
    from myphotoworks.core.faces import MIN_FACE_WIDTH_RATIO

    w = max(2, round(512 * MIN_FACE_WIDTH_RATIO * 0.8))
    engine = FakeFaceEngine(boxes=[(10, 10, 10 + w, 10 + w)], shapes=[blend()])
    s = _analyze(_jpeg(tmp_path, shallow_dof(seed=5)), engine).scores
    assert s.faces is None and engine.crop_sizes == []
    assert s.subject_source == "sharpest"


def test_a_face_the_landmarker_cannot_read_still_counts_as_a_neutral_open_face(tmp_path):
    engine = FakeFaceEngine(boxes=[FACE], shapes=[None])
    f = _analyze(_jpeg(tmp_path, shallow_dof(seed=5)), engine).scores.faces
    assert (f.count, f.closed_eyes, f.smile) == (1, 0, 0.0)


def test_face_boxes_are_stored_in_the_analysis_grid(tmp_path):
    engine = FakeFaceEngine(boxes=[FACE], shapes=[blend()])
    assert _analyze(_big_jpeg(tmp_path), engine).scores.faces.boxes == (FACE,)


def test_a_face_becomes_the_subject(tmp_path):
    engine = FakeFaceEngine(boxes=[FACE], shapes=[blend()])
    s = _analyze(_jpeg(tmp_path, shallow_dof(seed=5)), engine).scores    # sharp area is PATCH
    assert s.subject_source == "face" and s.subject_bbox == FACE


def test_face_sharpness_is_measured_on_the_face_not_the_frame(tmp_path):
    engine = FakeFaceEngine(boxes=[PATCH], shapes=[blend()])
    sharp_face = _analyze(_jpeg(tmp_path, shallow_dof(seed=5), "a.jpg"), engine).scores
    blurred = _analyze(_jpeg(tmp_path, blur(texture(seed=5), 3.0), "b.jpg"),
                       FakeFaceEngine(boxes=[PATCH], shapes=[blend()])).scores
    assert sharp_face.faces.sharpness > blurred.faces.sharpness + 10


def test_face_exposure_ignores_a_blown_out_background(tmp_path):
    good = _analyze(_jpeg(tmp_path, backlit(subject_mean=118.0), "a.jpg"),
                    FakeFaceEngine(boxes=[PATCH], shapes=[blend()])).scores
    blown = _analyze(_jpeg(tmp_path, backlit(subject_mean=250.0), "b.jpg"),
                     FakeFaceEngine(boxes=[PATCH], shapes=[blend()])).scores
    assert good.faces.exposure > 60 and good.faces.exposure > blown.faces.exposure


def test_face_exposure_follows_the_corrected_copy_but_sharpness_does_not(tmp_path):
    path = _jpeg(tmp_path, backlit(subject_mean=40.0))
    plain = _analyze(path, FakeFaceEngine(boxes=[PATCH], shapes=[blend()])).scores.faces
    lifted = _analyze(path, FakeFaceEngine(boxes=[PATCH], shapes=[blend()]),
                      correct=lambda im: im.point(lambda v: min(255, v + 80))).scores.faces
    assert lifted.exposure > plain.exposure + 10
    assert lifted.sharpness == pytest.approx(plain.sharpness)


# ---- single photo: the engine must never break the analysis ---------------------------------


def test_a_failing_detector_means_no_faces_and_a_log_entry(tmp_path, caplog):
    engine = FakeFaceEngine(fail_detect=True)
    with caplog.at_level(logging.WARNING):
        s = _analyze(_jpeg(tmp_path, shallow_dof(seed=5)), engine).scores
    assert s.faces is None and s.subject_sharpness > 0 and s.subject_source == "sharpest"
    assert caplog.records


def test_a_failing_landmarker_means_no_faces_for_that_photo(tmp_path, caplog):
    engine = FakeFaceEngine(boxes=[FACE], fail_blend=True)
    with caplog.at_level(logging.WARNING):
        s = _analyze(_jpeg(tmp_path, shallow_dof(seed=5)), engine).scores
    assert s.faces is None and s.subject_source == "sharpest"
    assert caplog.records


# ---- group runner ----------------------------------------------------------------------------


def _save(path, seed, taken, blur_sigma=0.0):
    img = detailed_scene(seed)
    if blur_sigma:
        img = img.filter(ImageFilter.GaussianBlur(blur_sigma))
    exif = piexif.dump({"Exif": {piexif.ExifIFD.DateTimeOriginal: taken.encode()}})
    img.save(path, "JPEG", quality=95, exif=exif)
    return PhotoItem(path)


@pytest.fixture
def photos(tmp_path):
    return [
        _save(tmp_path / "a1.jpg", 1, "2026:01:01 12:00:00"),
        _save(tmp_path / "a2.jpg", 1, "2026:01:01 12:00:01", blur_sigma=3.0),
        _save(tmp_path / "b1.jpg", 2, "2026:01:01 12:05:00"),
        _save(tmp_path / "b2.jpg", 2, "2026:01:01 12:05:01", blur_sigma=0.8),
        _save(tmp_path / "c1.jpg", 3, "2026:01:01 12:10:00"),
        _save(tmp_path / "d1.jpg", 4, "2026:01:01 12:20:00"),
    ]


def _engine():
    """Every photo has one face; the analysed photos (a1 a2 b1 b2 c1 d1) answer in that order:
    a1 and c1 blink."""
    from myphotoworks.core.faces import EYE_CLOSED_TH

    shut = blend(blink_l=EYE_CLOSED_TH + 0.3, blink_r=EYE_CLOSED_TH + 0.3)
    return FakeFaceEngine(boxes=[FACE_320], shapes=[shut, blend(), blend(), blend(), shut, blend()])


def test_the_engine_is_built_once_per_run_and_asked_once_per_photo(photos):
    engine, built = _engine(), []

    def factory():
        built.append(1)
        return engine

    run_grouping(photos, AppSettings(), face_engine_factory=factory)
    assert len(built) == 1
    assert len(engine.detect_shapes) == len(photos)
    run_grouping(photos, AppSettings(), face_engine_factory=factory)      # analyses are cached
    assert len(engine.detect_shapes) == len(photos)


def test_a_blinking_sharp_photo_loses_to_an_open_eyed_blurry_one_in_a_real_run(photos):
    session, _ = run_grouping(photos, AppSettings(), face_engine_factory=_engine)
    a1, a2 = photos[0], photos[1]
    assert [p.scores.faces.count for p in photos] == [1] * 6
    assert all(p.scores.subject_source == "face" for p in photos)
    assert a2.is_recommended and not a1.is_recommended
    assert a2.reason.startswith("눈 감음 적음")
    assert "눈 감음 1명" in a1.reason
    assert photos[4].reason == "단독 사진" and photos[5].reason == "단독 사진"
    assert session.adopted_count() == 4


def test_no_engine_from_the_factory_runs_the_stage_one_chain(photos):
    session, _ = run_grouping(photos, AppSettings(), face_engine_factory=lambda: None)
    assert all(p.scores.faces is None for p in photos)
    assert photos[0].is_recommended and photos[0].reason.startswith("주제 선명도 우세")
    assert session.adopted_count() == 4


def test_a_factory_that_raises_runs_the_stage_one_chain(photos, caplog):
    def broken():
        raise RuntimeError("model load failed")

    with caplog.at_level(logging.WARNING):
        session, _ = run_grouping(photos, AppSettings(), face_engine_factory=broken)
    assert all(p.scores.faces is None for p in photos)
    assert session.group_count() == 4
    assert caplog.records


def test_refresh_correction_scores_remeasures_face_exposure_without_the_engine(photos):
    from myphotoworks.processing.group_runner import refresh_correction_scores

    engine = _engine()
    run_grouping(photos, AppSettings(), face_engine_factory=lambda: engine)
    before = {p.source_path.name: p.scores.faces for p in photos}
    calls = (len(engine.detect_shapes), len(engine.crop_sizes))
    new_settings = AppSettings(correction_mode=CorrectionMode.AUTO_LEVEL, brightness=40)
    assert refresh_correction_scores(photos, new_settings) == len(photos)
    for p in photos:
        old, new = before[p.source_path.name], p.scores.faces
        assert (new.boxes, new.closed_eyes, new.smile, new.sharpness) == (
            old.boxes, old.closed_eyes, old.smile, old.sharpness)
    assert any(p.scores.faces.exposure != before[p.source_path.name].exposure for p in photos)
    assert (len(engine.detect_shapes), len(engine.crop_sizes)) == calls


def test_rescoring_a_person_session_never_decodes_or_detects(photos, monkeypatch):
    import myphotoworks.core.analysis_image as ai
    import myphotoworks.processing.group_runner as gr

    engine = _engine()
    session, _ = run_grouping(photos, AppSettings(), face_engine_factory=lambda: engine)
    calls = (len(engine.detect_shapes), len(engine.crop_sizes))

    def boom(*a, **k):
        raise AssertionError("rescore must work from cached scores")

    monkeypatch.setattr(gr, "analyze_photo", boom)
    monkeypatch.setattr(ai, "load_analysis_image", boom)
    session.rescore(0.6)
    session.rescore(1.5)
    assert session.group_count() == 4
    assert (len(engine.detect_shapes), len(engine.crop_sizes)) == calls
