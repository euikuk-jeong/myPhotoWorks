"""Faces for the person chain (recommendation v2, stage 2).

Two layers. The judgement rules (``eye_closed``, ``smile_value``, ``select_main_faces``,
``summarize_faces``) are pure functions on blendshape dicts and boxes, so they need no model.
``MediaPipeFaceEngine`` is the only code that touches MediaPipe; everything else talks to the
two-method ``FaceEngine`` protocol, and ``get_face_engine`` returns ``None`` instead of raising
when faces cannot be analysed (no mediapipe, no model, unsupported CPU, switched off).
"""
from __future__ import annotations

import logging
import os
import sys
import threading
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np

logger = logging.getLogger(__name__)

Box = tuple[int, int, int, int]      # x0, y0, x1, y1 in pixels, x1 / y1 exclusive

# ---- tunables (plan §7; tuned with CEW / GENKI and the evaluation script) -------------------
EYE_CLOSED_TH = 0.5            # max(eyeBlinkLeft, eyeBlinkRight) at or above this: eyes closed
MAIN_FACE_REL_AREA = 0.25      # a face is a main person from this share of the largest face's area
MIN_FACE_WIDTH_RATIO = 0.03    # largest face narrower than this share of the photo: no portrait

MODEL_DIR = Path(__file__).resolve().parent.parent / "models_ml"
DETECTOR_MODEL = "blaze_face_short_range.tflite"
LANDMARKER_MODEL = "face_landmarker.task"
DISABLE_ENV = "MYPHOTOWORKS_DISABLE_FACES"      # any non-empty value except 0: no face analysis
_LANDMARKER_FACES = 3          # faces the landmarker may return for one crop (neighbours included)


# ---- judgement rules (pure) -----------------------------------------------------------------


def eye_closed(blendshapes: Mapping[str, float], threshold: float = EYE_CLOSED_TH) -> bool:
    """True when either eye is closed (a wink or a half-hidden eye counts). Missing entries
    read as open."""
    blink = max(blendshapes.get("eyeBlinkLeft", 0.0), blendshapes.get("eyeBlinkRight", 0.0))
    return blink >= threshold


def smile_value(blendshapes: Mapping[str, float]) -> float:
    """0..1 smile: mean of both mouth corners; missing entries read as neutral."""
    return (blendshapes.get("mouthSmileLeft", 0.0) + blendshapes.get("mouthSmileRight", 0.0)) / 2


def _area(box: Box) -> int:
    return max(0, box[2] - box[0]) * max(0, box[3] - box[1])


def select_main_faces(boxes: Sequence[Box], image_size: tuple[int, int]) -> list[Box]:
    """Faces worth analysing, in detector order: at least ``MAIN_FACE_REL_AREA`` of the largest
    face's area. When even the largest face is narrower than ``MIN_FACE_WIDTH_RATIO`` of the
    photo the photo has no portrait and the list is empty."""
    if not boxes:
        return []
    largest = max(boxes, key=_area)
    if largest[2] - largest[0] < MIN_FACE_WIDTH_RATIO * image_size[0]:
        return []
    limit = MAIN_FACE_REL_AREA * _area(largest)
    return [b for b in boxes if _area(b) >= limit]


def area_weights(boxes: Sequence[Box]) -> list[float]:
    """Face-size weights for averaging (box areas; equal weights when all boxes are empty)."""
    areas = [float(_area(b)) for b in boxes]
    return areas if sum(areas) > 0 else [1.0] * len(areas)


def weighted_mean(values: Sequence[float], boxes: Sequence[Box]) -> float:
    weights = area_weights(boxes)
    return sum(v * w for v, w in zip(values, weights, strict=True)) / sum(weights)


@dataclass(frozen=True)
class FaceMeasure:
    """One analysed main face. ``sharpness`` / ``exposure`` are 0..100, ``smile`` 0..1."""

    bbox: Box
    closed: bool
    smile: float
    sharpness: float
    exposure: float


@dataclass(frozen=True)
class FaceSummary:
    """The main faces of one photo; boxes are in the pixel grid of the analysis copy (the one
    ``QualityScores.subject_bbox`` uses), so a correction change can re-measure the exposure."""

    boxes: tuple[Box, ...]
    closed_eyes: int            # main people with closed eyes
    smile: float                # 0..1, face-size weighted
    sharpness: float            # 0..100, face-size weighted
    exposure: float             # 0..100, face-size weighted
    cut: int = 0                # main faces touching the frame edge (stage 3, composition)

    @property
    def count(self) -> int:
        return len(self.boxes)


def summarize_faces(measures: Sequence[FaceMeasure]) -> FaceSummary:
    """One photo's numbers: an integer count of closed eyes, face-size weighted means."""
    boxes = [m.bbox for m in measures]
    return FaceSummary(
        boxes=tuple(boxes),
        closed_eyes=sum(1 for m in measures if m.closed),
        smile=weighted_mean([m.smile for m in measures], boxes),
        sharpness=weighted_mean([m.sharpness for m in measures], boxes),
        exposure=weighted_mean([m.exposure for m in measures], boxes),
    )


# ---- engine ---------------------------------------------------------------------------------


class FaceEngine(Protocol):
    """What the pipeline needs from a face model. Both calls take uint8 RGB arrays (H, W, 3)."""

    def detect(self, rgb: np.ndarray) -> list[Box]:
        """Face boxes in the pixels of ``rgb``. An engine may also offer
        ``detect_scored(rgb) -> [(box, score)]``, which ``core/face_detect`` prefers: it keeps
        confident faces and finds small ones in tiles."""

    def blendshapes(
        self, rgb: np.ndarray, face_box: Box | None = None
    ) -> dict[str, float] | None:
        """Blendshape scores of the face in a face crop, ``None`` when the model sees no face.
        ``face_box`` is where the detected face is inside ``rgb`` (``None``: the crop centre);
        with a neighbour in the crop it tells which face is meant."""


