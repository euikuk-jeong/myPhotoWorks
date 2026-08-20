"""PreviewWindow — 3-pane Before / After-A / After-B photo preview."""
from __future__ import annotations

import copy
import logging
import threading
import time
from pathlib import Path

from PIL import Image, ImageFile, ImageOps

# Allow Pillow to load truncated/broken JPEG files instead of raising OSError.
ImageFile.LOAD_TRUNCATED_IMAGES = True
from PyQt6.QtCore import QEvent, QObject, QPointF, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QImage,
    QKeyEvent,
    QLinearGradient,
    QPainter,
    QPixmap,
    QWheelEvent,
)
from PyQt6.QtCore import QRunnable, QThreadPool, QTimer, pyqtSignal as _pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,

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
from myphotoworks.models.settings import AppSettings, CorrectionMode
from myphotoworks.processing import processor
from myphotoworks.recipes.builtin_recipes import (
    BUILTIN_RECIPES, build_correction_combo_items, populate_correction_combo,
)
from myphotoworks.ui.exif_panel import ExifPanel
from myphotoworks.utils.exif_reader import read_exif

_COMBO_ITEMS = build_correction_combo_items()

logger = logging.getLogger(__name__)

_BOTTOM_BAR_HEIGHT = 200
_ZOOM_FACTOR = 1.15
_ZOOM_MIN = 0.05
_ZOOM_MAX = 20.0


def _open_image(path: Path) -> Image.Image:
    """Open an image file with EXIF orientation correction applied."""
    return ImageOps.exif_transpose(Image.open(path)).convert("RGB")


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
    fit_requested = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumSize(100, 80)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(palette.ColorRole.Window, QColor(15, 20, 30))
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
        elif event.button() == Qt.MouseButton.MiddleButton:
            self.fit_requested.emit()

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

