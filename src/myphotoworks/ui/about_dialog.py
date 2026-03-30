"""About dialog — copyright and version information."""
from __future__ import annotations

import sys
from importlib.metadata import version, PackageNotFoundError
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
)


def _get_version() -> str:
    try:
        return version("myphotoworks")
    except PackageNotFoundError:
        return "0.1.0"


def _get_icon_path() -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).parent.parent))
    if hasattr(sys, "_MEIPASS"):
        return base / "myphotoworks" / "resources" / "myphotoworks.ico"
    return base / "resources" / "myphotoworks.ico"


class AboutDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("myPhotoWorks 정보")
        self.setFixedSize(360, 280)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(24, 20, 24, 16)

        # App icon
        icon_path = _get_icon_path()
        if icon_path.exists():
            icon_label = QLabel()
            pixmap = QPixmap(str(icon_path)).scaled(
                64, 64,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            icon_label.setPixmap(pixmap)
            icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(icon_label)

        # App name
        name_label = QLabel("<b style='font-size:16pt'>myPhotoWorks</b>")
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(name_label)

        # Version
        ver_label = QLabel(f"버전 {_get_version()}")
        ver_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(ver_label)

        # Description
        desc_label = QLabel("사진 일괄 처리 애플리케이션\n(리사이즈 · Auto Level · Auto Contrast)")
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(desc_label)

        layout.addStretch()

        # Copyright
        copyright_label = QLabel("© 2025 euikuk-jeong. All rights reserved.")
        copyright_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        copyright_label.setStyleSheet("color: gray; font-size: 9pt;")
        layout.addWidget(copyright_label)

        # GitHub link
        link_label = QLabel(
            '<a href="https://github.com/euikuk-jeong/myPhotoWorks">'
            "github.com/euikuk-jeong/myPhotoWorks</a>"
        )
        link_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        link_label.setOpenExternalLinks(True)
        link_label.setStyleSheet("font-size: 9pt;")
        layout.addWidget(link_label)

        layout.addSpacing(8)

        # OK button
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)
