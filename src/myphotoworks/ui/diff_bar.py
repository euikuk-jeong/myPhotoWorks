"""DiffBar — a bar drawn from the centre line, for comparing a photo with the recommended one.

Right of the centre (sage) = better than the recommended photo, left (rust) = worse. A difference
inside the criterion's deadband ("same") is a short grey bar, "none" (nothing to compare) draws
only the track. The recommended photo itself has no bar: it is the centre line.
"""
from __future__ import annotations

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import QSizePolicy, QWidget

from myphotoworks.ui.styles import tokens

_TRACK_H = 4.0
_DECIDING_H = 6.0                  # the criterion that decided the group is a little thicker


class DiffBar(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._delta = 0.0
        self._verdict = "none"
        self.setFixedHeight(10)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_delta(self, delta: float, verdict: str) -> None:
        """``delta`` -1..1 of the half bar (positive = better); ``verdict`` better / worse /
        same / none."""
        self._verdict = verdict
        self._delta = 0.0 if verdict == "none" else max(-1.0, min(1.0, float(delta)))
        self.update()

    def value(self) -> int:
        """The signed bar length in percent of the half width (-100..100)."""
        return round(self._delta * 100)

    def verdict(self) -> str:
        return self._verdict

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = float(self.width()), float(self.height())
        thick = _DECIDING_H if self.property("deciding") else _TRACK_H
        top = (h - thick) / 2.0
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(tokens.RAISED))
        painter.drawRoundedRect(QRectF(0.0, top, w, thick), thick / 2.0, thick / 2.0)
        centre = w / 2.0
        if self._delta != 0.0:
            colour = {"better": tokens.PICK, "worse": tokens.WARN}.get(
                self._verdict, tokens.TEXT_DISABLED)
            length = abs(self._delta) * centre
            left = centre if self._delta > 0 else centre - length
            painter.setBrush(QColor(colour))
            painter.drawRect(QRectF(left, top, length, thick))
        painter.setBrush(QColor(tokens.TEXT_MUTED))
        painter.drawRect(QRectF(centre - 0.5, 0.0, 1.0, h))        # the recommended photo
