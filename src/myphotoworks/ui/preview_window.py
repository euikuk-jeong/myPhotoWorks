"""PreviewWindow — 3-pane Before / After-A / After-B photo preview."""
from __future__ import annotations

import copy
from pathlib import Path

from PyQt6.QtCore import QPointF, Qt, pyqtSignal
from PyQt6.QtGui import (
    QImage,
    QKeyEvent,
    QPainter,
    QPixmap,
    QWheelEvent,
)
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from myphotoworks.models.photo_item import PhotoItem
from myphotoworks.models.settings import AppSettings
from myphotoworks.processing import processor
from myphotoworks.ui.exif_panel import ExifPanel
from myphotoworks.utils.exif_reader import read_exif

_BOTTOM_BAR_HEIGHT = 110
_ZOOM_FACTOR = 1.15
_ZOOM_MIN = 0.05
_ZOOM_MAX = 20.0


# ---------------------------------------------------------------------------
# _ImageView — zoom/pan canvas with auto-fit
# ---------------------------------------------------------------------------

class _ImageView(QWidget):
    """Custom widget rendering a QPixmap with zoom and synchronized pan.

    Fit management is handled externally by PreviewWindow._force_fit_all().

    Signals
    -------
    view_changed(zoom, offset) — emitted only on user-driven zoom/pan.
    """

    view_changed = pyqtSignal(float, QPointF)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumSize(100, 80)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(palette.ColorRole.Window, Qt.GlobalColor.white)
        self.setPalette(palette)

        self._pixmap: QPixmap | None = None
        self._zoom: float = 1.0
        self._offset = QPointF(0.0, 0.0)

        self._drag_start: QPointF | None = None
        self._drag_offset_start = QPointF(0.0, 0.0)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_pixmap(self, pixmap: QPixmap) -> None:
        self._pixmap = pixmap
        self.update()

    def set_view(self, zoom: float, offset: QPointF) -> None:
        """Apply zoom/offset from external source."""
        self._zoom = zoom
        self._offset = offset
        self.update()

    # ------------------------------------------------------------------
    # Paint
    # ------------------------------------------------------------------

    def paintEvent(self, event) -> None:  # noqa: N802
        if not self._pixmap:
            return
        from PyQt6.QtCore import QRectF
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        scaled_w = self._pixmap.width() * self._zoom
        scaled_h = self._pixmap.height() * self._zoom
        x = (self.width() - scaled_w) / 2.0 + self._offset.x()
        y = (self.height() - scaled_h) / 2.0 + self._offset.y()

        painter.drawPixmap(
            QRectF(x, y, scaled_w, scaled_h),
            self._pixmap,
            QRectF(self._pixmap.rect()),
        )

    # ------------------------------------------------------------------
    # Zoom (wheel)
    # ------------------------------------------------------------------

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        delta = event.angleDelta().y()
        factor = _ZOOM_FACTOR if delta > 0 else 1.0 / _ZOOM_FACTOR
        new_zoom = max(_ZOOM_MIN, min(_ZOOM_MAX, self._zoom * factor))
        r = new_zoom / self._zoom

        mouse = event.position()
        cx, cy = self.width() / 2.0, self.height() / 2.0
        self._offset = QPointF(
            r * self._offset.x() + (mouse.x() - cx) * (1.0 - r),
            r * self._offset.y() + (mouse.y() - cy) * (1.0 - r),
        )
        self._zoom = new_zoom
        self.update()
        self.view_changed.emit(self._zoom, QPointF(self._offset))

    # ------------------------------------------------------------------
    # Pan (drag)
    # ------------------------------------------------------------------

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = event.position()
            self._drag_offset_start = QPointF(self._offset)
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._drag_start is not None:
            delta = event.position() - self._drag_start
            self._offset = QPointF(
                self._drag_offset_start.x() + delta.x(),
                self._drag_offset_start.y() + delta.y(),
            )
            self.update()
            self.view_changed.emit(self._zoom, QPointF(self._offset))

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = None
            self.setCursor(Qt.CursorShape.OpenHandCursor)


# ---------------------------------------------------------------------------
# _ExifBar — scrollable EXIF info (Before pane bottom)
# ---------------------------------------------------------------------------

