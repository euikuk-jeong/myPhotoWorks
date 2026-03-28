"""ExifPanel — floating, moveable window showing EXIF information as a table."""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from myphotoworks.utils.exif_reader import read_exif


def _item(text: str) -> QTableWidgetItem:
    item = QTableWidgetItem(text or "—")
    item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
    return item


def _fmt_date(raw: str) -> str:
    return raw.replace(":", "/", 2) if raw else ""


class ExifPanel(QDialog):
    """Non-modal floating window that displays EXIF data as a two-column table."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent, Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowTitle("EXIF 정보")
        self.resize(380, 520)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        self._table = QTableWidget(0, 2)
        self._table.setHorizontalHeaderLabels(["항목", "정보"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setFont(QFont("", -1, QFont.Weight.Bold))
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.setWordWrap(False)

        layout.addWidget(self._table)

    def update_photo(self, path: Path, index: int = 0, total: int = 0) -> None:
        """Load EXIF from *path* and refresh the table.

        Parameters
        ----------
        index : 1-based current photo index (0 = don't show 번호 row)
        total : total photo count
        """
        exif = read_exif(path)

        rows: list[tuple[str, str]] = []

        if index > 0:
            rows.append(("번호", f"{index} / {total}"))

        rows += [
            ("파일이름",   exif["filename"]),
            ("파일크기",   exif["file_size"]),
            ("파일날짜",   _fmt_date(exif["file_date"])),
            ("카메라 제조사", exif["make"]),
            ("카메라 모델명", exif["model"]),
            ("소프트웨어",  exif["software"]),
            ("촬영날짜",   _fmt_date(exif["date"])),
            ("해상도",    exif["size"]),
            ("Orientation", exif["orientation"]),
            ("플래시 사용", exif["flash"]),
            ("초점 거리",  exif["focal_length"]),
            ("셔터속도",   exif["shutter"]),
            ("조리개 값",  exif["aperture"]),
            ("ISO 값",   exif["iso"]),
            ("노출보정",   exif["exposure_bias"]),
            ("측광 모드",  exif["metering_mode"]),
            ("프로그램 모드", exif["program_mode"]),
            ("코멘트",    exif["comment"]),
        ]

        self._table.setRowCount(len(rows))
        for r, (key, val) in enumerate(rows):
            self._table.setItem(r, 0, _item(key))
            self._table.setItem(r, 1, _item(val))

        self._table.resizeRowsToContents()
