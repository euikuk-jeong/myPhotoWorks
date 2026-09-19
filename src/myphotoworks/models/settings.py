from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from myphotoworks.core.grouping import GroupingMode


class ResizeAxis(Enum):
    LONG = "long"    # 긴 축 기준
    SHORT = "short"  # 짧은 축 기준


class OutputPathMode(Enum):
    FIRST_FILE = "first_file"  # 첫 번째 파일 기준 output 폴더
    PER_FILE = "per_file"      # 각 파일별 output 폴더
    CUSTOM = "custom"          # 직접 지정 경로


class CorrectionMode(str, Enum):
    NONE = "none"
    AUTO_LEVEL = "auto_level"
    AUTO_CONTRAST = "auto_contrast"
    AUTO_LEVEL_CONTRAST = "auto_level_contrast"
    RECIPE = "recipe"  # recipe_name 필드와 함께 사용


@dataclass
class AppSettings:
    # Effects
    correction_mode: CorrectionMode = CorrectionMode.NONE
    recipe_name: str = ""   # CorrectionMode.RECIPE 시 builtin recipe key
    brightness: int = 0     # -100 ~ +100
    contrast: int = 0       # -100 ~ +100

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

    # Lumis Flow grouping
    grouping_mode: GroupingMode = GroupingMode.AUTO
    similarity_slider: int = 50          # 0 strict .. 100 loose
    time_gap: float = 2.0                # seconds
    global_clustering: bool = False      # compare against all groups, not just neighbours
    use_exif_hints: bool = False         # focal length / lens / aperture consistency
    weight_sharpness: float = 0.5
    weight_exposure: float = 0.3
    weight_color: float = 0.2
    show_reason: bool = True
    show_score: bool = True

    def weights(self) -> tuple[float, float, float]:
        return (self.weight_sharpness, self.weight_exposure, self.weight_color)
