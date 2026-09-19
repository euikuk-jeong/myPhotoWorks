"""ThumbnailPanel — scrollable photo list with async thumbnail generation.

Besides the plain list it can show grouping results: adoption checkboxes, recommendation
stars, score badges, group headers ("그룹별 보기") and an "adopted only" filter. The panel
never owns grouping state — it renders a GroupSession handed to it and reports user
intent through signals.
"""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import (
    QObject,
    QPoint,
    QRect,
    QRunnable,
    QSize,
    Qt,
    QThreadPool,
    pyqtSignal,
)
from PyQt6.QtGui import QColor, QIcon, QImage, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import (
    QListWidget,
    QListWidgetItem,
    QMenu,
    QStyledItemDelegate,
    QStyleOptionViewItem,
)

from myphotoworks.models.photo_item import PhotoItem, ProcessStatus

THUMBNAIL_SIZE = 80
SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp"}

_PHOTO_ROLE = Qt.ItemDataRole.UserRole
_ACCENT = QColor("#58a6ff")
_STAR = QColor("#f5c451")


def checkbox_rect(item_rect: QRect) -> QRect:
    return QRect(item_rect.right() - 22, item_rect.top() + 4, 18, 18)


class _LoaderSignals(QObject):
    loaded = pyqtSignal(str, QImage)


class _ThumbnailLoader(QRunnable):
    """Background runnable that decodes a thumbnail QImage for one photo."""

    def __init__(self, path: Path, signals: _LoaderSignals) -> None:
        super().__init__()
        self._path = path
        self._signals = signals

    def run(self) -> None:
        try:
            from PIL import Image, ImageOps

            with Image.open(self._path) as img:
                img = ImageOps.exif_transpose(img)
                img.thumbnail((THUMBNAIL_SIZE, THUMBNAIL_SIZE), Image.Resampling.LANCZOS)
                img = img.convert("RGB")
                data = img.tobytes("raw", "RGB")
                qimg = QImage(
                    data, img.width, img.height, img.width * 3, QImage.Format.Format_RGB888
                ).copy()  # detach from the Python buffer
            self._signals.loaded.emit(str(self._path), qimg)
        except Exception:
            pass


class _CardDelegate(QStyledItemDelegate):
    """Paints adoption border, star, checkbox and score badge over a thumbnail card."""

    def __init__(self, panel: ThumbnailPanel) -> None:
        super().__init__(panel)
        self._panel = panel

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        super().paint(painter, option, index)
        photo = index.data(_PHOTO_ROLE)
        if photo is None or not self._panel.grouping_active:
            return
        r = option.rect
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if photo.is_adopted:
            painter.setPen(QPen(_ACCENT, 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(r.adjusted(1, 1, -1, -1), 6, 6)

        box = checkbox_rect(r)
        painter.setPen(QPen(QColor("#e6edf3"), 1))
        painter.setBrush(_ACCENT if photo.is_adopted else QColor(13, 17, 23, 180))
        painter.drawRoundedRect(box, 3, 3)
        if photo.is_adopted:
            painter.setPen(QPen(QColor("#0d1117"), 2))
            painter.drawLine(box.left() + 4, box.center().y(), box.left() + 7, box.bottom() - 4)
            painter.drawLine(box.left() + 7, box.bottom() - 4, box.right() - 3, box.top() + 4)

        if photo.is_recommended:
            base_font = painter.font()
            star_font = painter.font()
            star_font.setPointSize(13)
            painter.setFont(star_font)
            painter.setPen(_STAR)
            painter.drawText(r.left() + 6, r.top() + 20, "★")
            painter.setFont(base_font)

        if self._panel.show_score and photo.scores is not None:
            from myphotoworks.core.scoring import composite

            text = str(round(composite(photo.scores, self._panel.weights)))
            badge = QRect(r.right() - 30, r.top() + self._panel.icon_px - 8, 26, 16)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(13, 17, 23, 205))
            painter.drawRoundedRect(badge, 4, 4)
            painter.setPen(QColor("#e6edf3"))
            painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, text)

        if "흐림" in photo.reason:
            badge = QRect(r.left() + 6, r.top() + self._panel.icon_px - 8, 32, 16)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(210, 153, 34, 230))
            painter.drawRoundedRect(badge, 4, 4)
            painter.setPen(QColor("#0d1117"))
            painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, "흐림")
        painter.restore()


