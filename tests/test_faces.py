"""Recommendation v2, stage 2 — face judgement rules (plan §5-3), no model needed.

New ``core/faces.py`` API under test:

    EYE_CLOSED_TH, MAIN_FACE_REL_AREA, MIN_FACE_WIDTH_RATIO     named tunables (plan §7)
    DETECTOR_MODEL, LANDMARKER_MODEL                            model file names in ``MODEL_DIR``
    eye_closed(blendshapes, threshold=EYE_CLOSED_TH) -> bool    one closed eye is enough
    smile_value(blendshapes) -> float                           mean of mouthSmileLeft / Right
    select_main_faces(boxes, image_size) -> list[box]           faces to analyse, detector order
    FaceMeasure(bbox, closed, smile, sharpness, exposure)       one analysed face
    FaceSummary(boxes, closed_eyes, smile, sharpness, exposure) one photo; ``.count`` = len(boxes)
    summarize_faces(measures) -> FaceSummary                    integer closed count, weighted means
    get_face_engine(model_dir=None) -> engine | None            None (never an exception) when
                                                                mediapipe / model files are unusable

Boxes are ``(x0, y0, x1, y1)`` in analysis-copy pixels, ``image_size`` is ``(w, h)`` of that copy.
Threshold values are tuned later (CEW / GENKI), so inputs are built relative to the constants.
"""
import logging
import sys
from dataclasses import FrozenInstanceError

import pytest

from tests.synthetic import blend, box_with_area, face_summary

# ---- eyes -----------------------------------------------------------------------------------


def test_both_eyes_above_the_threshold_are_closed_and_below_are_open():
    from myphotoworks.core.faces import EYE_CLOSED_TH, eye_closed

    assert eye_closed(blend(EYE_CLOSED_TH + 0.1, EYE_CLOSED_TH + 0.1)) is True
    assert eye_closed(blend(EYE_CLOSED_TH - 0.1, EYE_CLOSED_TH - 0.1)) is False


def test_one_closed_eye_counts_as_closed():
    """Plan §5-3: initial rule is ``max`` of the two eyes (a wink or a half-hidden eye counts)."""
    from myphotoworks.core.faces import EYE_CLOSED_TH, eye_closed

    assert eye_closed(blend(blink_l=EYE_CLOSED_TH + 0.2, blink_r=0.0)) is True
    assert eye_closed(blend(blink_l=0.0, blink_r=EYE_CLOSED_TH + 0.2)) is True


def test_the_threshold_itself_is_closed_and_can_be_overridden():
    from myphotoworks.core.faces import EYE_CLOSED_TH, eye_closed

    assert eye_closed(blend(EYE_CLOSED_TH, EYE_CLOSED_TH)) is True      # >= threshold
    assert eye_closed(blend(0.5, 0.5), threshold=0.9) is False
    assert eye_closed(blend(0.5, 0.5), threshold=0.4) is True


def test_missing_blendshape_entries_read_as_open_eyes():
    from myphotoworks.core.faces import eye_closed

    assert eye_closed({}) is False


# ---- smile ----------------------------------------------------------------------------------


def test_smile_is_the_mean_of_the_two_mouth_corners():
    from myphotoworks.core.faces import smile_value

    assert smile_value(blend(smile_l=0.8, smile_r=0.4)) == pytest.approx(0.6)
    assert smile_value(blend()) == 0.0


def test_missing_smile_entries_read_as_a_neutral_face():
    from myphotoworks.core.faces import smile_value

    assert smile_value({}) == 0.0


# ---- main faces (§5-3: >= 25 % of the largest face; < 3 % of the photo width ignored) ---------

SIZE = (1000, 800)


def test_faces_below_the_relative_area_limit_are_not_main_faces():
    from myphotoworks.core.faces import MAIN_FACE_REL_AREA, select_main_faces

    big = box_with_area(40_000)
    mid = box_with_area(40_000 * MAIN_FACE_REL_AREA * 1.2, x0=300)
    small = box_with_area(40_000 * MAIN_FACE_REL_AREA * 0.6, x0=600)
    assert select_main_faces([big, mid, small], SIZE) == [big, mid]


def test_main_faces_keep_the_detector_order():
    from myphotoworks.core.faces import select_main_faces

    a, b = box_with_area(10_000, x0=0), box_with_area(40_000, x0=300)   # b is the larger one
    assert select_main_faces([a, b], SIZE) == [a, b]


def test_the_relative_limit_is_measured_against_the_largest_face_of_that_photo():
    from myphotoworks.core.faces import select_main_faces

    only = box_with_area(10_000)                       # alone: it is its own largest face
    assert select_main_faces([only], SIZE) == [only]


def test_no_detection_gives_no_main_faces():
    from myphotoworks.core.faces import select_main_faces

    assert select_main_faces([], SIZE) == []