class _ExifBar(QWidget):
    """Compact two-column EXIF table shown below the Before pane."""

    _ROWS = [
        ("파일명",   "filename"),
        ("크기",    "size"),
        ("촬영일",   "date"),
        ("카메라",   "model"),
        ("셔터",    "shutter"),
        ("조리개",   "aperture"),
        ("초점거리",  "focal_length"),
        ("ISO",    "iso"),
        ("노출보정",  "exposure_bias"),
    ]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedHeight(_BOTTOM_BAR_HEIGHT)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._table = QTableWidget(len(self._ROWS), 2)
        self._table.horizontalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._table.setAlternatingRowColors(True)
        self._table.setFrameShape(QFrame.Shape.NoFrame)
        self._table.setWordWrap(False)

        # Pre-populate row labels
        for r, (label, _) in enumerate(self._ROWS):
            key_item = QTableWidgetItem(label)
            key_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self._table.setItem(r, 0, key_item)
            val_item = QTableWidgetItem("—")
            val_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self._table.setItem(r, 1, val_item)

        self._table.resizeRowsToContents()
        layout.addWidget(self._table)

    def update_photo(self, path: Path) -> None:
        exif = read_exif(path)
        for r, (_, key) in enumerate(self._ROWS):
            raw = exif.get(key, "")
            if key == "date" and raw:
                raw = raw.replace(":", "/", 2)
            self._table.item(r, 1).setText(raw or "—")


# ---------------------------------------------------------------------------
# _EffectsBar — inline color correction settings (After pane bottom)
# ---------------------------------------------------------------------------

class _EffectsBar(QWidget):
    settings_changed = pyqtSignal()

    def __init__(self, settings: AppSettings, parent=None) -> None:
        super().__init__(parent)
        self.setFixedHeight(_BOTTOM_BAR_HEIGHT)
        self._settings = copy.copy(settings)
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        row1 = QHBoxLayout()
        self._auto_level_cb = QCheckBox("Auto Level")
        self._auto_level_cb.setChecked(self._settings.auto_level)
        self._auto_level_cb.toggled.connect(self._on_change)
        row1.addWidget(self._auto_level_cb)

        self._auto_contrast_cb = QCheckBox("Auto Contrast")
        self._auto_contrast_cb.setChecked(self._settings.auto_contrast)
        self._auto_contrast_cb.toggled.connect(self._on_change)
        row1.addWidget(self._auto_contrast_cb)
        row1.addStretch()
        layout.addLayout(row1)

        form = QFormLayout()
        form.setSpacing(2)

        self._brightness_slider = _MiniSlider(-100, 100, self._settings.brightness)
        self._brightness_slider.valueChanged.connect(self._on_change)
        form.addRow("밝기", self._brightness_slider)

        self._contrast_slider = _MiniSlider(-100, 100, self._settings.contrast)
        self._contrast_slider.valueChanged.connect(self._on_change)
        form.addRow("대비", self._contrast_slider)

        layout.addLayout(form)

    def settings(self) -> AppSettings:
        self._settings.auto_level = self._auto_level_cb.isChecked()
        self._settings.auto_contrast = self._auto_contrast_cb.isChecked()
        self._settings.brightness = self._brightness_slider.value()
        self._settings.contrast = self._contrast_slider.value()
        return self._settings

    def _on_change(self) -> None:
        self.settings_changed.emit()


# ---------------------------------------------------------------------------
# _MiniSlider
# ---------------------------------------------------------------------------