class ThumbnailPanel(QListWidget):
    """QListWidget showing photo thumbnails.

    Signals
    -------
    photo_selected(PhotoItem)
        Emitted when a thumbnail is single-clicked.
    photo_double_clicked(PhotoItem)
        Emitted when a thumbnail is double-clicked (open preview).
    adoption_toggle_requested(PhotoItem, bool)
        User clicked a card checkbox (or pressed Space) — value is the requested new state.
    photos_added(list) / photos_removed(list)
        Photos were added to / removed from the list.
    """

    photo_selected = pyqtSignal(object)
    photo_double_clicked = pyqtSignal(object)
    show_info_requested = pyqtSignal()
    adoption_toggle_requested = pyqtSignal(object, bool)
    photos_added = pyqtSignal(list)
    photos_removed = pyqtSignal(list)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setIconSize(QSize(THUMBNAIL_SIZE, THUMBNAIL_SIZE))
        self.setViewMode(QListWidget.ViewMode.IconMode)
        self.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.setSpacing(4)
        self.setDragDropMode(QListWidget.DragDropMode.DropOnly)
        self.setAcceptDrops(True)
        self.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_context_menu)
        self.setItemDelegate(_CardDelegate(self))

        self._photos: list[PhotoItem] = []      # every loaded photo, load order
        self._rows: list[PhotoItem | None] = []  # list rows; None = group header
        self._pool = QThreadPool.globalInstance()
        self._icons: dict[str, QIcon] = {}
        self._signals = _LoaderSignals()
        self._signals.loaded.connect(self._on_thumbnail_loaded)

        # grouping display state
        self._session = None
        self._grouped_view = False
        self._adopted_only = False
        self.icon_px = THUMBNAIL_SIZE
        self.show_score = True
        self.show_reason = True
        self.weights = (0.5, 0.3, 0.2)

        self.currentRowChanged.connect(self._on_row_changed)
        self.itemDoubleClicked.connect(self._on_double_clicked)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def grouping_active(self) -> bool:
        return self._session is not None

    def add_photos(self, paths: list[Path]) -> None:
        """Add new photos (skip duplicates and unsupported formats)."""
        existing = {p.source_path for p in self._photos}
        added: list[PhotoItem] = []
        for path in paths:
            if path.suffix.lower() not in SUPPORTED_EXTS:
                continue
            if path in existing:
                continue
            item = PhotoItem(source_path=path)
            self._photos.append(item)
            added.append(item)
        if added:
            self.rebuild()
            self.photos_added.emit(added)

    def remove_selected(self) -> None:
        """Remove currently selected photos from the list."""
        doomed = {
            id(self._rows[self.row(item)]) for item in self.selectedItems()
            if self._rows[self.row(item)] is not None
        }
        if not doomed:
            return
        removed = [p for p in self._photos if id(p) in doomed]
        self._photos = [p for p in self._photos if id(p) not in doomed]
        self.rebuild()
        self.photos_removed.emit(removed)

    def clear_all(self) -> None:
        removed = list(self._photos)
        self._photos.clear()
        self.rebuild()
        self.photos_removed.emit(removed)

    def current_photo(self) -> PhotoItem | None:
        row = self.currentRow()
        if 0 <= row < len(self._rows):
            return self._rows[row]
        return None

    def all_photos(self) -> list[PhotoItem]:
        return list(self._photos)

    def photos(self) -> list[PhotoItem]:
        """The displayed list — this is also what preview / batch processing act on."""
        return [p for p in self._rows if p is not None]

    def update_status(self, photo: PhotoItem) -> None:
        """Refresh the status badge text for the given photo."""
        for i, p in enumerate(self._rows):
            if p is not None and p.source_path == photo.source_path:
                item = self.item(i)
                if item:
                    item.setText(self._status_label(photo))
                break

    # ---- grouping display ------------------------------------------------

    def set_session(self, session) -> None:
        self._session = session
        self.rebuild()

    def set_view(self, grouped: bool, adopted_only: bool) -> None:
        self._grouped_view = grouped
        self._adopted_only = adopted_only
        self.rebuild()

    def set_options(self, show_reason: bool, show_score: bool, weights) -> None:
        self.show_reason, self.show_score, self.weights = show_reason, show_score, weights
        self.rebuild()

    def rebuild(self) -> None:
        """Re-create the rows from the current photos / session / view flags."""
        current = self.current_photo()
        self.blockSignals(True)
        self.clear()
        self._rows = []
        for kind, payload in self._layout():
            if kind == "header":
                self._add_header(payload)
            else:
                self._add_photo_item(payload)
        self.blockSignals(False)
        if current is not None:
            for i, p in enumerate(self._rows):
                if p is current:
                    self.setCurrentRow(i)
                    break
        self.viewport().update()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _layout(self):
        s = self._session
        if s is None:
            for p in self._photos:
                yield "photo", p
            return
        if not self._grouped_view:
            for p in self._photos:
                if p.is_adopted or not self._adopted_only:
                    yield "photo", p
            return
        singles: list[PhotoItem] = []
        for g in s.groups():
            shown = [p for p in g.photos if p.is_adopted or not self._adopted_only]
            if g.is_single:
                singles.extend(shown)
                continue
            if shown:
                yield "header", self._group_title(g, len(shown))
                for p in shown:
                    yield "photo", p
        if singles:
            yield "header", f"단독 사진 · {len(singles)}장"
            for p in singles:
                yield "photo", p

    def _group_title(self, group, shown: int) -> str:
        n = len(group.photos)
        title = f"그룹 {self._group_number(group.id)} · {n}장"
        if shown != n:
            title += f" 중 {shown}장 표시"
        times = sorted(
            p.analysis.taken for p in group.photos if p.analysis and p.analysis.taken
        )
        if times:
            a, b = times[0].strftime("%H:%M:%S"), times[-1].strftime("%H:%M:%S")
            title += f" · {a}" if a == b else f" · {a} – {b}"
        if self.show_reason:
            rec = next((p for p in group.photos if p.is_recommended), None)
            if rec is not None and rec.reason:
                title += f"   ★ {rec.reason}"
        return title

    def _group_number(self, gid: int) -> int:
        for k, g in enumerate(self._session.groups(), start=1):
            if g.id == gid:
                return k
        return gid

    def _add_header(self, text: str) -> None:
        item = QListWidgetItem(text)
        item.setFlags(Qt.ItemFlag.ItemIsEnabled)
        item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        item.setSizeHint(QSize(self._header_width(), 26))
        item.setData(_PHOTO_ROLE, None)
        self.addItem(item)
        self._rows.append(None)

    def _add_photo_item(self, photo: PhotoItem) -> None:
        item = QListWidgetItem(photo.source_path.name)
        item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom)
        item.setSizeHint(QSize(THUMBNAIL_SIZE + 20, THUMBNAIL_SIZE + 24))
        item.setData(_PHOTO_ROLE, photo)
        if self._session is not None and photo.reason:
            item.setToolTip(photo.reason)
        icon = self._icons.get(str(photo.source_path))
        if icon is not None:
            item.setIcon(icon)
        else:
            self._pool.start(_ThumbnailLoader(photo.source_path, self._signals))
        self.addItem(item)
        self._rows.append(photo)

    def _header_width(self) -> int:
        return max(200, self.viewport().width() - 24)

    def _on_thumbnail_loaded(self, path: str, image: QImage) -> None:
        icon = QIcon(QPixmap.fromImage(image))
        self._icons[path] = icon
        for i, p in enumerate(self._rows):
            if p is not None and str(p.source_path) == path:
                item = self.item(i)
                if item is not None:
                    item.setIcon(icon)

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        for i, p in enumerate(self._rows):
            if p is None:
                item = self.item(i)
                if item is not None:
                    item.setSizeHint(QSize(self._header_width(), 26))

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if self._session is not None and event.button() == Qt.MouseButton.LeftButton:
            index = self.indexAt(event.position().toPoint())
            if index.isValid():
                photo = index.data(_PHOTO_ROLE)
                rect = self.visualRect(index)
                if photo is not None and checkbox_rect(rect).contains(event.position().toPoint()):
                    self.adoption_toggle_requested.emit(photo, not photo.is_adopted)
                    return
        super().mousePressEvent(event)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if self._session is not None and event.key() == Qt.Key.Key_Space:
            photo = self.current_photo()
            if photo is not None:
                self.adoption_toggle_requested.emit(photo, not photo.is_adopted)
                return
        super().keyPressEvent(event)

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:  # noqa: N802
        paths = [Path(u.toLocalFile()) for u in event.mimeData().urls()]
        self.add_photos(paths)
        event.acceptProposedAction()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _status_label(photo: PhotoItem) -> str:
        labels = {
            ProcessStatus.PENDING: "",
            ProcessStatus.PROCESSING: "처리중",
            ProcessStatus.DONE: "완료",
            ProcessStatus.ERROR: "오류",
        }
        return labels.get(photo.status, "")

    def _on_row_changed(self, row: int) -> None:
        if 0 <= row < len(self._rows) and self._rows[row] is not None:
            self.photo_selected.emit(self._rows[row])

    def _on_double_clicked(self, item: QListWidgetItem) -> None:
        row = self.row(item)
        if 0 <= row < len(self._rows) and self._rows[row] is not None:
            self.photo_double_clicked.emit(self._rows[row])

    def _on_context_menu(self, pos: QPoint) -> None:
        item = self.itemAt(pos)
        if item is None:
            return
        menu = QMenu(self)
        info_action = menu.addAction("정보")
        action = menu.exec(self.viewport().mapToGlobal(pos))
        if action is info_action:
            self.show_info_requested.emit()
