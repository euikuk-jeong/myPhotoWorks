"""Recommendation v2, stage 2 — face data inside ``QualityScores`` (plan §5-2, §4-6).

``QualityScores.faces`` is ``None`` or a ``FaceSummary``; its boxes live in the pixel grid of the
analysis copy, like ``subject_bbox``. A correction change re-measures *face exposure* from the
cached boxes (corrected copy) and keeps everything measured on the uncorrected copy: sharpness,
closed eyes, smile, boxes. No detector or decode is involved. The algorithm version is bumped
because exported labels record it.
"""
import pytest

from tests.synthetic import PATCH, backlit, face_summary, scores, to_rgb_image


def test_faces_default_to_none():
    assert scores().faces is None


def test_algorithm_version_marks_stage_two():
    from myphotoworks.core.scoring import ALGORITHM_VERSION

    assert ALGORITHM_VERSION == "v2-stage2"


def test_rescore_corrected_remeasures_face_exposure_and_keeps_the_rest():
    from myphotoworks.core.scoring import rescore_corrected

    faces = face_summary(boxes=[PATCH], closed=1, smile=0.4, sharp=77.0, exposure=5.0)
    old = scores(60, 5, 50, faces=faces, subject_bbox=PATCH, subject_source="face")
    raw = to_rgb_image(backlit(subject_mean=40.0))            # dark subject
    corrected = to_rgb_image(backlit(subject_mean=118.0))     # brightened by the correction
    new = rescore_corrected(old, raw, corrected)
    assert new.faces.exposure > 50.0
    assert new.faces.exposure == pytest.approx(new.subject_exposure, abs=1.0)   # same box
    assert (new.faces.boxes, new.faces.closed_eyes, new.faces.smile, new.faces.sharpness) == (
        faces.boxes, 1, 0.4, 77.0)


def test_rescore_corrected_leaves_a_faceless_photo_faceless():
    from myphotoworks.core.scoring import rescore_corrected

    old = scores(60, 40, 50)
    img = to_rgb_image(backlit())
    assert rescore_corrected(old, img, img).faces is None
