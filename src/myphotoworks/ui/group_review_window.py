"""GroupReviewWindow — compare photos per group, adopt several, edit groups, undo."""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QObject, QRunnable, QSize, Qt, QThreadPool, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QIcon,
    QImage,
    QKeySequence,
    QLinearGradient,
    QPainter,
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
    QVBoxLayout,
    QWidget,
)

from myphotoworks.core.analysis_image import load_analysis_image
from myphotoworks.core.scoring import composite
from myphotoworks.models.group_session import GroupSession
from myphotoworks.models.photo_item import PhotoItem
from myphotoworks.models.settings import AppSettings
from myphotoworks.processing.export import export_adopted
from myphotoworks.ui.thumbnail_panel import _PHOTO_ROLE, _CardDelegate, checkbox_rect
from myphotoworks.ui.zoom_view import ZoomPanView

STRIP_ICON = 130
PREVIEW_LONG_SIDE = 1000   # fitted preview
DETAIL_LONG_SIDE = 4000    # loaded on first zoom-in so detail is not blurry
DETAIL_CACHE = 3


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


class _GroupList(QListWidget):
    """Group list that accepts photo cards dragged from the film strip."""

    photo_dropped = pyqtSignal(int)  # target group id

    def __init__(self) -> None:
        super().__init__()
        self.setAcceptDrops(True)
        self.setDragDropMode(QListWidget.DragDropMode.DropOnly)

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
    """Horizontal film strip of one group's photos."""

    adoption_toggle_requested = pyqtSignal(object, bool)
    context_requested = pyqtSignal(object, object)  # photo, global pos

    def __init__(self) -> None:
        super().__init__()
        self.setViewMode(QListWidget.ViewMode.IconMode)
        self.setFlow(QListWidget.Flow.LeftToRight)
        self.setWrapping(False)
        self.setMovement(QListWidget.Movement.Static)
        self.setIconSize(QSize(STRIP_ICON, STRIP_ICON))
        self.setSpacing(6)
        self.setFixedHeight(STRIP_ICON + 52)
        self.setDragEnabled(True)
        self.setDragDropMode(QListWidget.DragDropMode.DragOnly)
        self.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_context)
        self.setItemDelegate(_CardDelegate(self))
        # duck-typed panel attributes used by _CardDelegate
        self.grouping_active = True
        self.icon_px = STRIP_ICON
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
                if checkbox_rect(self.visualRect(index)).contains(event.position().toPoint()):
                    self.adoption_toggle_requested.emit(photo, not photo.is_adopted)
                    return
        super().mousePressEvent(event)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Space:
            photo = self.current_photo()
            if photo is not None:
                self.adoption_toggle_requested.emit(photo, not photo.is_adopted)
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
        body = QHBoxLayout()
        root.addLayout(body, 1)

        left = QVBoxLayout()
        left.addWidget(QLabel("그룹 목록"))
        self._group_list = _GroupList()
        self._group_list.setFixedWidth(260)
        self._group_list.currentItemChanged.connect(self._on_group_item)
        self._group_list.photo_dropped.connect(self._on_drop_to_group)
        left.addWidget(self._group_list, 1)
        left.addWidget(QLabel("그룹 수정 (현재 그룹)"))
        self._merge_up = QPushButton("위 그룹과 병합")
        self._merge_down = QPushButton("아래 그룹과 병합")
        self._split_btn = QPushButton("선택 사진부터 새 그룹으로 분리")
        self._merge_up.clicked.connect(lambda: self._merge(-1))
        self._merge_down.clicked.connect(lambda: self._merge(1))
        self._split_btn.clicked.connect(self._split)
        for b in (self._merge_up, self._merge_down, self._split_btn):
            left.addWidget(b)
        body.addLayout(left)

        right = QVBoxLayout()
        top = QHBoxLayout()
        self._preview = ZoomPanView()
        self._preview.detail_requested.connect(self._request_detail)
        top.addWidget(self._preview, 1)

        score_box = QVBoxLayout()
        self._score_title = QLabel("품질 점수")
        score_box.addWidget(self._score_title)
        self._bars: list[QProgressBar] = []
        for name in ("선명도", "노출", "색감"):
            score_box.addWidget(QLabel(name))
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setFormat("%v")
            score_box.addWidget(bar)
            self._bars.append(bar)
        self._total_label = QLabel()
        self._weights_label = QLabel()
        score_box.addWidget(self._total_label)
        score_box.addWidget(self._weights_label)
        score_box.addStretch()
        score_w = QWidget()
        score_w.setLayout(score_box)
        score_w.setFixedWidth(230)
        top.addWidget(score_w)
        right.addLayout(top, 1)

        self._reason_label = QLabel()
        self._reason_label.setWordWrap(True)
        right.addWidget(self._reason_label)
        self._group_info = QLabel()
        right.addWidget(self._group_info)

        self._strip = _Strip()
        self._strip.currentItemChanged.connect(self._on_strip_current)
        self._strip.adoption_toggle_requested.connect(self._on_toggle)
        self._strip.context_requested.connect(self._on_context)
        right.addWidget(self._strip)

        self._recent = QLabel("최근 작업: 없음")
        right.addWidget(self._recent)
        body.addLayout(right, 1)

        bar = QHBoxLayout()
        bar.addWidget(QLabel("현재 그룹:"))
        self._btn_all = QPushButton("전체 채택")
        self._btn_none = QPushButton("전체 해제")
        self._btn_rec = QPushButton("추천만 채택")
        self._btn_undo = QPushButton("되돌리기")
        self._btn_all.clicked.connect(lambda: self._batch(self._session.adopt_all, "전체 채택"))
        self._btn_none.clicked.connect(lambda: self._batch(self._session.clear_all, "전체 해제"))
        self._btn_rec.clicked.connect(
            lambda: self._batch(self._session.adopt_recommended, "추천만 채택")
        )
        self._btn_undo.clicked.connect(self._undo)
        for b in (self._btn_all, self._btn_none, self._btn_rec, self._btn_undo):
            bar.addWidget(b)
        bar.addWidget(QLabel("← → 이동 · Space 채택 토글 · Ctrl+Z 되돌리기"))
        bar.addStretch()
        self._export_btn = QPushButton()
        self._export_btn.clicked.connect(self._export)
        close_btn = QPushButton("닫기")
        close_btn.clicked.connect(self.close)
        bar.addWidget(self._export_btn)
        bar.addWidget(close_btn)
        root.addLayout(bar)

        QShortcut(QKeySequence("Ctrl+Z"), self, activated=self._undo)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0.0, QColor("#0d1117"))
        gradient.setColorAt(0.5, QColor("#161b22"))
        gradient.setColorAt(1.0, QColor("#1c2333"))
        painter.fillRect(self.rect(), gradient)

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
        self._group_list.blockSignals(True)
        self._group_list.clear()
        for k, g in enumerate(groups, start=1):
            adopted = sum(1 for p in g.photos if p.is_adopted)
            item = QListWidgetItem(
                f"그룹 {k} · {len(g.photos)}장 · 채택 {adopted}  [{self._session.tag(g.id)}]"
            )
            item.setData(Qt.ItemDataRole.UserRole, g.id)
            self._group_list.addItem(item)
            if g.id == self._gid:
                self._group_list.setCurrentItem(item)
        self._group_list.blockSignals(False)
        self._fill_strip()
        self._update_side_widgets()
        self.setWindowTitle(
            f"그룹 리뷰 — 그룹 {ids.index(self._gid) + 1 if self._gid in ids else 0} / {len(ids)}"
            f" · 채택 {self._session.adopted_count()}장"
        )

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
                item.setSizeHint(QSize(STRIP_ICON + 20, STRIP_ICON + 40))
                item.setIcon(self._icon(p))
                item.setToolTip(p.reason)
                strip.addItem(item)
                if p is prev:
                    strip.setCurrentItem(item)
            if strip.currentItem() is None and strip.count():
                strip.setCurrentRow(0)
        strip.blockSignals(False)
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
        self._score_title.setText(f"품질 점수 · {photo.source_path.name}")
        if photo.scores is not None:
            for bar, v in zip(self._bars, (photo.scores.sharpness, photo.scores.exposure,
                                           photo.scores.color), strict=True):
                bar.setValue(round(v))
            w = self._settings.weights()
            self._total_label.setText(f"종합 {round(composite(photo.scores, w))}")
            self._weights_label.setText(f"가중치 {w[0]:.2f} / {w[1]:.2f} / {w[2]:.2f}")
        else:
            for bar in self._bars:
                bar.setValue(0)
            self._total_label.setText("종합 -")
            self._weights_label.setText("분석하지 못한 사진입니다")
        rec = next((p for p in self._session.group(photo.group_id).photos if p.is_recommended),
                   None)
        reason = f"[{state}{star}] {photo.reason or '-'}"
        if rec is not None and rec is not photo:
            reason += f"   · 추천: {rec.source_path.name} ({rec.reason})"
        self._reason_label.setText("추천 이유  " + reason)

    def _update_side_widgets(self) -> None:
        ids = [g.id for g in self._session.groups()]
        k = ids.index(self._gid) if self._gid in ids else -1
        self._merge_up.setEnabled(k > 0)
        self._merge_down.setEnabled(0 <= k < len(ids) - 1)
        self._btn_undo.setEnabled(self._session.can_undo)
        n = self._session.adopted_count()
        self._export_btn.setText(f"채택 사진 내보내기 ({n}장)")
        self._export_btn.setEnabled(n > 0)
        if self._gid is not None:
            g = self._session.group(self._gid)
            times = sorted(p.analysis.taken for p in g.photos if p.analysis and p.analysis.taken)
            span = ""
            if times:
                a, b = times[0].strftime("%H:%M:%S"), times[-1].strftime("%H:%M:%S")
                span = f" · {a}" if a == b else f" · {a} – {b}"
            adopted = sum(1 for p in g.photos if p.is_adopted)
            self._group_info.setText(
                f"{len(g.photos)}장{span} · 채택 {adopted}장 · 우클릭: 그룹 수정 · "
                "그룹 목록으로 드래그해도 이동"
            )

    # ---------------------------------------------------------------- events

    def _select_group(self, gid: int) -> None:
        self._gid = gid
        self._session.mark_reviewed(gid)
        self._reload()
        self._strip.setFocus()

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
                targets[move.addAction(f"그룹 {k} ({len(g.photos)}장)")] = g.id
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
        msg = f"{copied}장을 복사했습니다.\n{dest}"
        if errors:
            msg += f"\n\n실패 {len(errors)}건:\n" + "\n".join(errors[:5])
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
