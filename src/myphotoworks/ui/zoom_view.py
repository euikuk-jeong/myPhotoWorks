"""ZoomPanView — image canvas with wheel zoom, drag pan and middle-click reset."""
from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPixmap, QWheelEvent
from PyQt6.QtWidgets import QWidget

ZOOM_STEP = 1.15
MAX_ZOOM = 8.0            # relative to the logical image size (see set_image)
DETAIL_TRIGGER = 1.05     # ask for a sharper image once zoomed past fit * this


class ZoomPanView(QWidget):
    """Shows one image fitted to the widget.

    * wheel        — zoom around the cursor (never smaller than "fit")
    * left drag    — pan (the image cannot be dragged out of view)
    * middle click — reset to fit / centred
    * a higher-resolution pixmap can replace the display one (``set_detail``) without
      changing what the user sees; ``detail_requested`` fires once per image when the
      user first zooms in.
    """

    detail_requested = pyqtSignal(str)   # key of the image
    zoom_changed = pyqtSignal(float)     # zoom relative to "fit" (1.0 = fitted)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumSize(360, 240)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(palette.ColorRole.Window, QColor(13, 17, 23))
        self.setPalette(palette)

        self._key: str | None = None
        self._pixmap: QPixmap | None = None
        self._logical_w = 1.0
        self._logical_h = 1.0
        self._message = ""
        self._has_detail = False
        self._detail_asked = False
        self._zoom = 1.0
        self._offset = QPointF(0.0, 0.0)
        self._user_zoomed = False
        self._drag_start: QPointF | None = None
        self._drag_offset = QPointF(0.0, 0.0)

    # ------------------------------------------------------------------ API

    @property
    def key(self) -> str | None:
        return self._key

    @property
    def zoom(self) -> float:
        return self._zoom

    @property
    def offset(self) -> QPointF:
        return QPointF(self._offset)

    def fit_zoom(self) -> float:
        if not self._pixmap or self.width() <= 0 or self.height() <= 0:
            return 1.0
        return min(self.width() / self._logical_w, self.height() / self._logical_h)

    def relative_zoom(self) -> float:
        fit = self.fit_zoom()
        return self._zoom / fit if fit > 0 else 1.0

    def set_image(self, key: str, pixmap: QPixmap | None, message: str = "") -> None:
        """Show ``pixmap``. Same ``key`` as before keeps the current zoom and position;
        a different key resets to fit. The pixmap's size defines the logical size."""
        same = key == self._key and pixmap is not None and self._pixmap is not None
        self._key = key
        self._message = message
        if pixmap is None or pixmap.isNull():
            self._pixmap = None
            self.update()
            return
        if same:
            # refresh only (e.g. adoption changed): keep view state and detail image
            if not self._has_detail:
                self._pixmap = pixmap
                self._logical_w, self._logical_h = float(pixmap.width()), float(pixmap.height())
            self.update()
            return
        self._pixmap = pixmap
        self._logical_w, self._logical_h = float(pixmap.width()), float(pixmap.height())
        self._has_detail = False
        self._detail_asked = False
        self.reset_view()

    def set_detail(self, key: str, pixmap: QPixmap) -> None:
        """Swap in a sharper pixmap of the *same* image; the view does not move."""
        if key != self._key or pixmap.isNull() or self._pixmap is None:
            return
        self._pixmap = pixmap
        self._has_detail = True
        self.update()

    def reset_view(self) -> None:
        self._zoom = self.fit_zoom()
        self._offset = QPointF(0.0, 0.0)
        self._user_zoomed = False
        self._detail_asked = self._has_detail
        self.update()
        self.zoom_changed.emit(1.0)

    def clear(self) -> None:
        self._key = None
        self._pixmap = None
        self._has_detail = False
        self.update()

    # ------------------------------------------------------------------ helpers

    def _clamp_offset(self, offset: QPointF) -> QPointF:
        sw, sh = self._logical_w * self._zoom, self._logical_h * self._zoom
        limit_x = max(0.0, (sw - self.width()) / 2.0)
        limit_y = max(0.0, (sh - self.height()) / 2.0)
        return QPointF(
            max(-limit_x, min(limit_x, offset.x())),
            max(-limit_y, min(limit_y, offset.y())),
        )

    def _image_rect(self) -> QRectF:
        sw, sh = self._logical_w * self._zoom, self._logical_h * self._zoom
        return QRectF(
            (self.width() - sw) / 2.0 + self._offset.x(),
            (self.height() - sh) / 2.0 + self._offset.y(),
            sw, sh,
        )

    # ------------------------------------------------------------------ paint

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        if self._pixmap is None:
            if self._message:
                painter.setPen(QColor(139, 148, 158))
                painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._message)
            return
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.drawPixmap(self._image_rect(), self._pixmap, QRectF(self._pixmap.rect()))

        rel = self.relative_zoom()
        text = "화면 맞춤" if rel <= 1.001 else f"{rel * 100:.0f}%"
        hint = "휠: 확대/축소 · 드래그: 이동 · 가운데 버튼: 초기화"
        font = QFont(painter.font())
        font.setPointSize(8)
        painter.setFont(font)
        painter.setPen(QColor(230, 237, 243, 210))
        painter.fillRect(QRectF(6, self.height() - 24, self.width() - 12, 18),
                         QColor(13, 17, 23, 150))
        painter.drawText(QRectF(12, self.height() - 24, self.width() - 24, 18),
                         Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                         f"{text}   {hint}")

    # ------------------------------------------------------------------ input

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        if self._pixmap is None:
            return
        delta = event.angleDelta().y()
        if delta == 0:
            return
        fit = self.fit_zoom()
        factor = ZOOM_STEP if delta > 0 else 1.0 / ZOOM_STEP
        new_zoom = max(fit, min(MAX_ZOOM, self._zoom * factor))
        if new_zoom == self._zoom:
            return
        r = new_zoom / self._zoom
        mouse = event.position()
        centre = QPointF(self.width() / 2.0, self.height() / 2.0)
        # keep the image point under the cursor fixed
        p = mouse - centre - self._offset
        self._zoom = new_zoom
        self._offset = self._clamp_offset(mouse - centre - p * r)
        self._user_zoomed = new_zoom > fit * 1.0005
        self.update()
        self.zoom_changed.emit(self.relative_zoom())
        if (self._user_zoomed and not self._detail_asked
                and new_zoom > fit * DETAIL_TRIGGER and self._key is not None):
            self._detail_asked = True
            self.detail_requested.emit(self._key)
        event.accept()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self._pixmap is not None:
            self._drag_start = event.position()
            self._drag_offset = QPointF(self._offset)
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        elif event.button() == Qt.MouseButton.MiddleButton:
            self.reset_view()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._drag_start is not None:
            moved = self._drag_offset + (event.position() - self._drag_start)
            self._offset = self._clamp_offset(moved)
            self.update()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = None
            self.setCursor(Qt.CursorShape.OpenHandCursor)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if self._pixmap is None:
            return
        if self._user_zoomed:
            self._zoom = max(self._zoom, self.fit_zoom())
            self._offset = self._clamp_offset(self._offset)
        else:
            self._zoom = self.fit_zoom()
            self._offset = QPointF(0.0, 0.0)
