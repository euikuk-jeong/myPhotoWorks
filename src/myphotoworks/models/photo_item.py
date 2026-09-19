from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PIL import Image

    from myphotoworks.core.pipeline import Analysis
    from myphotoworks.core.scoring import QualityScores


class ProcessStatus(Enum):
    PENDING = auto()
    PROCESSING = auto()
    DONE = auto()
    ERROR = auto()


@dataclass
class PhotoItem:
    source_path: Path
    exif: dict = field(default_factory=dict)
    status: ProcessStatus = ProcessStatus.PENDING
    processed_image: "Image.Image | None" = None
    error_message: str = ""

    # --- Lumis Flow grouping (filled by GroupSession) ---
    group_id: int | None = None
    is_recommended: bool = False   # algorithm's pick
    is_adopted: bool = False       # user's decision (starts equal to is_recommended)
    scores: "QualityScores | None" = None
    reason: str = ""
    analysis: "Analysis | None" = None  # cached signature/scores from the last grouping run
    analysis_key: tuple | None = None   # correction settings the cached analysis was built with
