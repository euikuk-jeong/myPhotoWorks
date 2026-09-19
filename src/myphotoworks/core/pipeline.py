"""Per-photo analysis: one small decode yields signature, scores and capture time."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PIL import Image

from myphotoworks.core.analysis_image import DEFAULT_LONG_SIDE, load_analysis_image
from myphotoworks.core.grouping import ExifHints
from myphotoworks.core.scoring import QualityScores, score_images
from myphotoworks.core.similarity import Signature, compute_signature


@dataclass
class Analysis:
    signature: Signature
    scores: QualityScores
    taken: datetime | None
    hints: ExifHints | None = None


def analyze_photo(
    path: Path,
    taken: datetime | None,
    hints: ExifHints | None = None,
    correct: Callable[[Image.Image], Image.Image] | None = None,
    long_side: int = DEFAULT_LONG_SIDE,
) -> Analysis:
    """Decode a small copy once; derive signature and quality scores.

    ``correct`` applies the user's correction settings so exposure / colour reflect the
    final result. Sharpness and the signature always use the uncorrected copy.
    """
    raw = load_analysis_image(path, long_side)
    corrected = correct(raw.copy()) if correct is not None else raw
    return Analysis(compute_signature(raw), score_images(raw, corrected), taken, hints)
