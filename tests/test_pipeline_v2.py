"""Recommendation v2, stage 1 — analysis pipeline and group runner (plan §4-6).

``analyze_photo`` fills the subject-based ``QualityScores``; ``run_grouping`` passes
``AppSettings.recommend_sensitivity`` to the session; ``refresh_correction_scores`` keeps the
decode-time values (subject sharpness / source / motion) and recomputes only subject exposure
and colour on the corrected image; re-recommending needs no decoding.
"""
from datetime import datetime

import numpy as np
import piexif
import pytest
from PIL import Image, ImageFilter

from myphotoworks.models.photo_item import PhotoItem
from myphotoworks.models.settings import AppSettings, CorrectionMode
from myphotoworks.processing.group_runner import run_grouping
from tests.synthetic import shallow_dof, texture, to_rgb_image
from tests.test_grouping import scene

SOURCES = {"sharpest", "center"}


def detailed_scene(seed: int) -> Image.Image:
    """``scene`` plus fine texture: the smooth block scenes have no detail at all, so no
    sharpness metric (nor a person) could tell them from their blurred copies."""
    base = np.asarray(scene(seed), dtype=np.float64)
    detail = texture(base.shape[0], base.shape[1], seed=seed + 100, cell=2)
    mixed = np.clip(base + 0.3 * (detail[..., None] - 127.5), 0, 255)
    return Image.fromarray(mixed.astype("uint8"))


def _save(path, seed, taken=None, blur=0.0):
    img = detailed_scene(seed)
    if blur:
        img = img.filter(ImageFilter.GaussianBlur(blur))
    kwargs = {}
    if taken:
        kwargs["exif"] = piexif.dump({"Exif": {piexif.ExifIFD.DateTimeOriginal: taken.encode()}})
    img.save(path, "JPEG", quality=95, **kwargs)
    return PhotoItem(path)


@pytest.fixture
def photos(tmp_path):
    return [
        _save(tmp_path / "a1.jpg", 1, "2026:01:01 12:00:00"),
        _save(tmp_path / "a2.jpg", 1, "2026:01:01 12:00:01", blur=3.0),
        _save(tmp_path / "b1.jpg", 2, "2026:01:01 12:05:00"),
        _save(tmp_path / "b2.jpg", 2, "2026:01:01 12:05:01", blur=0.8),
        _save(tmp_path / "c1.jpg", 3, "2026:01:01 12:10:00"),
        _save(tmp_path / "d1.jpg", 4, "2026:01:01 12:20:00"),
    ]


def test_analyze_photo_fills_subject_scores(tmp_path):
    from myphotoworks.core.pipeline import analyze_photo

    path = tmp_path / "shallow.jpg"
    to_rgb_image(shallow_dof(seed=12)).save(path, "JPEG", quality=95)
    a = analyze_photo(path, datetime(2026, 1, 1))
    s = a.scores
    assert s.subject_source == "sharpest"
    assert 0 <= s.subject_sharpness <= 100 and 0 <= s.subject_exposure <= 100
    assert 0 <= s.color <= 100 and 0.0 <= s.motion_ratio <= 1.0


def test_run_grouping_scores_and_badges_use_the_new_chain(photos):
    session, _ = run_grouping(photos, AppSettings())
    a1, a2 = photos[0], photos[1]
    assert a1.is_recommended and not a2.is_recommended          # a2 is blurred
    assert all(p.scores.subject_source in SOURCES for p in photos)
    assert a1.reason.startswith("주제 선명도 우세")
    assert "흐림" in a2.reason
    assert photos[4].reason == "단독 사진" and photos[5].reason == "단독 사진"
    assert session.adopted_count() == 4


def test_run_grouping_hands_the_sensitivity_to_the_session(photos):
    session, _ = run_grouping(photos, AppSettings(recommend_sensitivity=0.6))
    assert session.to_label_dict()["sensitivity"] == 0.6


def test_refresh_correction_scores_keeps_decode_time_values(photos):
    from myphotoworks.processing.group_runner import correction_key, refresh_correction_scores

    session, _ = run_grouping(photos, AppSettings())
    before = {p.source_path.name: (p.scores.subject_sharpness, p.scores.subject_exposure,
                                   p.scores.subject_source, p.scores.motion_ratio)
              for p in photos}
    groups_before = [[p.source_path.name for p in g.photos] for g in session.groups()]
    new_settings = AppSettings(correction_mode=CorrectionMode.AUTO_LEVEL, brightness=40)
    assert refresh_correction_scores(photos, new_settings) == len(photos)
    assert all(p.analysis_key == correction_key(new_settings) for p in photos)
    assert any(p.scores.subject_exposure != before[p.source_path.name][1] for p in photos)
    for p in photos:
        sharp, _exp, source, motion = before[p.source_path.name]
        assert (p.scores.subject_sharpness, p.scores.subject_source,
                p.scores.motion_ratio) == (sharp, source, motion)
    assert [[p.source_path.name for p in g.photos] for g in session.groups()] == groups_before
    assert refresh_correction_scores(photos, new_settings) == 0


def test_rescoring_a_session_never_decodes(photos, monkeypatch):
    import myphotoworks.core.analysis_image as ai
    import myphotoworks.processing.group_runner as gr

    session, _ = run_grouping(photos, AppSettings())

    def boom(*a, **k):
        raise AssertionError("rescore must work from cached scores")

    monkeypatch.setattr(gr, "analyze_photo", boom)
    monkeypatch.setattr(ai, "load_analysis_image", boom)
    session.rescore(0.6)
    session.rescore(1.5)
    assert session.group_count() == 4
