from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class ResizeAxis(Enum):
    LONG = "long"    # 긴 축 기준
    SHORT = "short"  # 짧은 축 기준


class OutputPathMode(Enum):
    FIRST_FILE = "first_file"  # 첫 번째 파일 기준 output 폴더
    PER_FILE = "per_file"      # 각 파일별 output 폴더
    CUSTOM = "custom"          # 직접 지정 경로


@dataclass
class AppSettings:
    # Effects
    auto_level: bool = False
    auto_contrast: bool = False
    brightness: int = 0   # -100 ~ +100
    contrast: int = 0     # -100 ~ +100

    # Resize
    resize_enabled: bool = False
    resize_axis: ResizeAxis = ResizeAxis.LONG
    resize_px: int = 1920

    # Output
    output_path_mode: OutputPathMode = OutputPathMode.FIRST_FILE
    output_custom_dir: Path = field(default_factory=lambda: Path("."))
    output_prefix: str = ""
    output_suffix: str = ""
    output_quality: int = 90   # 1~100
