"""Recommendation v2, stage 2 — shipping the face models (plan §5-1, §1 rule 9).

Runtime files must live inside ``src/myphotoworks/`` and be listed in the ``datas`` of
``myphotoworks.spec`` (the v1.3.0 recipe bug: files outside the package are missing from the wheel
and the exe). Plain file / text checks only: nothing here imports mediapipe or loads a model.

    src/myphotoworks/models_ml/blaze_face_short_range.tflite    Face Detector (short-range)
    src/myphotoworks/models_ml/face_landmarker.task             Face Landmarker with blendshapes
    core.faces.MODEL_DIR                                        that directory
    core.faces.DETECTOR_MODEL / LANDMARKER_MODEL                the two file names
"""
import os
import tomllib
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PyQt6.QtWidgets import QLabel  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / "src" / "myphotoworks" / "models_ml"
MODEL_FILES = ("blaze_face_short_range.tflite", "face_landmarker.task")


def test_mediapipe_is_a_declared_dependency():
    deps = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"][
        "dependencies"]
    assert any(d.lower().replace("_", "-").startswith("mediapipe") for d in deps)


@pytest.mark.parametrize("name", MODEL_FILES)
def test_model_file_is_inside_the_package_and_not_empty(name):
    path = MODEL_DIR / name
    assert path.is_file() and path.stat().st_size > 10_000


def test_faces_module_points_at_the_package_model_directory():
    from myphotoworks.core import faces

    assert Path(faces.MODEL_DIR).resolve() == MODEL_DIR.resolve()
    assert (faces.DETECTOR_MODEL, faces.LANDMARKER_MODEL) == MODEL_FILES


def test_pyinstaller_spec_ships_the_models_and_mediapipe():
    spec = (ROOT / "myphotoworks.spec").read_text(encoding="utf-8")
    assert "models_ml" in spec          # datas: the model files
    assert "mediapipe" in spec          # hidden import / collected data and binaries


def test_about_dialog_credits_mediapipe_and_its_license(qtbot):
    from myphotoworks.ui.about_dialog import AboutDialog

    dlg = AboutDialog()
    qtbot.addWidget(dlg)
    text = " ".join(lbl.text() for lbl in dlg.findChildren(QLabel))
    assert "MediaPipe" in text and "Apache" in text
