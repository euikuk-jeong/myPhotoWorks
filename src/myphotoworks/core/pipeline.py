"""Per-photo analysis: one small decode yields signature, scores and capture time."""
from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
from PIL import Image

from myphotoworks.core.analysis_image import (
    DEFAULT_LONG_SIDE,
    face_crops,
    load_analysis_image,
)
from myphotoworks.core.face_detect import detect_faces
from myphotoworks.core.faces import Box, FaceEngine, select_main_faces
from myphotoworks.core.grouping import ExifHints
from myphotoworks.core.scoring import QualityScores, score_images
from myphotoworks.core.similarity import Signature, compute_signature

logger = logging.getLogger(__name__)


@dataclass
class Analysis:
    signature: Signature
    scores: QualityScores
    taken: datetime | None
    hints: ExifHints | None = None


def analyze_faces(
    path: Path, raw: Image.Image, engine: FaceEngine | None
) -> list[tuple[Box, Mapping[str, float] | None]]:
    """Main faces of a photo as ``(box in the pixels of raw, blendshapes or None)``.

    Two stages: the detector looks at the small analysis copy and, when that is not conclusive,
    at tiles of a larger decode (``core/face_detect``: small faces, no false ones); only photos
    with a main face cost a second decode of the faces from the original for the landmarker,
    which is told where each face is inside its crop. A detector or decode failure means "no
    faces" for this photo (logged); a landmarker failure only leaves that face's blendshapes
    unknown (``None``: eyes open, neutral) - the detected face stays. The analysis itself never
    fails because of faces.
    """
    if engine is None:
        return []
    try:
        boxes = detect_faces(path, raw, engine)
        main = select_main_faces(boxes, raw.size)
        crops = face_crops(path, main, raw.size)            # one decode for all faces
    except Exception as e:
        logger.warning("face analysis failed for %s: %s", path, e)
        return []
    faces = []
    failed = 0
    for box, crop in zip(main, crops, strict=True):
        try:
            shapes = engine.blendshapes(np.asarray(crop.image), crop.face_box)
        except Exception as e:
            failed += 1
            error = e
            shapes = None
        faces.append((box, shapes))
    if failed:
        logger.warning("landmarker failed for %d of %d faces of %s: %s",
                       failed, len(faces), path, error)
    return faces


def analyze_photo(
    path: Path,
    taken: datetime | None,
    hints: ExifHints | None = None,
    correct: Callable[[Image.Image], Image.Image] | None = None,
    long_side: int = DEFAULT_LONG_SIDE,
    face_engine: FaceEngine | None = None,
) -> Analysis:
    """Decode a small copy once; derive signature and quality scores.

    ``correct`` applies the user's correction settings so exposure / colour reflect the
    final result. Sharpness and the signature always use the uncorrected copy. ``face_engine``
    (optional) finds the main faces: they become the subject and fill ``scores.faces``. Without
    faces, ``hints.af_point`` (the camera's AF point) is the subject when it is known.
    """
    raw = load_analysis_image(path, long_side)
    corrected = correct(raw.copy()) if correct is not None else raw
    faces = analyze_faces(path, raw, face_engine)
    af_point = hints.af_point if hints is not None else None
    scores = score_images(raw, corrected, faces, af_point)
    return Analysis(compute_signature(raw), scores, taken, hints)
