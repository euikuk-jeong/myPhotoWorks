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
    QPointF,
    QRect,
    QRectF,
    QRunnable,
    QSize,
    Qt,
    QThreadPool,
    pyqtSignal,
)
from PyQt6.QtGui import QColor, QIcon, QImage, QPainter, QPainterPath, QPen, QPixmap
from PyQt6.QtWidgets import (
    QListWidget,
    QListWidgetItem,
    QMenu,
    QStyledItemDelegate,
    QStyleOptionViewItem,
)

from myphotoworks.models.photo_item import PhotoItem, ProcessStatus
from myphotoworks.ui.styles import tokens

THUMB_BOX = QSize(168, 112)   # 3:2 display box; portrait photos fit its height
CARD_PAD = 12                 # room around the photo for the adoption loop
CARD_TEXT_H = 22              # filename line under the photo
SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp"}

_PHOTO_ROLE = Qt.ItemDataRole.UserRole
_ACCENT = QColor(tokens.PICK)
_STAR = QColor(tokens.PICK)
_LOOP_OUTSET = 7              # how far the adoption loop sits outside the photo


def checkbox_rect(photo_rect: QRect) -> QRect:
    """Hit/paint area of the adoption checkbox: the photo's top-right corner."""
    return QRect(photo_rect.right() - 23, photo_rect.top() + 5, 18, 18)


def pick_loop_path(photo_rect: QRectF) -> QPainterPath:
    """A hand-drawn china-marker loop around ``photo_rect`` (stays within the outset).

    The start overshoots slightly past the end, like a real pencil loop.
    """
    r = QRectF(photo_rect).adjusted(-_LOOP_OUTSET, -_LOOP_OUTSET, _LOOP_OUTSET, _LOOP_OUTSET)
    x, y, w, h = r.x(), r.y(), r.width(), r.height()

    def p(fx: float, fy: float) -> QPointF:
        return QPointF(x + fx * w, y + fy * h)

    path = QPainterPath(p(0.07, 0.10))
    path.cubicTo(p(0.30, 0.02), p(0.70, 0.00), p(0.95, 0.06))
    path.cubicTo(p(1.00, 0.30), p(1.00, 0.65), p(0.96, 0.92))
    path.cubicTo(p(0.70, 1.00), p(0.30, 0.99), p(0.05, 0.93))
    path.cubicTo(p(0.00, 0.65), p(0.00, 0.33), p(0.04, 0.09))
    path.cubicTo(p(0.07, 0.04), p(0.12, 0.03), p(0.18, 0.03))
    return path


def status_badge(status: ProcessStatus) -> tuple[str, str] | None:
    """Badge (text, colour token) shown on a card for a batch status; None when pending."""
    return {
        ProcessStatus.PROCESSING: ("처리중", tokens.TEXT_MUTED),
        ProcessStatus.DONE: ("완료", tokens.OK),
        ProcessStatus.ERROR: ("오류", tokens.DANGER),
    }.get(status)


def status_badge_rect(photo_rect: QRect, text_width: int, blur_shown: bool) -> QRect:
    """Status badge at the photo's bottom-left; one row higher when the blur badge is there.

    The width follows the text so it stays clear of the bottom-right score badge
    on narrow portrait photos.
    """
    bottom = photo_rect.bottom() - (39 if blur_shown else 21)
    return QRect(photo_rect.left() + 5, bottom, max(32, text_width + 12), 16)


class _LoaderSignals(QObject):
    loaded = pyqtSignal(str, QImage, int, int)   # path, thumbnail, original width, height


class _ThumbnailLoader(QRunnable):
    """Background runnable that decodes a thumbnail QImage for one photo."""

    def __init__(self, path: Path, signals: _LoaderSignals, box: QSize) -> None:
        super().__init__()
        self._path = path
        self._signals = signals
        self._box = (box.width(), box.height())

    def run(self) -> None:
        try:
            from PIL import Image, ImageOps

            with Image.open(self._path) as img:
                img = ImageOps.exif_transpose(img)
                width, height = img.size
                img.thumbnail(self._box, Image.Resampling.LANCZOS)
                img = img.convert("RGB")
                data = img.tobytes("raw", "RGB")
                qimg = QImage(
                    data, img.width, img.height, img.width * 3, QImage.Format.Format_RGB888
                ).copy()  # detach from the Python buffer
            self._signals.loaded.emit(str(self._path), qimg, width, height)
        except Exception:
            pass