_RECIPE_ROWS = [
    ("필름 시뮬레이션", "film_sim"),
    ("화이트밸런스",    "wb"),
    ("톤 커브",        "tone"),
    ("채도",           "color"),
    ("선명도",         "sharpness"),
    ("그레인",         "grain"),
]


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
        layout.setSpacing(3)

        # Correction mode dropdown
        self._mode_combo = QComboBox()
        populate_correction_combo(self._mode_combo)
        self._mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        layout.addWidget(self._mode_combo)

        # Brightness / Contrast
        form = QFormLayout()
        form.setSpacing(2)
        form.setContentsMargins(0, 0, 0, 0)

        self._brightness_slider = _MiniSlider(-100, 100, self._settings.brightness)
        self._brightness_slider.valueChanged.connect(self._on_change)
        form.addRow("밝기", self._brightness_slider)

        self._contrast_slider = _MiniSlider(-100, 100, self._settings.contrast)
        self._contrast_slider.valueChanged.connect(self._on_change)
        form.addRow("대비", self._contrast_slider)

        layout.addLayout(form)

        # Recipe info table — styled like _ExifBar, shown only when recipe mode active
        self._recipe_table = QTableWidget(len(_RECIPE_ROWS), 2)
        self._recipe_table.horizontalHeader().setVisible(False)
        self._recipe_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self._recipe_table.horizontalHeader().setStretchLastSection(True)
        self._recipe_table.verticalHeader().setVisible(False)
        self._recipe_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._recipe_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._recipe_table.setAlternatingRowColors(True)
        self._recipe_table.setFrameShape(QFrame.Shape.NoFrame)
        self._recipe_table.setWordWrap(False)

        for r, (label, _) in enumerate(_RECIPE_ROWS):
            key_item = QTableWidgetItem(label)
            key_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self._recipe_table.setItem(r, 0, key_item)
            val_item = QTableWidgetItem("—")
            val_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self._recipe_table.setItem(r, 1, val_item)

        self._recipe_table.resizeRowsToContents()
        layout.addWidget(self._recipe_table)

        self._sync_mode_combo()
        self._update_recipe_info()

    def settings(self) -> AppSettings:
        self._settings.brightness = self._brightness_slider.value()
        self._settings.contrast = self._contrast_slider.value()
        return self._settings

    def load_settings(self, settings: AppSettings) -> None:
        """Sync UI to new settings without emitting signals."""
        self._settings = copy.copy(settings)
        self._sync_mode_combo()
        self._brightness_slider.set_value(self._settings.brightness)
        self._contrast_slider.set_value(self._settings.contrast)
        self._update_recipe_info()

    def _sync_mode_combo(self) -> None:
        target_mode = self._settings.correction_mode
        target_key = self._settings.recipe_name
        self._mode_combo.blockSignals(True)
        for i, item in enumerate(_COMBO_ITEMS):
            if item.is_separator:
                continue
            if item.mode == target_mode and item.recipe_key == target_key:
                self._mode_combo.setCurrentIndex(i)
                break
        self._mode_combo.blockSignals(False)

    def _update_recipe_info(self) -> None:
        is_recipe = self._settings.correction_mode == CorrectionMode.RECIPE
        self._recipe_table.setVisible(is_recipe)
        if not is_recipe:
            return
        rd = BUILTIN_RECIPES.get(self._settings.recipe_name)
        if rd is None:
            return
        values = [
            rd.film_sim.value,
            f"{rd.wb_kelvin}K  R:{rd.wb_shift_r:+d}  B:{rd.wb_shift_b:+d}",
            f"S:{rd.tone_shadow:+d}  H:{rd.tone_highlight:+d}",
            f"{rd.color:+d}",
            f"{rd.sharpness:+d}",
            rd.grain_effect,
        ]
        for r, val in enumerate(values):
            self._recipe_table.item(r, 1).setText(val)

    def _on_mode_changed(self, index: int) -> None:
        if index < 0 or index >= len(_COMBO_ITEMS):
            return
        item = _COMBO_ITEMS[index]
        if item.is_separator:
            self._sync_mode_combo()
            return
        self._settings.correction_mode = item.mode
        self._settings.recipe_name = item.recipe_key
        self._update_recipe_info()
        self.settings_changed.emit()

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

    def set_value(self, v: int) -> None:
        """Set value without emitting valueChanged."""
        self._slider.blockSignals(True)
        self._spin.blockSignals(True)
        self._slider.setValue(v)
        self._spin.setValue(v)
        self._slider.blockSignals(False)
        self._spin.blockSignals(False)

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
        title_lbl.setObjectName("pane-title")
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
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

# ---------------------------------------------------------------------------
# _PrefetchCache — background image loader for adjacent photos
# ---------------------------------------------------------------------------

class _PrefetchCache:
    """Cache that pre-loads adjacent images in a background thread.

    Stores tuples of (original_image, preview_image) keyed by file path.
    Capacity is kept small (3 entries: prev, current, next) to limit memory.
    """

    _MAX_ENTRIES = 3

    def __init__(self, preview_max_px: int) -> None:
        self._preview_max_px = preview_max_px
        self._cache: dict[Path, tuple[Image.Image, Image.Image]] = {}
        self._lock = threading.Lock()
        self._pending: set[Path] = set()

    def get(self, path: Path) -> tuple[Image.Image, Image.Image] | None:
        with self._lock:
            return self._cache.get(path)

    def _load_and_store(self, path: Path) -> None:
        try:
            t0 = time.perf_counter()
            img = _open_image(path)
            w, h = img.size
            long_side = max(w, h)
            if long_side <= self._preview_max_px:
                preview = img
            else:
                ratio = self._preview_max_px / long_side
                new_size = (max(1, int(w * ratio)), max(1, int(h * ratio)))
                preview = img.resize(new_size, Image.Resampling.LANCZOS)
            elapsed = (time.perf_counter() - t0) * 1000
            logger.debug("[prefetch] loaded %.1f ms  (%s)", elapsed, path.name)
            with self._lock:
                self._cache[path] = (img, preview)
                self._pending.discard(path)
        except Exception:
            logger.debug("[prefetch] failed to load %s", path.name, exc_info=True)
            with self._lock:
                self._pending.discard(path)

    def prefetch(self, paths: list[Path]) -> None:
        """Schedule background loads for given paths, evicting stale entries."""
        path_set = set(paths)
        with self._lock:
            # Evict entries not in the desired set
            for key in list(self._cache.keys()):
                if key not in path_set:
                    del self._cache[key]
            to_load = [p for p in paths if p not in self._cache and p not in self._pending]
            self._pending.update(to_load)
        for p in to_load:
            threading.Thread(target=self._load_and_store, args=(p,), daemon=True).start()

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()


