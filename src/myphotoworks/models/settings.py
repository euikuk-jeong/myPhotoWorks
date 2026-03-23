from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class AppSettings:
    # Filter
    bw_enabled: bool = False
    level_min: int = 0
    level_max: int = 255

    # Effects
    auto_level: bool = False
    auto_contrast: bool = False
    brightness: int = 0   # -100 ~ +100
    contrast: int = 0     # -100 ~ +100

    # Sharpen / Gaussian (mutually exclusive)
    sharpen_enabled: bool = False
    sharpen_amount: float = 1.0
    gaussian_enabled: bool = False
    gaussian_radius: float = 1.0

    # Watermark
    watermark_enabled: bool = False
    watermark_text: str = ""
    watermark_use_timestamp: bool = True
    watermark_font_size: int = 24

    # Resize
    resize_enabled: bool = False
    resize_width: int = 0
    resize_height: int = 0
    resize_keep_aspect: bool = True

    # Output
    output_dir: Path = field(default_factory=lambda: Path("."))
    output_format: str = "JPEG"   # "JPEG" | "PNG"
    output_quality: int = 90
    target_ppi: int = 72