class _CardDelegate(QStyledItemDelegate):
    """Paints the adoption loop, checkbox, recommendation star and badges over a card.

    Everything is placed relative to the photo's actual rect (portrait photos are
    narrower than the 3:2 box) and kept inside the item rect, so repaints leave no trails.
    """

    def __init__(self, panel: ThumbnailPanel) -> None:
        super().__init__(panel)
        self._panel = panel

    def photo_rect(self, item_rect: QRect, index) -> QRect:
        """Rect the thumbnail pixmap actually occupies inside the item.

        Mirrors the ``#thumbGrid::item`` box model (1px border + CARD_PAD top padding,
        icon box centred horizontally). Computed by hand on purpose: copying the
        QStyleOptionViewItem in Python and asking the style crashed under GC.
        """
        box = self._panel.iconSize()
        top = item_rect.top() + 1 + CARD_PAD
        left = item_rect.left() + (item_rect.width() - box.width()) // 2
        icon = index.data(Qt.ItemDataRole.DecorationRole)
        size = icon.actualSize(box) if isinstance(icon, QIcon) and not icon.isNull() else box
        # IconMode centres the pixmap horizontally but pins it to the top of the box
        # (visible with a landscape photo in the review strip's square box)
        return QRect(left + (box.width() - size.width()) // 2, top, size.width(), size.height())

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        super().paint(painter, option, index)
        photo = index.data(_PHOTO_ROLE)
        if photo is None:
            return
        r = self.photo_rect(option.rect, index)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        status = status_badge(photo.status)
        if status is not None:
            text, color = status
            blur_shown = self._panel.grouping_active and "흐림" in photo.reason
            badge = status_badge_rect(
                r, painter.fontMetrics().horizontalAdvance(text), blur_shown
            )
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(tokens.color(color, 230))
            painter.drawRoundedRect(badge, 4, 4)
            painter.setPen(QColor(tokens.ON_PRIMARY))
            painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, text)
        if not self._panel.grouping_active:
            painter.restore()
            return
        if photo.is_adopted:
            pen = QPen(_ACCENT, 2.4)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(pick_loop_path(QRectF(r)))

        box = QRectF(checkbox_rect(r))
        if photo.is_adopted:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(_ACCENT)
        else:
            painter.setPen(QPen(tokens.color(tokens.TEXT_STRONG, 220), 1.4))
            painter.setBrush(tokens.color(tokens.SUNKEN, 150))
        painter.drawEllipse(box)
        if photo.is_adopted:
            check = QPen(QColor(tokens.ON_PRIMARY), 2)
            check.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(check)
            x, y = box.left(), box.top()
            painter.drawPolyline([QPointF(x + 5, y + 9.5), QPointF(x + 8, y + 12.5),
                                  QPointF(x + 13, y + 6.5)])

        if photo.is_recommended:
            font = painter.font()
            font.setPointSize(12)
            star = QPainterPath()
            star.addText(QPointF(r.left() + 6, r.top() + 19), font, "★")
            painter.setPen(QPen(tokens.color(tokens.SUNKEN, 200), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(star)
            painter.fillPath(star, _STAR)

        if self._panel.show_score and photo.scores is not None:
            from myphotoworks.core.scoring import composite

            text = str(round(composite(photo.scores, self._panel.weights)))
            badge = QRect(r.right() - 31, r.bottom() - 21, 26, 16)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(tokens.color(tokens.SUNKEN, 200))
            painter.drawRoundedRect(badge, 4, 4)
            painter.setPen(QColor(tokens.TEXT))
            painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, text)

        if "흐림" in photo.reason:
            badge = QRect(r.left() + 5, r.bottom() - 21, 32, 16)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(tokens.color(tokens.WARN, 230))
            painter.drawRoundedRect(badge, 4, 4)
            painter.setPen(QColor(tokens.ON_PRIMARY))
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
    current_size_loaded(PhotoItem)
        The current photo's thumbnail (and so its pixel size) finished loading.
    """

    photo_selected = pyqtSignal(object)
    current_size_loaded = pyqtSignal(object)
    photo_double_clicked = pyqtSignal(object)
    show_info_requested = pyqtSignal()
    adoption_toggle_requested = pyqtSignal(object, bool)
    photos_added = pyqtSignal(list)
    photos_removed = pyqtSignal(list)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setIconSize(THUMB_BOX)
        self.setViewMode(QListWidget.ViewMode.IconMode)
        self.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.setMovement(QListWidget.Movement.Static)
        self.setSpacing(4)
        self.setObjectName("thumbGrid")  # card padding in light_table.qss
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
        self._sizes: dict[str, tuple[int, int]] = {}   # original (width, height) per path
        self._signals = _LoaderSignals()
        self._signals.loaded.connect(self._on_thumbnail_loaded)

        # grouping display state
        self._session = None
        self._grouped_view = False
        self._adopted_only = False
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

    def image_size(self, photo: PhotoItem) -> tuple[int, int] | None:
        """Original (width, height) once the thumbnail has loaded, else None."""
        return self._sizes.get(str(photo.source_path))

    def photos(self) -> list[PhotoItem]:
        """The displayed list — this is also what preview / batch processing act on."""
        return [p for p in self._rows if p is not None]

    def update_status(self, photo: PhotoItem) -> None:
        """Repaint the given photo's card so its status badge follows ``photo.status``."""
        for i, p in enumerate(self._rows):
            if p is not None and p.source_path == photo.source_path:
                item = self.item(i)
                if item:
                    self.viewport().update(self.visualItemRect(item))
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
            yield "header", f"단독 사진 · {len(singles):,}장"
            for p in singles:
                yield "photo", p

    def _group_title(self, group, shown: int) -> str:
        n = len(group.photos)
        title = f"그룹 {self._group_number(group.id):,} · {n:,}장"
        if shown != n:
            title += f" 중 {shown:,}장 표시"
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
        item.setSizeHint(QSize(THUMB_BOX.width() + 2 * CARD_PAD,
                               THUMB_BOX.height() + CARD_PAD + CARD_TEXT_H + 4))
        item.setData(_PHOTO_ROLE, photo)
        if self._session is not None and photo.reason:
            item.setToolTip(photo.reason)
        icon = self._icons.get(str(photo.source_path))
        if icon is not None:
            item.setIcon(icon)
        else:
            self._pool.start(_ThumbnailLoader(photo.source_path, self._signals, self._load_box()))
        self.addItem(item)
        self._rows.append(photo)

    def _header_width(self) -> int:
        return max(200, self.viewport().width() - 24)

    def _load_box(self) -> QSize:
        """Decode size: the display box scaled to the screen so HiDPI stays sharp."""
        ratio = self.devicePixelRatioF()
        return QSize(round(THUMB_BOX.width() * ratio), round(THUMB_BOX.height() * ratio))

    def _on_thumbnail_loaded(self, path: str, image: QImage, width: int, height: int) -> None:
        pixmap = QPixmap.fromImage(image)
        pixmap.setDevicePixelRatio(self.devicePixelRatioF())
        icon = QIcon(pixmap)
        self._icons[path] = icon
        self._sizes[path] = (width, height)
        for i, p in enumerate(self._rows):
            if p is not None and str(p.source_path) == path:
                item = self.item(i)
                if item is not None:
                    item.setIcon(icon)
        current = self.current_photo()
        if current is not None and str(current.source_path) == path:
            self.current_size_loaded.emit(current)

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

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        if self.count() == 0:
            painter = QPainter(self.viewport())
            painter.setPen(QColor(tokens.TEXT_MUTED))
            painter.drawText(self.viewport().rect(), Qt.AlignmentFlag.AlignCenter,
                             "사진을 여기로 끌어다 놓거나 파일 추가를 누르세요.")

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if self._session is not None and event.button() == Qt.MouseButton.LeftButton:
            index = self.indexAt(event.position().toPoint())
            if index.isValid():
                photo = index.data(_PHOTO_ROLE)
                rect = self.itemDelegate().photo_rect(self.visualRect(index), index)
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