def test_a_photo_whose_largest_face_is_under_the_width_limit_has_no_faces():
    """Plan Q13: tiny faces in a landscape do not make it a portrait."""
    from myphotoworks.core.faces import MIN_FACE_WIDTH_RATIO, select_main_faces

    w_small, w_ok = (round(SIZE[0] * MIN_FACE_WIDTH_RATIO * k) for k in (0.8, 1.2))
    too_small, big_enough = (0, 0, w_small, w_small), (0, 0, w_ok, w_ok)
    assert select_main_faces([too_small], SIZE) == []
    assert select_main_faces([big_enough], SIZE) == [big_enough]


# ---- summary of one photo -------------------------------------------------------------------


def _measure(bbox, closed=False, smile=0.0, sharpness=70.0, exposure=70.0):
    from myphotoworks.core.faces import FaceMeasure

    return FaceMeasure(bbox, closed, smile, sharpness, exposure)


def test_closed_eyes_is_an_integer_count_of_closed_faces():
    from myphotoworks.core.faces import summarize_faces

    box = box_with_area(10_000)
    s = summarize_faces([_measure(box, closed=True), _measure(box, closed=False),
                         _measure(box, closed=True)])
    assert s.closed_eyes == 2 and isinstance(s.closed_eyes, int)
    assert s.count == 3


def test_smile_sharpness_and_exposure_are_weighted_by_face_area():
    from myphotoworks.core.faces import summarize_faces

    big, small = box_with_area(30_000), box_with_area(10_000, x0=500)   # 3 : 1
    s = summarize_faces([_measure(big, smile=0.8, sharpness=80, exposure=60),
                         _measure(small, smile=0.0, sharpness=40, exposure=20)])
    assert s.smile == pytest.approx(0.6, abs=0.01)
    assert s.sharpness == pytest.approx(70, abs=0.5)
    assert s.exposure == pytest.approx(50, abs=0.5)


def test_summary_of_a_single_face_passes_the_values_through_and_keeps_the_boxes():
    from myphotoworks.core.faces import summarize_faces

    box = (10, 20, 110, 140)
    s = summarize_faces([_measure(box, closed=True, smile=0.3, sharpness=55, exposure=65)])
    assert s.boxes == (box,)
    assert (s.closed_eyes, s.smile, s.sharpness, s.exposure) == (1, 0.3, 55, 65)


def test_face_summary_is_an_immutable_value_with_a_count():
    s = face_summary(n=3, closed=1)
    assert s.count == 3
    with pytest.raises(FrozenInstanceError):
        s.closed_eyes = 0


# ---- engine factory: never raises, returns None when it cannot work -------------------------


@pytest.mark.parametrize("value", ["1", "true"])
def test_the_default_engine_can_be_switched_off_by_the_environment(monkeypatch, value):
    """``MYPHOTOWORKS_DISABLE_FACES`` (set for the whole test suite by ``tests/conftest.py``):
    no model is loaded; an explicit ``model_dir`` is not affected."""
    from myphotoworks.core.faces import DISABLE_ENV, get_face_engine

    monkeypatch.setenv(DISABLE_ENV, value)
    assert get_face_engine() is None


def test_missing_model_files_give_no_engine_and_a_log_entry(tmp_path, caplog):
    from myphotoworks.core.faces import get_face_engine

    with caplog.at_level(logging.WARNING):
        assert get_face_engine(model_dir=tmp_path) is None
    assert caplog.records


def test_missing_mediapipe_gives_no_engine(tmp_path, monkeypatch):
    from myphotoworks.core.faces import DETECTOR_MODEL, LANDMARKER_MODEL, get_face_engine

    (tmp_path / DETECTOR_MODEL).write_bytes(b"x")
    (tmp_path / LANDMARKER_MODEL).write_bytes(b"x")
    monkeypatch.setitem(sys.modules, "mediapipe", None)       # `import mediapipe` -> ImportError
    assert get_face_engine(model_dir=tmp_path) is None


def test_corrupt_model_files_give_no_engine(tmp_path):
    from myphotoworks.core.faces import DETECTOR_MODEL, LANDMARKER_MODEL, get_face_engine

    (tmp_path / DETECTOR_MODEL).write_bytes(b"not a model")
    (tmp_path / LANDMARKER_MODEL).write_bytes(b"not a model")
    assert get_face_engine(model_dir=tmp_path) is None


# ---- landmarker result with neighbours in the crop ------------------------------------------


def test_the_landmarker_face_closest_to_the_crop_centre_is_the_one_measured():
    """The crop is centred on the detected face; a neighbour inside its margin must not lend
    its blendshapes (the landmarker may return several faces)."""
    from types import SimpleNamespace as NS

    from myphotoworks.core.faces import MediaPipeFaceEngine

    def face(cx, cy):
        return [NS(x=cx - 0.05, y=cy), NS(x=cx + 0.05, y=cy)]

    pick = MediaPipeFaceEngine._nearest_to_centre
    three = NS(face_blendshapes=[[], [], []],
               face_landmarks=[face(0.2, 0.5), face(0.55, 0.5), face(0.9, 0.5)])
    assert pick(three) == 1
    assert pick(NS(face_blendshapes=[[]], face_landmarks=[face(0.1, 0.1)])) == 0
    assert pick(NS(face_blendshapes=[[], []], face_landmarks=[])) == 0      # no landmarks: first