# ---------------------------------------------------------------------------
# _RenderWorker — background QRunnable for After-pane rendering
# ---------------------------------------------------------------------------

class _RenderWorkerSignals(QObject):
    done = _pyqtSignal(object, str, int)  # (QPixmap, pane_id, seq)


class _RenderWorker(QRunnable):
    def __init__(
        self,
        photo: PhotoItem,
        settings: AppSettings,
        source_image,
        pane_id: str,
        seq: int,
    ) -> None:
        super().__init__()
        self.setAutoDelete(True)
        self._photo = photo
        self._settings = settings
        self._source = source_image
        self._pane_id = pane_id
        self._seq = seq
        self.signals = _RenderWorkerSignals()

    def run(self) -> None:
        try:
            img = processor.process(
                self._photo, self._settings,
                apply_effects=True,
                source_image=self._source,
            )
            pixmap = PreviewWindow._pil_to_pixmap(img)
            self.signals.done.emit(pixmap, self._pane_id, self._seq)
        except Exception:
            logger.debug("[_RenderWorker] render failed", exc_info=True)


class PreviewWindow(QMainWindow):
    """3-pane preview: Before | After-A | After-B.

    Keyboard shortcuts
    ------------------
    1 / 2 / 3       save from respective pane → next
    Space           skip → next
    Del             delete original → next
    ← / ` / →       previous / next photo
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
        self._saved_count = 0
        self._exif_panel: ExifPanel | None = None
        self._user_has_zoomed = False
        self._first_show = True
        self._cached_image: Image.Image | None = None
        self._cached_preview: Image.Image | None = None  # downsampled for effects
        self._prefetch = _PrefetchCache(preview_max_px=1600)

        # Background render sequencing — discard stale results
        self._render_seq_a: int = 0
        self._render_seq_b: int = 0

        # Debounce timers: fire 150 ms after last settings change
        self._debounce_a = QTimer(self)
        self._debounce_a.setSingleShot(True)
        self._debounce_a.setInterval(150)
        self._debounce_a.timeout.connect(self._trigger_render_a)

        self._debounce_b = QTimer(self)
        self._debounce_b.setSingleShot(True)
        self._debounce_b.setInterval(150)
        self._debounce_b.timeout.connect(self._trigger_render_b)

        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._build_ui()
        QApplication.instance().installEventFilter(self)

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
        self._before_pane.image_view.fit_requested.connect(self._on_fit_requested)
        self._splitter.addWidget(self._before_pane)

        self._effects_bar_a = _EffectsBar(copy.copy(self._base_settings))
        self._effects_bar_a.settings_changed.connect(self._on_after_a_changed)
        self._after_a_pane = _Pane("After-A", self._effects_bar_a)
        self._after_a_pane.image_view.view_changed.connect(self._on_view_changed)
        self._after_a_pane.image_view.fit_requested.connect(self._on_fit_requested)
        self._splitter.addWidget(self._after_a_pane)

        self._effects_bar_b = _EffectsBar(copy.copy(self._base_settings))
        self._effects_bar_b.settings_changed.connect(self._on_after_b_changed)
        self._after_b_pane = _Pane("After-B", self._effects_bar_b)
        self._after_b_pane.image_view.view_changed.connect(self._on_view_changed)
        self._after_b_pane.image_view.fit_requested.connect(self._on_fit_requested)
        self._splitter.addWidget(self._after_b_pane)

        for i in range(3):
            self._splitter.setStretchFactor(i, 1)

        root.addWidget(self._splitter, 1)  # stretch=1 so splitter fills all available height

        # Action button bar — wrapped in a container widget for distinct background
        action_widget = QWidget()
        action_widget.setObjectName("preview-action-bar")
        action_widget.setStyleSheet(
            "#preview-action-bar {"
            "  background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            "    stop:0 #1a2d4a, stop:1 #0f1e33);"
            "  border-top: 1px solid rgba(100,160,255,0.18);"
            "  border-radius: 0px;"
            "}"
        )
        action_bar = QHBoxLayout(action_widget)
        action_bar.setContentsMargins(8, 6, 8, 6)
        action_bar.setSpacing(6)

        def _btn(label: str, shortcut: str, callback) -> QPushButton:
            btn = QPushButton(f"{label}\n[{shortcut}]")
            btn.setFixedHeight(44)
            btn.clicked.connect(callback)
            return btn

        action_bar.addStretch()

        self._prev_btn = _btn("이전", "←", self._go_prev)
        action_bar.addWidget(self._prev_btn)

        action_bar.addWidget(_btn("1 선택", "1", self._on_save_1))
        action_bar.addWidget(_btn("2 선택", "2", self._on_save_2))
        action_bar.addWidget(_btn("3 선택", "3", self._on_save_3))

        del_btn = _btn("원본 삭제", "Del", self._on_delete)
        del_btn.setObjectName("delete-btn")
        action_bar.addWidget(del_btn)

        exif_btn = QPushButton("EXIF\n[E]")
        exif_btn.setFixedHeight(44)
        exif_btn.setCheckable(True)
        exif_btn.toggled.connect(self._toggle_exif)
        action_bar.addWidget(exif_btn)

        self._next_btn = _btn("다음", "→", self._go_next)
        action_bar.addWidget(self._next_btn)

        action_bar.addStretch()

        root.addWidget(action_widget)

        status_bar = QStatusBar()
        self.setStatusBar(status_bar)
        hint = QLabel("1:Before저장(리사이즈만)  2:After-A저장  3:After-B저장  Del:원본삭제  `/←:이전  4/→:다음  E:EXIF  Home:화면맞춤")
        hint.setObjectName("hint-label")
        status_bar.addWidget(hint)

    # ------------------------------------------------------------------
    # Show / resize events
    # ------------------------------------------------------------------

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0.0, QColor("#0d1117"))
        gradient.setColorAt(0.5, QColor("#161b22"))
        gradient.setColorAt(1.0, QColor("#1c2333"))
        painter.fillRect(self.rect(), gradient)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if self._first_show:
            self._first_show = False
            self._load_current()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        # Use a deferred call so child widgets have been resized before we read their sizes
        if not self._user_has_zoomed:
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
        t_total = time.perf_counter()
        photo = self._photos[self._index]
        total = len(self._photos)
        self.setWindowTitle(f"미리보기  {self._index + 1}/{total}  —  {photo.source_path.name}")
        self._prev_btn.setEnabled(self._index > 0)
        self._next_btn.setEnabled(self._index < total - 1)

        self._user_has_zoomed = False

        # Try prefetch cache first; fall back to synchronous load
        cached = self._prefetch.get(photo.source_path)
        if cached is not None:
            self._cached_image, self._cached_preview = cached
            logger.debug("[_load_current] cache HIT  (%s)", photo.source_path.name)
        else:
            try:
                t0 = time.perf_counter()
                self._cached_image = _open_image(photo.source_path)
                logger.debug("[_load_current] Image.open %.1f ms  (%s)",
                             (time.perf_counter() - t0) * 1000, photo.source_path.name)

                t0 = time.perf_counter()
                self._cached_preview = self._make_preview_image(self._cached_image)
                logger.debug("[_load_current] downsample %.1f ms  (%dx%d → %dx%d)",
                             (time.perf_counter() - t0) * 1000,
                             self._cached_image.width, self._cached_image.height,
                             self._cached_preview.width, self._cached_preview.height)
            except OSError as exc:
                logger.warning("[_load_current] cannot load %s: %s", photo.source_path.name, exc)
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.warning(
                    self,
                    "이미지 로드 실패",
                    f"{photo.source_path.name}\n\n손상된 이미지 파일입니다:\n{exc}",
                )
                return

        t0 = time.perf_counter()
        self._exif_bar.update_photo(photo.source_path)
        logger.debug("[_load_current] EXIF read %.1f ms",
                     (time.perf_counter() - t0) * 1000)

        t0 = time.perf_counter()
        self._render_before(photo)
        logger.debug("[_load_current] render_before %.1f ms",
                     (time.perf_counter() - t0) * 1000)

        # Kick off background renders for both After panes
        self._trigger_render_a()
        self._trigger_render_b()

        # Defer fit so the event loop has processed the new pixmaps
        QTimer.singleShot(0, self._force_fit_all)

        if self._exif_panel and self._exif_panel.isVisible():
            self._exif_panel.update_photo(
                photo.source_path, index=self._index + 1, total=len(self._photos)
            )

        logger.info("[_load_current] TOTAL %.1f ms  (%s)",
                    (time.perf_counter() - t_total) * 1000, photo.source_path.name)

        # Prefetch adjacent photos in background
        self._prefetch_adjacent()

    _PREVIEW_MAX_PX = 1600  # long-side cap for preview effects

    @classmethod
    def _make_preview_image(cls, img: Image.Image) -> Image.Image:
        """Downsample to _PREVIEW_MAX_PX on the long side for fast effects."""
        w, h = img.size
        long_side = max(w, h)
        if long_side <= cls._PREVIEW_MAX_PX:
            return img
        ratio = cls._PREVIEW_MAX_PX / long_side
        new_size = (max(1, int(w * ratio)), max(1, int(h * ratio)))
        return img.resize(new_size, Image.Resampling.LANCZOS)

    def _prefetch_adjacent(self) -> None:
        """Request background loading of prev/next photos."""
        targets: list[Path] = [self._photos[self._index].source_path]
        if self._index + 1 < len(self._photos):
            targets.append(self._photos[self._index + 1].source_path)
        if self._index - 1 >= 0:
            targets.append(self._photos[self._index - 1].source_path)
        self._prefetch.prefetch(targets)

    def _render_before(self, photo: PhotoItem) -> None:
        try:
            src = self._cached_preview if self._cached_preview is not None else self._cached_image
            if src is not None:
                self._before_pane.set_pixmap(self._pil_to_pixmap(src))
            else:
                self._before_pane.set_pixmap(self._pil_to_pixmap(_open_image(photo.source_path)))
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

    def _on_fit_requested(self) -> None:
        self._user_has_zoomed = False
        self._force_fit_all()

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
    # After pane re-render (debounced + background thread)
    # ------------------------------------------------------------------

    def _on_after_a_changed(self) -> None:
        self._debounce_a.start()

    def _on_after_b_changed(self) -> None:
        self._debounce_b.start()

    def _trigger_render_a(self) -> None:
        if not self._photos:
            return
        self._render_seq_a += 1
        seq = self._render_seq_a
        settings = copy.copy(self._effects_bar_a.settings())
        settings.resize_enabled = False
        photo = self._photos[self._index]
        source = self._cached_preview or self._cached_image
        worker = _RenderWorker(photo, settings, source, "a", seq)
        worker.signals.done.connect(self._on_render_done)
        QThreadPool.globalInstance().start(worker)

    def _trigger_render_b(self) -> None:
        if not self._photos:
            return
        self._render_seq_b += 1
        seq = self._render_seq_b
        settings = copy.copy(self._effects_bar_b.settings())
        settings.resize_enabled = False
        photo = self._photos[self._index]
        source = self._cached_preview or self._cached_image
        worker = _RenderWorker(photo, settings, source, "b", seq)
        worker.signals.done.connect(self._on_render_done)
        QThreadPool.globalInstance().start(worker)

    def _on_render_done(self, pixmap, pane_id: str, seq: int) -> None:
        # Discard result if a newer render has been requested
        if pane_id == "a":
            if seq < self._render_seq_a:
                return
            self._after_a_pane.set_pixmap(pixmap)
        else:
            if seq < self._render_seq_b:
                return
            self._after_b_pane.set_pixmap(pixmap)
        # Async render may land after _force_fit_all() already ran against
        # stale (previous photo) pixmap dimensions — refit once the new
        # pixmap is in place, unless the user has manually zoomed/panned.
        if not self._user_has_zoomed:
            self._force_fit_all()

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
        t_total = time.perf_counter()
        try:
            t0 = time.perf_counter()
            img = processor.process(photo, settings, apply_effects=apply_effects)
            logger.debug("[save] process %.1f ms", (time.perf_counter() - t0) * 1000)

            out_path = self._resolve_output_path(photo, settings)
            out_path.parent.mkdir(parents=True, exist_ok=True)

            t0 = time.perf_counter()
            processor.save(img, out_path, settings, photo.source_path)
            logger.debug("[save] write %.1f ms", (time.perf_counter() - t0) * 1000)

            self.photo_saved.emit(photo)
            self._saved_count += 1
        except Exception as e:
            self.statusBar().showMessage(f"저장 실패: {e}", 3000)
            return
        logger.info("[save] TOTAL %.1f ms  (%s)",
                    (time.perf_counter() - t_total) * 1000, photo.source_path.name)
        self._advance()

    def _advance(self) -> None:
        if self._index < len(self._photos) - 1:
            self._index += 1
            self._load_current()
        else:
            total = len(self._photos)
            QMessageBox.information(
                self,
                "미리보기 완료",
                f"모든 사진을 검토했습니다.\n\n전체 {total}개 중 {self._saved_count}개가 저장되었습니다.",
            )

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
    # Window close
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:  # noqa: N802
        self._prefetch.clear()
        QApplication.instance().removeEventFilter(self)
        super().closeEvent(event)

    # ------------------------------------------------------------------
    # Event filter — route child-widget key events to this window
    # ------------------------------------------------------------------

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        if (
            event.type() == QEvent.Type.KeyPress
            and isinstance(obj, QWidget)
            and obj is not self
            and self.isAncestorOf(obj)
        ):
            key = event.key()
            # E / Home: no conflict with any child widget → always intercept
            if key in (Qt.Key.Key_E, Qt.Key.Key_Home):
                self.keyPressEvent(event)
                return True
            # Nav keys: always intercept (slider is adjusted via mouse/wheel, not keyboard)
            if key in (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_QuoteLeft):
                self.keyPressEvent(event)
                return True
            # 1/2/3/4 / Space / Del: let QSpinBox type-input pass through; intercept from all others
            if key in (
                Qt.Key.Key_1, Qt.Key.Key_2, Qt.Key.Key_3, Qt.Key.Key_4,
                Qt.Key.Key_Space, Qt.Key.Key_Delete,
            ):
                if not isinstance(obj, QSpinBox):
                    self.keyPressEvent(event)
                    return True
        return super().eventFilter(obj, event)

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
        elif key == Qt.Key.Key_Space:
            self._on_skip()
        elif key in (Qt.Key.Key_QuoteLeft, Qt.Key.Key_Left):
            self._go_prev()
        elif key in (Qt.Key.Key_4, Qt.Key.Key_Right):
            self._go_next()
        elif key == Qt.Key.Key_Delete:
            self._on_delete()
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
        elif key == Qt.Key.Key_Home:
            self._user_has_zoomed = False
            self._force_fit_all()
        else:
            super().keyPressEvent(event)