class _MiniSlider(QWidget):
    valueChanged = pyqtSignal()

    def __init__(self, minimum: int, maximum: int, value: int, parent=None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(minimum, maximum)
        self._slider.setValue(value)

        self._spin = QSpinBox()
        self._spin.setRange(minimum, maximum)
        self._spin.setValue(value)
        self._spin.setFixedWidth(48)

        layout.addWidget(self._slider)
        layout.addWidget(self._spin)

        self._slider.valueChanged.connect(self._on_slider)
        self._spin.valueChanged.connect(self._on_spin)

    def value(self) -> int:
        return self._slider.value()

    def _on_slider(self, v: int) -> None:
        self._spin.blockSignals(True)
        self._spin.setValue(v)
        self._spin.blockSignals(False)
        self.valueChanged.emit()

    def _on_spin(self, v: int) -> None:
        self._slider.blockSignals(True)
        self._slider.setValue(v)
        self._slider.blockSignals(False)
        self.valueChanged.emit()


# ---------------------------------------------------------------------------
# _Pane — title + image view + bottom widget
# ---------------------------------------------------------------------------

class _Pane(QWidget):
    def __init__(self, title: str, bottom_widget: QWidget | None = None, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)

        title_lbl = QLabel(title)
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_lbl.setStyleSheet("font-weight: bold; background: #555; color: white; padding: 2px;")
        layout.addWidget(title_lbl)

        self.image_view = _ImageView()
        layout.addWidget(self.image_view, stretch=1)

        if bottom_widget is not None:
            layout.addWidget(bottom_widget)

    def set_pixmap(self, pixmap: QPixmap) -> None:
        self.image_view.set_pixmap(pixmap)


# ---------------------------------------------------------------------------
# PreviewWindow
# ---------------------------------------------------------------------------

class PreviewWindow(QMainWindow):
    """3-pane preview: Before | After-A | After-B.

    Keyboard shortcuts
    ------------------
    1 / 2 / 3       save from respective pane → next
    Space / `       skip → next
    Del             delete original → next
    ← / →           previous / next photo
    E               toggle EXIF floating panel
    """

    photo_saved = pyqtSignal(object)
    photo_deleted = pyqtSignal(object)

    def __init__(
        self,
        photos: list[PhotoItem],
        settings: AppSettings,
        first_file_dir: Path | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("미리보기")
        self.resize(1200, 750)

        self._photos = photos
        self._base_settings = settings
        self._first_file_dir = first_file_dir or (
            photos[0].source_path.parent if photos else Path(".")
        )
        self._index = 0
        self._exif_panel: ExifPanel | None = None
        self._user_has_zoomed = False
        self._first_show = True

        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(4)

        self._splitter = QSplitter(Qt.Orientation.Horizontal)

        self._exif_bar = _ExifBar()
        self._before_pane = _Pane("Before (원본)", self._exif_bar)
        self._before_pane.image_view.view_changed.connect(self._on_view_changed)
        self._splitter.addWidget(self._before_pane)

        self._effects_bar_a = _EffectsBar(copy.copy(self._base_settings))
        self._effects_bar_a.settings_changed.connect(self._on_after_a_changed)
        self._after_a_pane = _Pane("After-A", self._effects_bar_a)
        self._after_a_pane.image_view.view_changed.connect(self._on_view_changed)
        self._splitter.addWidget(self._after_a_pane)

        self._effects_bar_b = _EffectsBar(copy.copy(self._base_settings))
        self._effects_bar_b.settings_changed.connect(self._on_after_b_changed)
        self._after_b_pane = _Pane("After-B", self._effects_bar_b)
        self._after_b_pane.image_view.view_changed.connect(self._on_view_changed)
        self._splitter.addWidget(self._after_b_pane)

        for i in range(3):
            self._splitter.setStretchFactor(i, 1)

        root.addWidget(self._splitter, 1)  # stretch=1 so splitter fills all available height

        self._counter_lbl = QLabel()
        self._counter_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self._counter_lbl)

        # Action button bar
        action_bar = QHBoxLayout()
        action_bar.setSpacing(6)

        def _btn(label: str, shortcut: str, callback) -> QPushButton:
            btn = QPushButton(f"{label}\n[{shortcut}]")
            btn.setFixedHeight(44)
            btn.clicked.connect(callback)
            return btn

        self._prev_btn = _btn("이전", "←", self._go_prev)
        action_bar.addWidget(self._prev_btn)
        action_bar.addStretch()

        action_bar.addWidget(_btn("스킵", "Space", self._on_skip))
        action_bar.addWidget(_btn("1 선택", "1", self._on_save_1))
        action_bar.addWidget(_btn("2 선택", "2", self._on_save_2))
        action_bar.addWidget(_btn("3 선택", "3", self._on_save_3))

        del_btn = _btn("원본 삭제", "Del", self._on_delete)
        del_btn.setStyleSheet("color: red;")
        action_bar.addWidget(del_btn)

        action_bar.addStretch()
        self._next_btn = _btn("다음", "→", self._go_next)
        action_bar.addWidget(self._next_btn)

        exif_btn = QPushButton("EXIF\n[E]")
        exif_btn.setFixedHeight(44)
        exif_btn.setCheckable(True)
        exif_btn.toggled.connect(self._toggle_exif)
        action_bar.addWidget(exif_btn)

        root.addLayout(action_bar)

        status_bar = QStatusBar()
        self.setStatusBar(status_bar)
        hint = QLabel("1:Before저장(리사이즈만)  2:After-A저장  3:After-B저장  Space/`:스킵  Del:원본삭제  ←/→:이전/다음  E:EXIF")
        hint.setStyleSheet("color: gray;")
        status_bar.addWidget(hint)

    # ------------------------------------------------------------------
    # Show / resize events
    # ------------------------------------------------------------------

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if self._first_show:
            self._first_show = False
            self._load_current()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        # Use a deferred call so child widgets have been resized before we read their sizes
        if not self._user_has_zoomed:
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(0, self._force_fit_all)

    def _force_fit_all(self) -> None:
        """Equalize pane widths then apply a common fit-zoom to all 3 panes."""
        # Force equal widths so one pane doesn't get less space due to size hints
        total = self._splitter.width()
        if total <= 0:
            return
        third = total // 3
        self._splitter.setSizes([third, third, third])

        # Activate each pane's layout immediately so child widget sizes reflect the new split
        for pane in (self._before_pane, self._after_a_pane, self._after_b_pane):
            if pane.layout():
                pane.layout().activate()

        # Compute minimum fit-zoom across all 3 panes so image fits everywhere
        panes = (self._before_pane, self._after_a_pane, self._after_b_pane)
        zoom: float | None = None
        for pane in panes:
            view = pane.image_view
            if view._pixmap and view.width() > 0 and view.height() > 0:
                z = min(
                    view.width() / view._pixmap.width(),
                    view.height() / view._pixmap.height(),
                )
                if zoom is None or z < zoom:
                    zoom = z
        if zoom is None:
            return
        offset = QPointF(0.0, 0.0)
        for pane in panes:
            pane.image_view._zoom = zoom
            pane.image_view._offset = offset
            pane.image_view.update()

    # ------------------------------------------------------------------
    # Photo loading & rendering
    # ------------------------------------------------------------------

    def _load_current(self) -> None:
        if not self._photos:
            return
        from PyQt6.QtCore import QTimer
        photo = self._photos[self._index]
        total = len(self._photos)
        self._counter_lbl.setText(f"{self._index + 1} / {total}  —  {photo.source_path.name}")
        self._prev_btn.setEnabled(self._index > 0)
        self._next_btn.setEnabled(self._index < total - 1)

        self._user_has_zoomed = False
        self._exif_bar.update_photo(photo.source_path)
        self._render_before(photo)
        self._render_after(self._after_a_pane, self._effects_bar_a, photo)
        self._render_after(self._after_b_pane, self._effects_bar_b, photo)

        # Defer fit so the event loop has processed the new pixmaps
        QTimer.singleShot(0, self._force_fit_all)

        if self._exif_panel and self._exif_panel.isVisible():
            self._exif_panel.update_photo(
                photo.source_path, index=self._index + 1, total=len(self._photos)
            )

    def _render_before(self, photo: PhotoItem) -> None:
        try:
            from PIL import Image
            with Image.open(photo.source_path) as img:
                self._before_pane.set_pixmap(self._pil_to_pixmap(img.convert("RGB")))
        except Exception:
            pass

    def _render_after(self, pane: _Pane, effects_bar: _EffectsBar, photo: PhotoItem) -> None:
        """Render with color corrections only — no resize in preview."""
        try:
            settings = effects_bar.settings()
            preview_settings = copy.copy(settings)
            preview_settings.resize_enabled = False   # resize는 저장 시에만 적용
            img = processor.process(photo, preview_settings, apply_effects=True)
            pane.set_pixmap(self._pil_to_pixmap(img))
        except Exception:
            pass

    @staticmethod
    def _pil_to_pixmap(img) -> QPixmap:
        data = img.tobytes("raw", "RGB")
        qimg = QImage(data, img.width, img.height, img.width * 3,
                      QImage.Format.Format_RGB888)
        return QPixmap.fromImage(qimg)

    # ------------------------------------------------------------------
    # View sync
    # ------------------------------------------------------------------

    def _on_view_changed(self, zoom: float, offset: QPointF) -> None:
        self._user_has_zoomed = True
        sender_view = self.sender()
        for pane in (self._before_pane, self._after_a_pane, self._after_b_pane):
            if pane.image_view is not sender_view:
                pane.image_view.set_view(zoom, offset)

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _go_prev(self) -> None:
        if self._index > 0:
            self._index -= 1
            self._load_current()

    def _go_next(self) -> None:
        if self._index < len(self._photos) - 1:
            self._index += 1
            self._load_current()

    # ------------------------------------------------------------------
    # After pane re-render
    # ------------------------------------------------------------------

    def _on_after_a_changed(self) -> None:
        self._render_after(self._after_a_pane, self._effects_bar_a, self._photos[self._index])

    def _on_after_b_changed(self) -> None:
        self._render_after(self._after_b_pane, self._effects_bar_b, self._photos[self._index])

    # ------------------------------------------------------------------
    # EXIF floating panel
    # ------------------------------------------------------------------

    def _toggle_exif(self, checked: bool) -> None:
        if checked:
            if self._exif_panel is None:
                self._exif_panel = ExifPanel(self)
            self._exif_panel.update_photo(
                self._photos[self._index].source_path,
                index=self._index + 1, total=len(self._photos),
            )
            self._exif_panel.show()
        else:
            if self._exif_panel:
                self._exif_panel.hide()

    # ------------------------------------------------------------------
    # Button callbacks
    # ------------------------------------------------------------------

    def _on_skip(self) -> None:
        self._advance()

    def _on_save_1(self) -> None:
        self._save_and_advance(copy.copy(self._base_settings), apply_effects=False)

    def _on_save_2(self) -> None:
        self._save_and_advance(self._effects_bar_a.settings(), apply_effects=True)

    def _on_save_3(self) -> None:
        self._save_and_advance(self._effects_bar_b.settings(), apply_effects=True)

    def _on_delete(self) -> None:
        photo = self._photos[self._index]
        try:
            photo.source_path.unlink()
            self.photo_deleted.emit(photo)
        except Exception as e:
            self.statusBar().showMessage(f"삭제 실패: {e}", 3000)
            return
        self._photos.pop(self._index)
        if not self._photos:
            self.close()
            return
        if self._index >= len(self._photos):
            self._index = len(self._photos) - 1
        self._load_current()

    # ------------------------------------------------------------------
    # Save / advance
    # ------------------------------------------------------------------

    def _save_and_advance(self, settings: AppSettings, apply_effects: bool) -> None:
        photo = self._photos[self._index]
        try:
            img = processor.process(photo, settings, apply_effects=apply_effects)
            out_path = self._resolve_output_path(photo, settings)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            processor.save(img, out_path, settings, photo.source_path)
            self.photo_saved.emit(photo)
        except Exception as e:
            self.statusBar().showMessage(f"저장 실패: {e}", 3000)
            return
        self._advance()

    def _advance(self) -> None:
        if self._index < len(self._photos) - 1:
            self._index += 1
            self._load_current()
        else:
            self.statusBar().showMessage("마지막 사진입니다.", 2000)

    def _resolve_output_path(self, photo: PhotoItem, settings: AppSettings) -> Path:
        from myphotoworks.models.settings import OutputPathMode
        stem = settings.output_prefix + photo.source_path.stem + settings.output_suffix
        mode = settings.output_path_mode
        if mode == OutputPathMode.FIRST_FILE:
            out_dir = self._first_file_dir / "output"
        elif mode == OutputPathMode.PER_FILE:
            out_dir = photo.source_path.parent / "output"
        else:
            out_dir = settings.output_custom_dir
        return out_dir / (stem + ".jpg")

    # ------------------------------------------------------------------
    # Keyboard shortcuts
    # ------------------------------------------------------------------

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        key = event.key()
        if key == Qt.Key.Key_1:
            self._on_save_1()
        elif key == Qt.Key.Key_2:
            self._on_save_2()
        elif key == Qt.Key.Key_3:
            self._on_save_3()
        elif key in (Qt.Key.Key_Space, Qt.Key.Key_QuoteLeft):
            self._on_skip()
        elif key == Qt.Key.Key_Delete:
            self._on_delete()
        elif key == Qt.Key.Key_Left:
            self._go_prev()
        elif key == Qt.Key.Key_Right:
            self._go_next()
        elif key == Qt.Key.Key_E:
            if self._exif_panel and self._exif_panel.isVisible():
                self._exif_panel.hide()
            else:
                if self._exif_panel is None:
                    self._exif_panel = ExifPanel(self)
                self._exif_panel.update_photo(
                    self._photos[self._index].source_path,
                    index=self._index + 1, total=len(self._photos),
                )
                self._exif_panel.show()
        else:
            super().keyPressEvent(event)
