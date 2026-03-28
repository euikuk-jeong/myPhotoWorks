"""ThumbnailPanel — scrollable photo list with async thumbnail generation."""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QRunnable, QSize, Qt, QThreadPool, pyqtSignal
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import QListWidget, QListWidgetItem

from myphotoworks.models.photo_item import PhotoItem, ProcessStatus

THUMBNAIL_SIZE = 80
SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp"}


class _ThumbnailLoader(QRunnable):
    """Background runnable that generates a thumbnail for one PhotoItem."""

    def __init__(self, item: QListWidgetItem, photo: PhotoItem) -> None:
        super().__init__()
        self._list_item = item
        self._photo = photo

    def run(self) -> None:
        try:
            from PIL import Image
            with Image.open(self._photo.source_path) as img:
                img.thumbnail((THUMBNAIL_SIZE, THUMBNAIL_SIZE), Image.Resampling.LANCZOS)
                img = img.convert("RGB")
                data = img.tobytes("raw", "RGB")
                from PyQt6.QtGui import QImage
                qimg = QImage(data, img.width, img.height, img.width * 3,
                              QImage.Format.Format_RGB888)
                pixmap = QPixmap.fromImage(qimg)
                self._list_item.setIcon(QIcon(pixmap))
        except Exception:
            pass


class ThumbnailPanel(QListWidget):
    """QListWidget showing photo thumbnails.

    Signals
    -------
    photo_selected(PhotoItem)
        Emitted when a thumbnail is single-clicked.
    photo_double_clicked(PhotoItem)
        Emitted when a thumbnail is double-clicked (open preview).
    """

    photo_selected = pyqtSignal(object)
    photo_double_clicked = pyqtSignal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setIconSize(QSize(THUMBNAIL_SIZE, THUMBNAIL_SIZE))
        self.setViewMode(QListWidget.ViewMode.IconMode)
        self.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.setSpacing(4)
        self.setDragDropMode(QListWidget.DragDropMode.DropOnly)
        self.setAcceptDrops(True)
        self.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)

        self._photos: list[PhotoItem] = []
        self._pool = QThreadPool.globalInstance()

        self.currentRowChanged.connect(self._on_row_changed)
        self.itemDoubleClicked.connect(self._on_double_clicked)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_photos(self, paths: list[Path]) -> None:
        """Add new photos (skip duplicates and unsupported formats)."""
        existing = {p.source_path for p in self._photos}
        for path in paths:
            if path.suffix.lower() not in SUPPORTED_EXTS:
                continue
            if path in existing:
                continue
            photo = PhotoItem(source_path=path)
            self._photos.append(photo)
            self._add_list_item(photo)

    def remove_selected(self) -> None:
        """Remove currently selected photos from the list."""
        selected_rows = sorted(
            {self.row(item) for item in self.selectedItems()}, reverse=True
        )
        for row in selected_rows:
            if 0 <= row < len(self._photos):
                self._photos.pop(row)
                self.takeItem(row)

    def clear_all(self) -> None:
        self._photos.clear()
        self.clear()

    def current_photo(self) -> PhotoItem | None:
        row = self.currentRow()
        if 0 <= row < len(self._photos):
            return self._photos[row]
        return None

    def photos(self) -> list[PhotoItem]:
        return list(self._photos)

    def update_status(self, photo: PhotoItem) -> None:
        """Refresh the status badge text for the given photo."""
        for i, p in enumerate(self._photos):
            if p.source_path == photo.source_path:
                item = self.item(i)
                if item:
                    item.setText(self._status_label(photo))
                break

    # ------------------------------------------------------------------
    # Drag-and-drop
    # ------------------------------------------------------------------

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

    def _add_list_item(self, photo: PhotoItem) -> None:
        item = QListWidgetItem(photo.source_path.name)
        item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom)
        item.setSizeHint(QSize(THUMBNAIL_SIZE + 20, THUMBNAIL_SIZE + 24))
        self.addItem(item)
        loader = _ThumbnailLoader(item, photo)
        self._pool.start(loader)

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
        if 0 <= row < len(self._photos):
            self.photo_selected.emit(self._photos[row])

    def _on_double_clicked(self, item: QListWidgetItem) -> None:
        row = self.row(item)
        if 0 <= row < len(self._photos):
            self.photo_double_clicked.emit(self._photos[row])