class MediaPipeFaceEngine:
    """MediaPipe Tasks: BlazeFace detector + Face Landmarker (blendshapes). Models are read as
    bytes so non-ASCII install paths work. Calls are serialised; the instance is reused."""

    def __init__(self, model_dir: Path) -> None:
        import mediapipe as mp
        from mediapipe.tasks.python import BaseOptions, vision

        self._mp = mp
        self._lock = threading.Lock()
        self._detector = vision.FaceDetector.create_from_options(vision.FaceDetectorOptions(
            base_options=BaseOptions(
                model_asset_buffer=(model_dir / DETECTOR_MODEL).read_bytes())))
        self._landmarker = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(
            base_options=BaseOptions(
                model_asset_buffer=(model_dir / LANDMARKER_MODEL).read_bytes()),
            num_faces=_LANDMARKER_FACES, output_face_blendshapes=True))

    def _image(self, rgb: np.ndarray):
        return self._mp.Image(image_format=self._mp.ImageFormat.SRGB,
                              data=np.ascontiguousarray(rgb))

    def detect_scored(self, rgb: np.ndarray) -> list[tuple[Box, float]]:
        """Face boxes with the detector's score (0..1); ``core/face_detect`` filters on it."""
        with self._lock:
            result = self._detector.detect(self._image(rgb))
        found = []
        for d in result.detections:
            b = d.bounding_box
            score = d.categories[0].score if d.categories else 0.0
            found.append(((max(0, b.origin_x), max(0, b.origin_y),
                           b.origin_x + b.width, b.origin_y + b.height), float(score)))
        return found

    def detect(self, rgb: np.ndarray) -> list[Box]:
        return [box for box, _ in self.detect_scored(rgb)]

    def blendshapes(
        self, rgb: np.ndarray, face_box: Box | None = None
    ) -> dict[str, float] | None:
        with self._lock:
            result = self._landmarker.detect(self._image(rgb))
        if not result.face_blendshapes:
            return None
        k = self._nearest_to_centre(result, self._face_target(face_box, rgb.shape))
        return {c.category_name: c.score for c in result.face_blendshapes[k]}

    @staticmethod
    def _face_target(face_box: Box | None, shape: tuple[int, ...]) -> tuple[float, float]:
        """Centre of ``face_box`` as shares of an image of ``shape`` (height, width, ...); the
        image centre when the box is unknown."""
        if face_box is None:
            return 0.5, 0.5
        h, w = shape[0], shape[1]
        return (face_box[0] + face_box[2]) / 2 / w, (face_box[1] + face_box[3]) / 2 / h

    @staticmethod
    def _nearest_to_centre(result, target: tuple[float, float] = (0.5, 0.5)) -> int:
        """Index of the landmarker face whose landmarks sit closest to ``target`` (shares of the
        crop): the detected face, even when a neighbour inside the crop margin is nearer to the
        crop centre."""
        n = len(result.face_blendshapes)
        marks = getattr(result, "face_landmarks", None)
        if n == 1 or not marks or len(marks) != n:
            return 0

        def off_target(i: int) -> float:
            xs = [p.x for p in marks[i]]
            ys = [p.y for p in marks[i]]
            return (sum(xs) / len(xs) - target[0]) ** 2 + (sum(ys) / len(ys) - target[1]) ** 2

        return min(range(n), key=off_target)


def _cpu_has_avx() -> bool:
    """MediaPipe's native library aborts the whole process on a CPU without AVX (no exception
    to catch), so look before loading. Unknown platforms and unreadable info count as "yes"."""
    try:
        if sys.platform == "win32":
            import ctypes

            return bool(ctypes.windll.kernel32.IsProcessorFeaturePresent(39))  # PF_AVX
        if sys.platform.startswith("linux"):
            for line in Path("/proc/cpuinfo").read_text().splitlines():
                if line.startswith("flags"):
                    return "avx" in line.split()
    except Exception:
        pass
    return True


def _create_engine(model_dir: Path) -> FaceEngine | None:
    missing = [n for n in (DETECTOR_MODEL, LANDMARKER_MODEL) if not (model_dir / n).is_file()]
    if missing:
        logger.warning("face models missing in %s: %s - faces are not analysed",
                       model_dir, ", ".join(missing))
        return None
    if not _cpu_has_avx():
        logger.warning("CPU without AVX: MediaPipe cannot run - faces are not analysed")
        return None
    try:
        return MediaPipeFaceEngine(model_dir)
    except Exception as e:  # ImportError, OSError (missing system library), bad model ...
        logger.warning("face engine unavailable (%s: %s) - faces are not analysed",
                       type(e).__name__, e)
        return None


_default_lock = threading.Lock()
_default: list[FaceEngine | None] = []      # [] = not tried yet; [engine or None] = result


def get_face_engine(model_dir: Path | None = None) -> FaceEngine | None:
    """The face engine, or ``None`` when faces cannot be analysed - never raises.

    Without ``model_dir`` this is the shared, lazily built engine for the packaged models (and
    ``MYPHOTOWORKS_DISABLE_FACES`` switches it off); a failed attempt is remembered. With
    ``model_dir`` a fresh engine is built from that folder.
    """
    if model_dir is not None:
        return _create_engine(Path(model_dir))
    if os.environ.get(DISABLE_ENV, "0") not in ("", "0"):
        return None
    with _default_lock:
        if not _default:
            _default.append(_create_engine(MODEL_DIR))
        return _default[0]
