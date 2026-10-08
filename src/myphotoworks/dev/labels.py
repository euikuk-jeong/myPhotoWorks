"""Export the user's adoption decisions as evaluation labels (developer feature)."""
from __future__ import annotations

import json
import os
from pathlib import Path

from myphotoworks.core.explain import explain_photo, subject_overlay
from myphotoworks.models.group_session import GroupSession
from myphotoworks.models.photo_item import PhotoItem
from myphotoworks.utils.exif_reader import read_af_debug

DEV_ENV = "MYPHOTOWORKS_DEV"


def is_dev_mode() -> bool:
    return os.environ.get(DEV_ENV, "").strip().lower() in ("1", "true", "yes", "on")


def _round(value, digits: int = 3):
    return None if value is None else round(float(value), digits)


def photo_analysis(session: GroupSession, photo: PhotoItem) -> dict:
    """What the algorithm measured for one photo, for reading an export without the photos:
    adoption, the sentence and trace the review window shows, subject area, faces, tilt and the
    AF debug (raw Fujifilm values and why an AF point is or is not used)."""
    info: dict = {
        "adopted": photo.is_adopted,
        "recommended": photo.is_recommended,
        "reason": photo.reason,
        "facts": list(photo.facts),
        "af": read_af_debug(photo.source_path),
        "scored": photo.scores is not None,
    }
    s = photo.scores
    if s is None:
        return info
    scored = [p for p in session.group(photo.group_id).photos if p.scores is not None]
    explanation = explain_photo(
        [p.scores for p in scored], next(i for i, p in enumerate(scored) if p is photo),
        [p.source_path.stem for p in scored], session.sensitivity)
    info["why"] = explanation.headline
    info["trace"] = list(explanation.trace_lines)
    info["subject"] = {
        "source": s.subject_source,
        "sharpness": _round(s.subject_sharpness, 1),
        "exposure": _round(s.subject_exposure, 1),
        "color": _round(s.color, 1),
        "motion_ratio": _round(s.motion_ratio),
    }
    info["tilt"] = _round(s.tilt, 2)
    info["boxes"] = [{"source": b.source, "label": b.label,
                      "rect": [round(v, 3) for v in b.rect]} for b in subject_overlay(s)]
    faces = s.faces
    info["faces"] = None if faces is None else {
        "count": faces.count, "closed_eyes": faces.closed_eyes, "smile": _round(faces.smile),
        "sharpness": _round(faces.sharpness, 1), "exposure": _round(faces.exposure, 1),
        "cut": faces.cut,
    }
    return info


def write_labels(session: GroupSession, path: Path, root: Path | None = None) -> dict:
    label = session.to_label_dict(root, photo_info=lambda p: photo_analysis(session, p))
    Path(path).write_text(json.dumps(label, ensure_ascii=False, indent=2), encoding="utf-8")
    return label
