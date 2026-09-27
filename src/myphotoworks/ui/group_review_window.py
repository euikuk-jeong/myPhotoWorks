"""GroupReviewWindow — compare photos per group, adopt several, edit groups, undo."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtCore import (
    QObject,
    QRect,
    QRectF,
    QRunnable,
    QSize,
    Qt,
    QThreadPool,
    QTimer,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QColor,
    QFont,
    QIcon,
    QImage,
    QKeySequence,
    QPainter,
    QPen,
    QPixmap,
    QShortcut,
)
from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QStyle,
    QStyledItemDelegate,
    QVBoxLayout,
    QWidget,
)

from myphotoworks.core.analysis_image import load_analysis_image
from myphotoworks.core.scoring import composite
from myphotoworks.models.group_session import (
    TAG_EDITED,
    TAG_REVIEWED,
    TAG_TODO,
    Group,
    GroupSession,
)
from myphotoworks.models.photo_item import PhotoItem
from myphotoworks.models.settings import AppSettings
from myphotoworks.processing.export import export_adopted
from myphotoworks.ui.styles import tokens
from myphotoworks.ui.thumbnail_panel import (
    _PHOTO_ROLE,
    _STAR,
    CARD_PAD,
    CARD_TEXT_H,
    _CardDelegate,
    checkbox_rect,
)
from myphotoworks.ui.zoom_view import ZoomPanView

STRIP_ICON = 130
STRIP_ROW_HEIGHT = STRIP_ICON + 52   # one row of cards incl. name and padding
PREVIEW_LONG_SIDE = 1000   # fitted preview
DETAIL_LONG_SIDE = 4000    # loaded on first zoom-in so detail is not blurry
DETAIL_CACHE = 3
GROUP_THUMB = 56
GROUP_ROW_HEIGHT = GROUP_THUMB + 16
GROUP_BAR_W = 72           # adoption ratio bar on each group card
_SUMMARY_ROLE = Qt.ItemDataRole.UserRole + 1
_TAG_COLORS = {TAG_TODO: QColor(tokens.WARN), TAG_REVIEWED: QColor(tokens.OK),
               TAG_EDITED: QColor(tokens.PRIMARY)}


def time_span(photos: list[PhotoItem]) -> str:
    """'HH:MM:SS' or 'HH:MM:SS – HH:MM:SS' of the capture times, '' when none are known."""
    times = sorted(p.analysis.taken for p in photos if p.analysis and p.analysis.taken)
    if not times:
        return ""
    a, b = times[0].strftime("%H:%M:%S"), times[-1].strftime("%H:%M:%S")
    return a if a == b else f"{a} – {b}"


@dataclass(frozen=True)
class GroupSummary:
    """What one card of the group list shows."""

    number: int
    count: int
    adopted: int
    span: str
    tag: str
    cover: PhotoItem   # recommended photo, else the first one

    @property
    def text(self) -> str:
        return f"그룹 {self.number:,} · {self.count:,}장 · 채택 {self.adopted:,}  [{self.tag}]"


def _group_step_key(event, signal) -> bool:
    """PageUp / PageDown move between groups instead of scrolling the list."""
    step = {Qt.Key.Key_PageUp: -1, Qt.Key.Key_PageDown: 1}.get(event.key())
    if step is None:
        return False
    signal.emit(step)
    return True


def adoption_bar_fill(width: float, adopted: int, count: int) -> float:
    """Filled length of a ``width``-long bar for ``adopted`` of ``count`` photos.

    Any adoption shows at least a sliver, so "1 of 50" is still visible.
    """
    if count <= 0 or adopted <= 0:
        return 0.0
    return max(4.0, width * min(adopted, count) / count)


def group_summary(session: GroupSession, group: Group, number: int) -> GroupSummary:
    cover = next((p for p in group.photos if p.is_recommended), group.photos[0])
    return GroupSummary(
        number=number,
        count=len(group.photos),
        adopted=sum(1 for p in group.photos if p.is_adopted),
        span=time_span(group.photos),
        tag=session.tag(group.id),
        cover=cover,
    )


def _pil_to_qimage(img) -> QImage:
    img = img.convert("RGB")
    return QImage(
        img.tobytes("raw", "RGB"), img.width, img.height, img.width * 3,
        QImage.Format.Format_RGB888,
    ).copy()


def _pil_to_pixmap(img) -> QPixmap:
    return QPixmap.fromImage(_pil_to_qimage(img))


class _DetailSignals(QObject):
    loaded = pyqtSignal(str, QImage)


class _DetailLoader(QRunnable):
    """Loads a large copy of one photo in the background (for zoomed-in inspection)."""

    def __init__(self, path: Path, signals: _DetailSignals) -> None:
        super().__init__()
        self._path = path
        self._signals = signals

    def run(self) -> None:
        try:
            image = _pil_to_qimage(load_analysis_image(self._path, DETAIL_LONG_SIDE))
        except Exception:
            return
        self._signals.loaded.emit(str(self._path), image)


class _GroupDelegate(QStyledItemDelegate):
    """Paints a group card: cover thumbnail, title, review tag, size/time and adoption dots."""

    def __init__(self, parent, thumb) -> None:
        super().__init__(parent)
        self._thumb = thumb  # PhotoItem -> QIcon, loaded lazily for visible cards only

    def sizeHint(self, option, index) -> QSize:  # noqa: N802
        return QSize(option.rect.width(), GROUP_ROW_HEIGHT)

    def paint(self, painter: QPainter, option, index) -> None:
        s: GroupSummary | None = index.data(_SUMMARY_ROLE)
        if s is None:
            super().paint(painter, option, index)
            return
        r = option.rect.adjusted(0, 2, -2, -2)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hover = bool(option.state & QStyle.StateFlag.State_MouseOver)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if selected or hover:
            painter.setPen(QPen(QColor(tokens.TEXT_MUTED), 1) if selected else Qt.PenStyle.NoPen)
            painter.setBrush(QColor(tokens.RAISED if selected else tokens.DIVIDER))
            painter.drawRoundedRect(QRectF(r).adjusted(0.5, 0.5, -0.5, -0.5), 6, 6)

        thumb = QRect(r.left() + 6, r.top() + (r.height() - GROUP_THUMB) // 2,
                      GROUP_THUMB, GROUP_THUMB)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(tokens.SUNKEN))
        painter.drawRoundedRect(thumb, 4, 4)
        self._thumb(s.cover).paint(painter, thumb)

        x = thumb.right() + 10
        right = r.right() - 8
        line_h = (r.height() - 8) // 3
        top = r.top() + 4

        # review tag: a coloured dot + muted text, quieter than a filled pill
        base = painter.font()
        tag_font = painter.font()
        tag_font.setPointSizeF(base.pointSizeF() * 0.9)
        painter.setFont(tag_font)
        tag_w = painter.fontMetrics().horizontalAdvance(s.tag)
        tag_rect = QRect(right - tag_w, top, tag_w, line_h)
        painter.setPen(QColor(tokens.TEXT_MUTED))
        painter.drawText(tag_rect, Qt.AlignmentFlag.AlignVCenter, s.tag)
        dot = 6
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(_TAG_COLORS.get(s.tag, QColor(tokens.TEXT_MUTED)))
        painter.drawEllipse(QRect(tag_rect.left() - dot - 5, tag_rect.center().y() - dot // 2,
                                  dot, dot))
        badge = tag_rect.adjusted(-dot - 5, 0, 0, 0)

        title = painter.font()
        title.setPointSizeF(base.pointSizeF())
        title.setWeight(QFont.Weight.DemiBold)
        painter.setFont(title)
        painter.setPen(QColor(tokens.TEXT_STRONG))
        painter.drawText(QRect(x, top, badge.left() - x - 4, line_h),
                         Qt.AlignmentFlag.AlignVCenter, f"그룹 {s.number:,}")

        painter.setFont(base)
        painter.setPen(QColor(tokens.TEXT_MUTED))
        info = f"{s.count:,}장" + (f" · {s.span}" if s.span else "")
        info = painter.fontMetrics().elidedText(info, Qt.TextElideMode.ElideRight, right - x)
        painter.drawText(QRect(x, top + line_h, right - x, line_h),
                         Qt.AlignmentFlag.AlignVCenter, info)

        adopted = f"채택 {s.adopted:,}/{s.count:,}"
        row = QRect(x, top + 2 * line_h, right - x, line_h)
        painter.setPen(QColor(tokens.PICK_TEXT) if s.adopted else QColor(tokens.TEXT_MUTED))
        painter.drawText(row, Qt.AlignmentFlag.AlignVCenter, adopted)
        # adoption ratio bar: same width whatever the group size
        bx = x + painter.fontMetrics().horizontalAdvance(adopted) + 10
        bw = min(GROUP_BAR_W, right - bx)
        if bw > 8:
            track = QRectF(bx, row.center().y() - 2, bw, 4)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(tokens.RAISED))
            painter.drawRoundedRect(track, 2, 2)
            fill = adoption_bar_fill(bw, s.adopted, s.count)
            if fill:
                painter.setBrush(_STAR)
                painter.drawRoundedRect(QRectF(bx, track.top(), fill, 4), 2, 2)
        painter.restore()


class _GroupList(QListWidget):
    """Group list that accepts photo cards dragged from the film strip."""

    photo_dropped = pyqtSignal(int)  # target group id
    group_step_requested = pyqtSignal(int)  # PageUp -1 / PageDown +1

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if not _group_step_key(event, self.group_step_requested):
            super().keyPressEvent(event)

    def __init__(self) -> None:
        super().__init__()
        self.setAcceptDrops(True)
        self.setDragDropMode(QListWidget.DragDropMode.DropOnly)
        self.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.setMouseTracking(True)

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if isinstance(event.source(), _Strip):
            event.acceptProposedAction()

    def dragMoveEvent(self, event) -> None:  # noqa: N802
        item = self.itemAt(event.position().toPoint())
        if item is not None and isinstance(event.source(), _Strip):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:  # noqa: N802
        item = self.itemAt(event.position().toPoint())
        if item is not None and isinstance(event.source(), _Strip):
            self.photo_dropped.emit(item.data(Qt.ItemDataRole.UserRole))
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()


class _Strip(QListWidget):
    """Photo cards of one group. They wrap onto new rows and scroll vertically."""

    adoption_toggle_requested = pyqtSignal(object, bool)
    context_requested = pyqtSignal(object, object)  # photo, global pos
    group_step_requested = pyqtSignal(int)          # PageUp -1 / PageDown +1

    def __init__(self) -> None:
        super().__init__()
        self.setViewMode(QListWidget.ViewMode.IconMode)
        self.setFlow(QListWidget.Flow.LeftToRight)
        self.setWrapping(True)
        self.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.setUniformItemSizes(True)
        self.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setMovement(QListWidget.Movement.Static)
        self.setIconSize(QSize(STRIP_ICON, STRIP_ICON))
        self.setSpacing(6)
        self.setObjectName("thumbGrid")  # card padding in light_table.qss
        self.setMinimumHeight(STRIP_ROW_HEIGHT)
        self.setDragEnabled(True)
        self.setDragDropMode(QListWidget.DragDropMode.DragOnly)
        self.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_context)
        self.setItemDelegate(_CardDelegate(self))
        # duck-typed panel attributes used by _CardDelegate
        self.grouping_active = True
        self.show_score = True
        self.weights = (0.5, 0.3, 0.2)

    def current_photo(self) -> PhotoItem | None:
        item = self.currentItem()
        return item.data(_PHOTO_ROLE) if item else None

    def _on_context(self, pos) -> None:
        item = self.itemAt(pos)
        if item is not None:
            self.setCurrentItem(item)
            self.context_requested.emit(item.data(_PHOTO_ROLE), self.viewport().mapToGlobal(pos))

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            index = self.indexAt(event.position().toPoint())
            if index.isValid():
                photo = index.data(_PHOTO_ROLE)
                photo_rect = self.itemDelegate().photo_rect(self.visualRect(index), index)
                if checkbox_rect(photo_rect).contains(event.position().toPoint()):
                    self.adoption_toggle_requested.emit(photo, not photo.is_adopted)
                    return
        super().mousePressEvent(event)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Space:
            photo = self.current_photo()
            if photo is not None:
                self.adoption_toggle_requested.emit(photo, not photo.is_adopted)
                return
        if _group_step_key(event, self.group_step_requested):
            return
        super().keyPressEvent(event)


class GroupReviewWindow(QWidget):
    """Signals
    -------
    changed()  — adoption or group structure changed (main window should refresh)
    """

    changed = pyqtSignal()

    def __init__(self, session: GroupSession, settings: AppSettings, parent=None) -> None:
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowTitle("그룹 리뷰")
        self.resize(1100, 720)
        self._session = session
        self._settings = settings
        self._gid: int | None = None
        self._icons: dict[str, QIcon] = {}
        self._big: dict[str, QPixmap] = {}
        self._details: dict[str, QPixmap] = {}
        self._detail_pending: set[str] = set()
        self._detail_signals = _DetailSignals()
        self._detail_signals.loaded.connect(self._on_detail_loaded)
        self._build()
        groups = session.groups()
        if groups:
            self._select_group(groups[0].id)

    # ---------------------------------------------------------------- build

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_toolbar())

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(self._build_group_panel())
        body.addWidget(self._build_workspace(), 1)
        body.addWidget(self._build_score_panel())
        root.addLayout(body, 1)

        status = QWidget()
        status.setObjectName("statusStrip")  # styled like a status bar in light_table.qss
        status.setFixedHeight(28)
        sl = QHBoxLayout(status)
        sl.setContentsMargins(16, 0, 16, 0)
        self._recent = QLabel("최근 작업: 없음")
        sl.addWidget(self._recent)
        sl.addStretch()
        sl.addWidget(QLabel(
            "← → 사진 이동      PageUp/Down 그룹 이동      Space 채택 토글      Ctrl+Z 되돌리기"
        ))
        root.addWidget(status)

        QShortcut(QKeySequence("Ctrl+Z"), self, activated=self._undo)
        # the two lists handle PageUp/Down themselves (item views swallow those keys);
        # these shortcuts cover focus anywhere else in the window
        QShortcut(QKeySequence(Qt.Key.Key_PageUp), self, activated=lambda: self._step_group(-1))
        QShortcut(QKeySequence(Qt.Key.Key_PageDown), self, activated=lambda: self._step_group(1))
        self._strip.group_step_requested.connect(self._step_group)
        self._group_list.group_step_requested.connect(self._step_group)

    def _build_toolbar(self) -> QWidget:
        toolbar = QWidget()
        toolbar.setObjectName("toolbar")  # same band as the main window toolbar
        toolbar.setFixedHeight(52)
        bar = QHBoxLayout(toolbar)
        bar.setContentsMargins(16, 0, 16, 0)
        bar.setSpacing(6)

        self._title_label = QLabel()
        self._title_label.setObjectName("viewTitle")
        bar.addWidget(self._title_label)
        bar.addSpacing(12)
        self._adopted_label = QLabel()
        self._adopted_label.setObjectName("pickCount")  # pick colour in light_table.qss
        bar.addWidget(self._adopted_label)
        bar.addSpacing(20)

        def button(text: str, slot, role: str = "") -> QPushButton:
            btn = QPushButton(text)
            btn.setFixedHeight(32)
            if role:
                btn.setProperty(role, True)
            btn.clicked.connect(slot)
            bar.addWidget(btn)
            return btn

        self._btn_all = button(
            "전체 채택", lambda: self._batch(self._session.adopt_all, "전체 채택"))
        self._btn_none = button(
            "전체 해제", lambda: self._batch(self._session.clear_all, "전체 해제"))
        self._btn_rec = button(
            "추천만 채택", lambda: self._batch(self._session.adopt_recommended, "추천만 채택"))
        self._btn_undo = button("되돌리기", self._undo, role="quiet")

        bar.addStretch()
        self._export_btn = button("", self._export, role="primary")
        button("닫기", self.close)
        return toolbar

    def _build_group_panel(self) -> QWidget:
        panel = QWidget()
        panel.setProperty("side", "left")  # panel surface + edge in light_table.qss
        panel.setFixedWidth(280)
        left = QVBoxLayout(panel)
        left.setContentsMargins(12, 14, 12, 12)
        left.setSpacing(8)

        left.addWidget(self._section_title("그룹"))
        self._group_list = _GroupList()
        self._group_list.setObjectName("groupList")
        self._group_list.setItemDelegate(_GroupDelegate(self._group_list, self._icon))
        self._group_list.currentItemChanged.connect(self._on_group_item)
        self._group_list.photo_dropped.connect(self._on_drop_to_group)
        left.addWidget(self._group_list, 1)

        left.addSpacing(6)
        left.addWidget(self._section_title("현재 그룹 수정"))
        self._merge_up = QPushButton("위 그룹과 병합")
        self._merge_down = QPushButton("아래 그룹과 병합")
        self._split_btn = QPushButton("선택한 사진부터 새 그룹으로 분리")
        self._merge_up.clicked.connect(lambda: self._merge(-1))
        self._merge_down.clicked.connect(lambda: self._merge(1))
        self._split_btn.clicked.connect(self._split)
        for b in (self._merge_up, self._merge_down, self._split_btn):
            b.setFixedHeight(30)
            left.addWidget(b)
        return panel

    def _build_workspace(self) -> QWidget:
        workspace = QWidget()
        layout = QVBoxLayout(workspace)
        layout.setContentsMargins(16, 14, 16, 8)
        layout.setSpacing(0)

        upper = QWidget()
        upper_layout = QVBoxLayout(upper)
        upper_layout.setContentsMargins(0, 0, 0, 8)
        upper_layout.setSpacing(6)
        self._preview = ZoomPanView()
        self._preview.detail_requested.connect(self._request_detail)
        upper_layout.addWidget(self._preview, 1)
        self._reason_label = QLabel()
        self._reason_label.setWordWrap(True)
        upper_layout.addWidget(self._reason_label)
        self._group_info = QLabel()
        self._group_info.setObjectName("hint-label")
        upper_layout.addWidget(self._group_info)

        self._strip = _Strip()
        self._strip.currentItemChanged.connect(self._on_strip_current)
        self._strip.adoption_toggle_requested.connect(self._on_toggle)
        self._strip.context_requested.connect(self._on_context)
        self._splitter = QSplitter(Qt.Orientation.Vertical)
        self._splitter.setChildrenCollapsible(False)
        self._splitter.addWidget(upper)
        self._splitter.addWidget(self._strip)
        self._splitter.setStretchFactor(0, 1)
        self._splitter.setStretchFactor(1, 0)
        # one full row plus a peek of the next, so it is obvious the list scrolls
        self._splitter.setSizes([420, int(STRIP_ROW_HEIGHT * 1.4)])
        layout.addWidget(self._splitter, 1)
        return workspace

    def _build_score_panel(self) -> QWidget:
        panel = QWidget()
        panel.setProperty("side", "right")
        panel.setFixedWidth(240)
        box = QVBoxLayout(panel)
        box.setContentsMargins(18, 14, 18, 14)
        box.setSpacing(6)

        box.addWidget(self._section_title("품질 점수"))
        self._score_title = QLabel()
        self._score_title.setObjectName("scoreFile")
        box.addWidget(self._score_title)

        total_row = QHBoxLayout()
        self._total_label = QLabel()
        self._total_label.setObjectName("scoreTotal")
        total_row.addWidget(self._total_label)
        caption = QLabel("종합")
        caption.setObjectName("hint-label")
        total_row.addWidget(caption, 0, Qt.AlignmentFlag.AlignBottom)
        total_row.addStretch()
        box.addLayout(total_row)
        box.addSpacing(8)

        self._bars: list[QProgressBar] = []
        self._bar_values: list[QLabel] = []
        for name in ("선명도", "노출", "색감"):
            row = QHBoxLayout()
            row.addWidget(QLabel(name))
            row.addStretch()
            value = QLabel()
            row.addWidget(value)
            box.addLayout(row)
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setTextVisible(False)
            box.addWidget(bar)
            box.addSpacing(6)
            self._bars.append(bar)
            self._bar_values.append(value)

        self._weights_label = QLabel()
        self._weights_label.setObjectName("hint-label")
        self._weights_label.setWordWrap(True)
        box.addWidget(self._weights_label)
        box.addStretch()
        return panel

    @staticmethod
    def _section_title(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("sectionTitle")
        return label

    # ---------------------------------------------------------------- reload

    def refresh(self) -> None:
        """Called by the main window after it changed the session (weights, adoption)."""
        self._reload()

    def _reload(self) -> None:
        """Refresh everything from the session, keeping the current group when possible."""
        groups = self._session.groups()
        ids = [g.id for g in groups]
        if self._gid not in ids:
            self._gid = ids[0] if ids else None
        self._fill_group_list(groups)
        self._fill_strip()
        self._update_side_widgets()
        pos = ids.index(self._gid) + 1 if self._gid in ids else 0
        self._title_label.setText(f"그룹 {pos:,} / {len(ids):,}")
        total = sum(len(g.photos) for g in groups)
        self._adopted_label.setText(f"채택 {self._session.adopted_count():,}장/{total:,}장")
        self.setWindowTitle(
            f"그룹 리뷰 — 그룹 {pos:,} / {len(ids):,}"
            f" · 채택 {self._session.adopted_count():,}장"
        )

    def _fill_group_list(self, groups: list[Group]) -> None:
        """Update the cards in place; rebuild only when groups were added/removed/reordered.

        A rebuild keeps the scroll position, so the selected card does not jump to the edge.
        """
        lst = self._group_list
        ids = [g.id for g in groups]
        current = [lst.item(i).data(Qt.ItemDataRole.UserRole) for i in range(lst.count())]
        lst.blockSignals(True)
        rebuilt = current != ids
        if rebuilt:
            pos = lst.verticalScrollBar().value()
            lst.clear()
            for gid in ids:
                item = QListWidgetItem()
                item.setData(Qt.ItemDataRole.UserRole, gid)
                lst.addItem(item)
        for k, g in enumerate(groups):
            s = group_summary(self._session, g, k + 1)
            item = lst.item(k)
            item.setData(_SUMMARY_ROLE, s)
            item.setText(s.text)
            item.setToolTip(s.text + (f"\n{s.span}" if s.span else ""))
            if g.id == self._gid and lst.currentItem() is not item:
                lst.setCurrentItem(item)
        if rebuilt:
            lst.doItemsLayout()
            lst.verticalScrollBar().setValue(pos)
            if lst.currentItem() is not None:
                lst.scrollToItem(lst.currentItem())  # only moves if it went out of view
        lst.blockSignals(False)
        lst.viewport().update()

    def _fill_strip(self, keep: PhotoItem | None = None) -> None:
        strip = self._strip
        strip.show_score = self._settings.show_score
        strip.weights = self._settings.weights()
        prev = keep or strip.current_photo()
        strip.blockSignals(True)
        strip.clear()
        if self._gid is not None:
            group = self._session.group(self._gid)
            for p in group.photos:
                item = QListWidgetItem(p.source_path.name)
                item.setData(_PHOTO_ROLE, p)
                item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom)
                item.setSizeHint(QSize(STRIP_ICON + 2 * CARD_PAD,
                                       STRIP_ICON + CARD_PAD + CARD_TEXT_H + 4))
                item.setIcon(self._icon(p))
                item.setToolTip(p.reason)
                strip.addItem(item)
                if p is prev:
                    strip.setCurrentItem(item)
            if strip.currentItem() is None and strip.count():
                strip.setCurrentRow(0)
        strip.blockSignals(False)
        if strip.currentItem() is not None:
            strip.scrollToItem(strip.currentItem())
        strip.viewport().update()
        self._show_current()

    def _icon(self, photo: PhotoItem) -> QIcon:
        key = str(photo.source_path)
        if key not in self._icons:
            try:
                self._icons[key] = QIcon(_pil_to_pixmap(load_analysis_image(photo.source_path,
                                                                            STRIP_ICON * 2)))
            except Exception:
                self._icons[key] = QIcon()
        return self._icons[key]

    def _show_current(self) -> None:
        photo = self._strip.current_photo()
        if photo is None:
            self._preview.clear()
            self._preview.set_image("", None, "사진 없음")
            self._reason_label.setText("")
            return
        key = str(photo.source_path)
        if key not in self._big:
            try:
                self._big[key] = _pil_to_pixmap(
                    load_analysis_image(photo.source_path, PREVIEW_LONG_SIDE)
                )
            except Exception:
                self._big[key] = QPixmap()
        pm = self._big[key]
        if pm.isNull():
            self._preview.set_image(key, None, f"{photo.source_path.name}\n(불러올 수 없음)")
        else:
            # same photo -> zoom/pan are kept; another photo -> back to "fit"
            self._preview.set_image(key, pm)
            if key in self._details:
                self._preview.set_detail(key, self._details[key])
        state = "채택" if photo.is_adopted else "제외"
        star = " · 추천" if photo.is_recommended else ""
        self._score_title.setText(photo.source_path.name)
        if photo.scores is not None:
            values = (photo.scores.sharpness, photo.scores.exposure, photo.scores.color)
            for bar, label, v in zip(self._bars, self._bar_values, values, strict=True):
                bar.setValue(round(v))
                label.setText(str(round(v)))
            w = self._settings.weights()
            self._total_label.setText(str(round(composite(photo.scores, w))))
            self._weights_label.setText(
                f"가중치: 선명도 {w[0]:.0%}, 노출 {w[1]:.0%}, 색감 {w[2]:.0%}"
            )
        else:
            for bar, label in zip(self._bars, self._bar_values, strict=True):
                bar.setValue(0)
                label.setText("-")
            self._total_label.setText("-")
            self._weights_label.setText("분석하지 못한 사진입니다")
        rec = next((p for p in self._session.group(photo.group_id).photos if p.is_recommended),
                   None)
        reason = f"[{state}{star}] {photo.reason or '-'}"
        if rec is not None and rec is not photo:
            reason += f"   · 추천: {rec.source_path.name} ({rec.reason})"
        self._reason_label.setText(reason)

    def _update_side_widgets(self) -> None:
        ids = [g.id for g in self._session.groups()]
        k = ids.index(self._gid) if self._gid in ids else -1
        self._merge_up.setEnabled(k > 0)
        self._merge_down.setEnabled(0 <= k < len(ids) - 1)
        self._btn_undo.setEnabled(self._session.can_undo)
        n = self._session.adopted_count()
        self._export_btn.setText(f"채택 사진 내보내기 ({n:,}장)")
        self._export_btn.setEnabled(n > 0)
        if self._gid is not None:
            g = self._session.group(self._gid)
            span = time_span(g.photos)
            span = f" · {span}" if span else ""
            adopted = sum(1 for p in g.photos if p.is_adopted)
            self._group_info.setText(
                f"{len(g.photos):,}장{span} · 채택 {adopted:,}장      "
                "사진을 우클릭하거나 그룹 목록으로 끌어 옮길 수 있어요"
            )

    # ---------------------------------------------------------------- events

    def _select_group(self, gid: int) -> None:
        self._gid = gid
        self._session.mark_reviewed(gid)
        self._reload()
        self._strip.setFocus()

    def _step_group(self, step: int) -> None:
        """PageUp / PageDown: previous / next group."""
        ids = [g.id for g in self._session.groups()]
        if self._gid not in ids:
            return
        k = ids.index(self._gid) + step
        if 0 <= k < len(ids):
            self._select_group(ids[k])

    def _on_group_item(self, item, _prev) -> None:
        if item is not None:
            gid = item.data(Qt.ItemDataRole.UserRole)
            QTimer.singleShot(0, lambda: self._select_group(gid))  # list is rebuilt: defer

    def _on_strip_current(self, _item, _prev) -> None:
        self._show_current()

    def _after_change(self, text: str) -> None:
        self._recent.setText(f"최근 작업: {text} (되돌리기 = 이 작업 1건만 취소)")
        self._reload()
        self.changed.emit()

    def _on_toggle(self, photo: PhotoItem, value: bool) -> None:
        self._session.set_adopted(photo, value)
        self._after_change(f"{photo.source_path.name} {'채택' if value else '제외'}")
        self._strip.setFocus()

    def _batch(self, op, label: str) -> None:
        if self._gid is None:
            return
        op(self._gid)
        self._after_change(f"현재 그룹 {label}")

    def _undo(self) -> None:
        if self._session.undo():
            self._after_change("되돌리기")

    def _merge(self, direction: int) -> None:
        ids = [g.id for g in self._session.groups()]
        if self._gid not in ids:
            return
        k = ids.index(self._gid)
        other = k + direction
        if not 0 <= other < len(ids):
            return
        keep, absorb = (ids[other], self._gid) if direction < 0 else (self._gid, ids[other])
        self._session.merge(keep, absorb)
        self._gid = keep
        self._after_change("그룹 병합")

    def _split(self) -> None:
        photo = self._strip.current_photo()
        if photo is None:
            return
        gid = self._session.split_from(photo)
        if gid is None:
            QMessageBox.information(
                self, "그룹 분리", "첫 사진은 분리할 수 없습니다.\n두 번째 이후 사진을 선택하세요."
            )
            return
        self._gid = gid
        self._after_change("그룹 분리")

    def _on_context(self, photo: PhotoItem, global_pos) -> None:
        menu = QMenu(self)
        groups = self._session.groups()
        move = menu.addMenu("다른 그룹으로 이동")
        targets = {}
        for k, g in enumerate(groups, start=1):
            if g.id != photo.group_id:
                targets[move.addAction(f"그룹 {k:,} ({len(g.photos):,}장)")] = g.id
        if not targets:
            move.setEnabled(False)
        detach = menu.addAction("그룹에서 분리 (단독 사진)")
        detach.setEnabled(len(self._session.group(photo.group_id).photos) > 1)
        action = menu.exec(global_pos)
        if action is None:
            return
        if action is detach:
            self._gid = self._session.detach_photo(photo)
            self._after_change(f"{photo.source_path.name} 분리")
        elif action in targets:
            self._move_photo(photo, targets[action])

    def _on_drop_to_group(self, gid: int) -> None:
        photo = self._strip.current_photo()
        if photo is not None and photo.group_id != gid:
            self._move_photo(photo, gid)

    def _move_photo(self, photo: PhotoItem, gid: int) -> None:
        self._session.move_photo(photo, gid)
        self._after_change(f"{photo.source_path.name} 이동")

    def _export(self) -> None:
        dest = QFileDialog.getExistingDirectory(self, "채택 사진 내보내기 — 폴더 선택")
        if not dest:
            return
        copied, errors = export_adopted(
            [p for g in self._session.groups() for p in g.photos], Path(dest)
        )
        msg = f"{copied:,}장을 복사했습니다.\n{dest}"
        if errors:
            msg += f"\n\n실패 {len(errors):,}건:\n" + "\n".join(errors[:5])
        QMessageBox.information(self, "내보내기 완료", msg)

    def _request_detail(self, key: str) -> None:
        if key in self._details:
            self._preview.set_detail(key, self._details[key])
            return
        if key in self._detail_pending:
            return
        self._detail_pending.add(key)
        QThreadPool.globalInstance().start(_DetailLoader(Path(key), self._detail_signals))

    def _on_detail_loaded(self, key: str, image: QImage) -> None:
        self._detail_pending.discard(key)
        self._details[key] = QPixmap.fromImage(image)
        while len(self._details) > DETAIL_CACHE:
            self._details.pop(next(iter(self._details)))
        self._preview.set_detail(key, self._details.get(key, QPixmap()))
