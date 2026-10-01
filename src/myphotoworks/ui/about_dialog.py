"""About dialog — copyright and version information."""
from __future__ import annotations

import sys
from importlib.metadata import PackageNotFoundError, version
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
        return base / "myphotoworks" / "resources" / "myphotoworks.png"
    return base / "resources" / "myphotoworks.png"


class AboutDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("myPhotoWorks 정보")
        self.setFixedSize(380, 390)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        layout = QVBoxLayout(self)
        layout.setSpacing(6)
        layout.setContentsMargins(28, 28, 28, 20)

        # App icon
        icon_path = _get_icon_path()
        if icon_path.exists():
            icon_label = QLabel()
            pixmap = QPixmap(str(icon_path)).scaled(
                80, 80,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            icon_label.setPixmap(pixmap)
            icon_label.setFixedSize(80, 80)
            icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(icon_label, alignment=Qt.AlignmentFlag.AlignHCenter)
            layout.addSpacing(10)

        # App name
        name_label = QLabel("myPhotoWorks")
        name_label.setObjectName("aboutTitle")  # styled in light_table.qss
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(name_label)

        # Version
        ver_label = QLabel(f"버전 {_get_version()}")
        ver_label.setObjectName("hint-label")
        ver_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(ver_label)
        layout.addSpacing(8)

        # Description
        desc_label = QLabel("사진 일괄 보정·선별 애플리케이션\n필름 레시피, 그룹 리뷰, 리사이즈")
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(desc_label)

        layout.addStretch()

        # Third-party notice (face analysis)
        notice_label = QLabel("얼굴 분석: Google MediaPipe (Apache License 2.0)")
        notice_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        notice_label.setObjectName("hint-label")
        layout.addWidget(notice_label)

        # Copyright
        copyright_label = QLabel("© 2025 euikuk-jeong. All rights reserved.")
        copyright_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        copyright_label.setObjectName("hint-label")
        layout.addWidget(copyright_label)

        # GitHub link
        link_label = QLabel(
            '<a href="https://github.com/euikuk-jeong/myPhotoWorks">'
            "github.com/euikuk-jeong/myPhotoWorks</a>"
        )
        link_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        link_label.setOpenExternalLinks(True)
        layout.addWidget(link_label)

        layout.addSpacing(8)

        # OK button
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.setCenterButtons(True)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)
