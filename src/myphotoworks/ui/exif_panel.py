"""ExifPanel — floating, moveable window showing EXIF information."""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QFormLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from myphotoworks.utils.exif_reader import read_exif


class ExifPanel(QDialog):
    """Non-modal floating window that displays EXIF data for a photo.

    The window is moveable and stays on top of the preview window.
    Call update_photo(path) to refresh the displayed data.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent, Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowTitle("EXIF 정보")
        self.setMinimumWidth(260)

        layout = QVBoxLayout(self)
        layout.setSpacing(4)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        def _label() -> QLabel:
            lbl = QLabel("—")
            lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            return lbl

        self._lbl_filename = _label()
        self._lbl_size = _label()
        self._lbl_date = _label()
        self._lbl_iso = _label()
        self._lbl_comment = _label()

        form.addRow("파일명", self._lbl_filename)
        form.addRow("크기", self._lbl_size)
        form.addRow("촬영일", self._lbl_date)
        form.addRow("ISO", self._lbl_iso)
        form.addRow("코멘트", self._lbl_comment)

        layout.addLayout(form)
        self.adjustSize()

    def update_photo(self, path: Path) -> None:
        """Load EXIF from path and refresh all labels."""
        exif = read_exif(path)
        self._lbl_filename.setText(exif.get("filename") or "—")
        self._lbl_size.setText(exif.get("size") or "—")

        date_raw = exif.get("date", "")
        self._lbl_date.setText(date_raw.replace(":", "/", 2) if date_raw else "—")

        self._lbl_iso.setText(exif.get("iso") or "—")
        self._lbl_comment.setText(exif.get("comment") or "—")
