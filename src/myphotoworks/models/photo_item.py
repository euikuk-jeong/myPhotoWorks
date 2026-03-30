from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PIL import Image


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
