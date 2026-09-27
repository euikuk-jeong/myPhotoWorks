"""ExifPanel — frameless, semi-transparent overlay listing a photo's EXIF, grouped.

It floats above the preview window (drag it by its header, close with × or Esc) so the
photo underneath stays visible.
"""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QPoint, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QPainter, QPen
from PyQt6.QtWidgets import (
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from myphotoworks.ui.styles import tokens
from myphotoworks.utils.exif_reader import read_exif

PANEL_ALPHA = 235   # ~92% opaque: the photo shows faintly through
HEADER_DRAG_H = 44  # top strip that moves the overlay


def _fmt_date(raw: str) -> str:
    return raw.replace(":", "/", 2) if raw else ""


Rows = list[tuple[str, str]]


def exif_groups(exif: dict, index: int = 0, total: int = 0) -> list[tuple[str, Rows]]:
    """EXIF rows grouped for display; empty values and then empty groups are dropped."""
    groups = [
        ("파일", [
            ("번호", f"{index:,} / {total:,}" if index > 0 else ""),
            ("파일 크기", exif.get("file_size", "")),
            ("파일 날짜", _fmt_date(exif.get("file_date", ""))),
            ("해상도", exif.get("size", "")),
        ]),
        ("카메라", [
            ("제조사", exif.get("make", "")),
            ("모델", exif.get("model", "")),
            ("소프트웨어", exif.get("software", "")),
        ]),
        ("촬영 설정", [
            ("촬영 날짜", _fmt_date(exif.get("date", ""))),
            ("초점 거리", exif.get("focal_length", "")),
            ("셔터 속도", exif.get("shutter", "")),
            ("조리개", exif.get("aperture", "")),
            ("ISO", exif.get("iso", "")),
            ("노출 보정", exif.get("exposure_bias", "")),
            ("측광 모드", exif.get("metering_mode", "")),
            ("프로그램 모드", exif.get("program_mode", "")),
            ("플래시", exif.get("flash", "")),
            ("방향", exif.get("orientation", "")),
        ]),
        ("코멘트", [("코멘트", exif.get("comment", ""))]),
    ]
    out = []
    for name, rows in groups:
        kept = [(k, str(v)) for k, v in rows if v not in ("", None)]
        if kept:
            out.append((name, kept))
    return out


class ExifPanel(QDialog):
    """Non-modal overlay. ``closed`` fires when the user dismisses it (× / Esc)."""

    closed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            parent,
            Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowTitle("EXIF 정보")
        self.resize(340, 500)
        self._drag_from: QPoint | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 12, 12, 16)
        root.setSpacing(4)

        header = QHBoxLayout()
        title = QLabel("EXIF 정보")
        title.setObjectName("viewTitle")
        header.addWidget(title)
        header.addStretch()
        close_btn = QToolButton()
        close_btn.setObjectName("exifClose")
        close_btn.setText("×")
        close_btn.setToolTip("닫기 (Esc)")
        close_btn.clicked.connect(self.reject)
        header.addWidget(close_btn)
        root.addLayout(header)

        self._file_label = QLabel()
        self._file_label.setObjectName("scoreFile")
        root.addWidget(self._file_label)
        root.addSpacing(6)

        self._scroll = QScrollArea()
        self._scroll.setObjectName("exifScroll")
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        root.addWidget(self._scroll, 1)

    # ------------------------------------------------------------------ content

    def update_photo(self, path: Path, index: int = 0, total: int = 0) -> None:
        """Load EXIF from *path* and rebuild the grouped list.

        index : 1-based current photo index (0 = don't show 번호)
        total : total photo count
        """
        exif = read_exif(path)
        self._file_label.setText(exif.get("filename") or path.name)

        body = QWidget()
        body.setObjectName("exifBody")
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 6, 0)
        layout.setSpacing(4)
        for name, rows in exif_groups(exif, index, total):
            heading = QLabel(name)
            heading.setObjectName("sectionTitle")
            layout.addSpacing(8)
            layout.addWidget(heading)
            grid = QGridLayout()
            grid.setHorizontalSpacing(14)
            grid.setVerticalSpacing(5)
            grid.setColumnStretch(1, 1)
            for r, (key, value) in enumerate(rows):
                k = QLabel(key)
                k.setObjectName("hint-label")
                v = QLabel(value)
                v.setWordWrap(True)
                v.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                grid.addWidget(k, r, 0, Qt.AlignmentFlag.AlignTop)
                grid.addWidget(v, r, 1)
            layout.addLayout(grid)
        layout.addStretch()
        self._scroll.setWidget(body)   # replaces (and deletes) the previous body

    # ------------------------------------------------------------------ window

    def reject(self) -> None:
        self.hide()
        self.closed.emit()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(tokens.color(tokens.LINE), 1))
        painter.setBrush(tokens.color(tokens.PANEL, PANEL_ALPHA))
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 10, 10)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and event.position().y() < HEADER_DRAG_H:
            self._drag_from = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._drag_from is not None:
            self.move(event.globalPosition().toPoint() - self._drag_from)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        self._drag_from = None
        super().mouseReleaseEvent(event)
