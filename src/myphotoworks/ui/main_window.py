"""MainWindow — file list (left, large) + settings panel (right) + bottom action bar."""
from __future__ import annotations

import dataclasses
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QKeySequence, QLinearGradient, QPainter, QShortcut
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from myphotoworks.models.photo_item import PhotoItem
from myphotoworks.models.settings import AppSettings
from myphotoworks.processing.group_runner import correction_key
from myphotoworks.ui.settings_panel import SettingsPanel
from myphotoworks.ui.thumbnail_panel import ThumbnailPanel
from myphotoworks.utils.config import load_config, load_settings, save_config, save_settings

SUPPORTED_FILTER = (
    "이미지 파일 (*.jpg *.jpeg *.png *.tif *.tiff *.bmp *.webp);;"
    "모든 파일 (*)"
)

_SYSMENU_ABOUT_ID = 0x1001  # custom Windows system-menu command ID
_WM_SYSCOMMAND = 0x0112

# Define Win32 MSG struct once at module level — redefining ctypes.Structure
# inside a frequently-called method causes memory issues.
try:
    import ctypes
    import ctypes.wintypes

    class _WinMSG(ctypes.Structure):
        _fields_ = [
            ("hwnd",    ctypes.wintypes.HWND),
            ("message", ctypes.c_uint),
            ("wParam",  ctypes.wintypes.WPARAM),
            ("lParam",  ctypes.wintypes.LPARAM),
            ("time",    ctypes.wintypes.DWORD),
            ("pt",      ctypes.wintypes.POINT),
        ]
except Exception:
    _WinMSG = None  # type: ignore[assignment,misc]


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("myPhotoWorks")
        self.resize(1100, 700)

        self._cfg = load_config()
        self._settings = load_settings(self._cfg)
        self._worker = None
        self._group_worker = None
        self._session = None
        self._review_win = None
        self._rescore_worker = None
        self._analysis_key = None

        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._build_ui()
        self._restore_geometry()

        f1 = QShortcut(QKeySequence(Qt.Key.Key_F1), self)
        f1.activated.connect(self._on_about)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(4)

        # --- Top button bar ---
        btn_bar = QHBoxLayout()

        self._add_files_btn = QPushButton("파일 추가")
        self._add_files_btn.setFixedHeight(28)
        self._add_files_btn.clicked.connect(self._on_add_files)
        btn_bar.addWidget(self._add_files_btn)

        self._add_folder_btn = QPushButton("폴더 추가")
        self._add_folder_btn.setFixedHeight(28)
        self._add_folder_btn.clicked.connect(self._on_add_folder)
        btn_bar.addWidget(self._add_folder_btn)

        self._remove_btn = QPushButton("선택 제거")
        self._remove_btn.setFixedHeight(28)
        self._remove_btn.setEnabled(False)
        self._remove_btn.clicked.connect(self._on_remove_selected)
        btn_bar.addWidget(self._remove_btn)

        self._clear_btn = QPushButton("전체 제거")
        self._clear_btn.setFixedHeight(28)
        self._clear_btn.setEnabled(False)
        self._clear_btn.clicked.connect(self._on_clear_all)
        btn_bar.addWidget(self._clear_btn)

        btn_bar.addStretch()

        self._all_view_btn = QPushButton("전체 보기")
        self._group_view_btn = QPushButton("그룹별 보기")
        for b in (self._all_view_btn, self._group_view_btn):
            b.setCheckable(True)
            b.setFixedHeight(28)
            b.setEnabled(False)
            btn_bar.addWidget(b)
        self._all_view_btn.setChecked(True)
        self._view_group = QButtonGroup(self)
        self._view_group.setExclusive(True)
        self._view_group.addButton(self._all_view_btn)
        self._view_group.addButton(self._group_view_btn)
        self._view_group.buttonClicked.connect(lambda _b: self._apply_view())

        self._adopted_only_cb = QCheckBox("채택만 보기")
        self._adopted_only_cb.setEnabled(False)
        self._adopted_only_cb.toggled.connect(lambda _c: self._apply_view())
        btn_bar.addWidget(self._adopted_only_cb)

        self._review_btn = QPushButton("그룹 리뷰")
        self._review_btn.setFixedHeight(28)
        self._review_btn.setEnabled(False)
        self._review_btn.clicked.connect(self._on_review)
        btn_bar.addWidget(self._review_btn)

        self._preview_btn = QPushButton("미리보기")
        self._preview_btn.setFixedHeight(28)
        self._preview_btn.setEnabled(False)
        self._preview_btn.clicked.connect(self._on_preview)
        btn_bar.addWidget(self._preview_btn)

        self._process_btn = QPushButton("일괄 적용")
        self._process_btn.setFixedHeight(28)
        self._process_btn.setEnabled(False)
        self._process_btn.clicked.connect(self._on_process)
        btn_bar.addWidget(self._process_btn)

        root.addLayout(btn_bar)

        # --- Splitter: thumbnail panel (large left) | settings panel ---
        splitter = QSplitter(Qt.Orientation.Horizontal)

        self._thumb_panel = ThumbnailPanel()
        self._thumb_panel.photo_selected.connect(self._on_photo_selected)
        self._thumb_panel.photo_double_clicked.connect(self._on_photo_double_clicked)
        self._thumb_panel.show_info_requested.connect(self._on_about)
        self._thumb_panel.photos_added.connect(self._on_photos_added)
        self._thumb_panel.photos_removed.connect(self._on_photos_removed)
        self._thumb_panel.adoption_toggle_requested.connect(self._on_adoption_toggle)
        self._thumb_panel.set_options(
            self._settings.show_reason, self._settings.show_score, self._settings.weights()
        )
        splitter.addWidget(self._thumb_panel)

        self._settings_panel = SettingsPanel(self._settings)
        self._settings_panel.settings_changed.connect(self._on_settings_changed)
        self._settings_panel.weights_changed.connect(self._on_weights_changed)
        self._settings_panel.display_changed.connect(self._on_display_changed)
        self._settings_panel.group_run_requested.connect(self._on_group_run)
        self._settings_panel.group_cancel_requested.connect(self._on_group_cancel)
        self._settings_panel.group_review_requested.connect(self._on_review)
        self._settings_panel.group_rescore_requested.connect(self._on_rescore)
        splitter.addWidget(self._settings_panel)


        # Thumbnail panel takes ~2/3, settings panel ~1/3
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)

        root.addWidget(splitter)

        # --- Status bar ---
        status_bar = QStatusBar()
        self.setStatusBar(status_bar)

        self._status_label = QLabel("사진을 추가하세요.")
        status_bar.addWidget(self._status_label, 1)

        self._progress_bar = QProgressBar()
        self._progress_bar.setFixedWidth(220)
        self._progress_bar.setVisible(False)
        status_bar.addPermanentWidget(self._progress_bar)

    # ------------------------------------------------------------------
    # Slots — file management
    # ------------------------------------------------------------------

    def _on_about(self) -> None:
        from myphotoworks.ui.about_dialog import AboutDialog

        dlg = AboutDialog(self)
        dlg.exec()

    def _on_add_files(self) -> None:
        last_dir = self._cfg.get("last_open_dir", str(Path.home()))
        paths, _ = QFileDialog.getOpenFileNames(
            self, "파일 추가", last_dir, SUPPORTED_FILTER
        )
        if not paths:
            return
        photo_paths = [Path(p) for p in paths]
        self._thumb_panel.add_photos(photo_paths)
        self._cfg["last_open_dir"] = str(photo_paths[0].parent)
        save_config(self._cfg)
        self._update_buttons()

    def _on_add_folder(self) -> None:
        last_dir = self._cfg.get("last_open_dir", str(Path.home()))
        folder = QFileDialog.getExistingDirectory(self, "폴더 추가", last_dir)
        if not folder:
            return
        folder_path = Path(folder)
        exts = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp"}
        paths = [p for p in sorted(folder_path.iterdir()) if p.suffix.lower() in exts]
        self._thumb_panel.add_photos(paths)
        self._cfg["last_open_dir"] = folder
        save_config(self._cfg)
        self._update_buttons()

    def _on_remove_selected(self) -> None:
        self._thumb_panel.remove_selected()
        self._update_buttons()

    def _on_clear_all(self) -> None:
        self._thumb_panel.clear_all()
        self._update_buttons()

    def _on_photo_selected(self, photo: PhotoItem) -> None:
        self._status_label.setText(photo.source_path.name)
        self._remove_btn.setEnabled(True)

    def _on_photo_double_clicked(self, photo: PhotoItem) -> None:
        photos = self._thumb_panel.photos()
        if not photos:
            return
        start_index = next(
            (i for i, p in enumerate(photos) if p.source_path == photo.source_path), 0
        )
        self._open_preview(photos, start_index)

    def _on_settings_changed(self, settings: AppSettings) -> None:
        self._settings = settings
        self._check_stale_scores()
        save_config(self._cfg)

    # ------------------------------------------------------------------
    # Preview
    # ------------------------------------------------------------------

    def _on_preview(self) -> None:
        photos = self._thumb_panel.photos()
        if not photos:
            return
        self._open_preview(photos, 0)

    def _open_preview(self, photos: list[PhotoItem], start_index: int) -> None:
        from myphotoworks.ui.preview_window import PreviewWindow

        first_dir = photos[0].source_path.parent if photos else Path(".")
        win = PreviewWindow(photos, self._settings, first_file_dir=first_dir, parent=self)
        win._index = start_index
        win.show()  # showEvent triggers _load_current() after widget sizes are valid

    # ------------------------------------------------------------------
    # Batch processing
    # ------------------------------------------------------------------

    def _on_process(self) -> None:
        photos = self._thumb_panel.photos()
        if not photos:
            return

        from myphotoworks.workers.batch_worker import BatchWorker
        first_dir = photos[0].source_path.parent
        self._worker = BatchWorker(photos, self._settings, first_file_dir=first_dir)
        self._worker.progress.connect(self._on_progress)
        self._worker.photo_done.connect(self._thumb_panel.update_status)
        self._worker.finished.connect(self._on_process_finished)
        self._worker.error.connect(self._on_process_error)

        self._progress_bar.setRange(0, len(photos))
        self._progress_bar.setValue(0)
        self._progress_bar.setVisible(True)
        self._set_processing(True)
        self._worker.start()

    def _on_progress(self, current: int, total: int) -> None:
        self._progress_bar.setValue(current)
        self._status_label.setText(f"처리 중... {current} / {total}")

    def _on_process_finished(self) -> None:
        self._progress_bar.setVisible(False)
        self._set_processing(False)
        photos = self._thumb_panel.photos()
        total = len(photos)
        from myphotoworks.models.photo_item import ProcessStatus
        saved = sum(1 for p in photos if p.status == ProcessStatus.DONE)
        self._status_label.setText(f"완료: {total}장 중 {saved}장 저장됨")
        self._update_buttons()
        QMessageBox.information(
            self,
            "일괄 적용 완료",
            f"처리가 완료되었습니다.\n\n전체 {total}개 중 {saved}개가 저장되었습니다.",
        )

    def _on_process_error(self, msg: str) -> None:
        self._status_label.setText(f"오류: {msg}")

    # ------------------------------------------------------------------
    # Grouping (Lumis Flow)
    # ------------------------------------------------------------------

    def _apply_view(self) -> None:
        self._thumb_panel.set_view(
            grouped=self._group_view_btn.isChecked(),
            adopted_only=self._adopted_only_cb.isChecked(),
        )
        self._update_buttons()

    def _set_grouping_controls(self, has_session: bool) -> None:
        self._all_view_btn.setEnabled(has_session)
        self._group_view_btn.setEnabled(has_session)
        self._adopted_only_cb.setEnabled(has_session)
        self._review_btn.setEnabled(has_session)
        self._settings_panel.group_tab.set_done(has_session)

    def _drop_session(self) -> None:
        if self._session is None:
            return
        self._session = None
        self._analysis_key = None
        self._settings_panel.group_tab.set_stale(False)
        if self._review_win is not None:
            self._review_win.close()
            self._review_win = None
        self._thumb_panel.set_session(None)
        self._all_view_btn.setChecked(True)
        self._adopted_only_cb.setChecked(False)
        self._set_grouping_controls(False)
        self._settings_panel.group_tab.clear_result()
        self._apply_view()

    def _on_photos_added(self, added: list[PhotoItem]) -> None:
        if self._session is not None:
            self._session.add_photos(added)
            self._thumb_panel.rebuild()
            self._update_buttons()
            self._status_label.setText(
                f"추가한 {self._session.added_count()}장은 그룹핑 전입니다. "
                "다시 그룹핑하면 그룹에 포함됩니다."
            )
            return
        self._update_buttons()

    def _on_photos_removed(self, removed: list[PhotoItem]) -> None:
        if self._session is not None:
            self._session.remove_photos(removed)
            if self._session.group_count() == 0:
                self._drop_session()
            else:
                self._on_review_changed()
                return
        self._update_buttons()

    def _on_group_run(self) -> None:
        photos = self._thumb_panel.all_photos()
        if not photos or self._group_worker is not None:
            return
        from myphotoworks.workers.group_worker import GroupWorker

        self._drop_session()
        self._group_worker = GroupWorker(photos, dataclasses.replace(self._settings))
        self._group_worker.progress.connect(self._settings_panel.group_tab.set_progress)
        self._group_worker.done.connect(self._on_group_done)
        self._group_worker.cancelled.connect(self._on_group_cancelled)
        self._group_worker.error.connect(self._on_group_error)
        self._group_worker.finished.connect(self._on_group_thread_finished)
        self._set_grouping_busy(True)
        self._group_worker.start()

    def _set_grouping_busy(self, busy: bool) -> None:
        self._settings_panel.group_tab.set_running(busy)
        for b in (self._add_files_btn, self._add_folder_btn, self._remove_btn,
                  self._clear_btn, self._preview_btn, self._process_btn):
            b.setEnabled(not busy)
        if busy:
            self._status_label.setText("그룹핑 중...")
        else:
            self._update_buttons()

    def _on_group_cancel(self) -> None:
        if self._group_worker is not None:
            self._group_worker.requestInterruption()

    def _on_group_thread_finished(self) -> None:
        worker, self._group_worker = self._group_worker, None
        if worker is not None:
            worker.deleteLater()

    def _on_group_done(self, session, result) -> None:
        self._session = session
        self._analysis_key = correction_key(self._settings)
        self._settings_panel.group_tab.set_stale(False)
        self._thumb_panel.set_options(
            self._settings.show_reason, self._settings.show_score, self._settings.weights()
        )
        self._thumb_panel.set_session(session)
        self._set_grouping_busy(False)
        self._set_grouping_controls(True)
        self._group_view_btn.setChecked(True)
        summary = (
            f"{len(session.photos_flat())}장 → {session.group_count()}개 그룹\n"
            f"단독 {session.single_count()}장 · 채택 {session.adopted_count()}장 · "
            f"검토 완료 {session.reviewed_count()} / {session.group_count()}"
        )
        warning = f"촬영 시각 없음 {result.no_time_count}장" if result.no_time_count else ""
        self._settings_panel.group_tab.show_result(summary, result.message, warning)
        self._apply_view()

    def _on_group_cancelled(self) -> None:
        self._set_grouping_busy(False)
        self._status_label.setText("그룹핑을 취소했습니다.")

    def _on_group_error(self, msg: str) -> None:
        self._set_grouping_busy(False)
        self._status_label.setText(f"그룹핑 오류: {msg}")
        QMessageBox.warning(self, "그룹핑 오류", msg)

    def _check_stale_scores(self) -> None:
        if self._session is None or self._analysis_key is None:
            return
        self._settings_panel.group_tab.set_stale(
            correction_key(self._settings) != self._analysis_key
        )

    def _on_rescore(self) -> None:
        if self._session is None or self._rescore_worker is not None:
            return
        from myphotoworks.workers.group_worker import RescoreWorker

        photos = self._session.photos_flat()
        self._rescore_worker = RescoreWorker(photos, dataclasses.replace(self._settings))
        self._rescore_worker.progress.connect(self._on_rescore_progress)
        self._rescore_worker.done.connect(self._on_rescore_done)
        self._rescore_worker.error.connect(self._on_group_error)
        self._rescore_worker.finished.connect(self._on_rescore_thread_finished)
        self._analysis_key_pending = correction_key(self._settings)
        self._settings_panel.group_tab.set_running(True)
        self._rescore_worker.start()

    def _on_rescore_progress(self, stage: str, cur: int, total: int) -> None:
        self._settings_panel.group_tab.set_progress(stage, cur, total)

    def _on_rescore_done(self, count: int) -> None:
        self._settings_panel.group_tab.set_running(False)
        if self._session is None:
            return
        self._analysis_key = self._analysis_key_pending
        self._session.rescore(self._settings.weights())
        self._check_stale_scores()
        self._on_review_changed()
        self._status_label.setText(f"노출·색감 점수를 다시 계산했습니다. ({count}장)")

    def _on_rescore_thread_finished(self) -> None:
        worker, self._rescore_worker = self._rescore_worker, None
        if worker is not None:
            worker.deleteLater()

    def _on_weights_changed(self) -> None:
        if self._session is None:
            return
        self._session.rescore(self._settings.weights())
        self._on_display_changed()
        self._on_review_changed()

    def _on_display_changed(self) -> None:
        self._thumb_panel.set_options(
            self._settings.show_reason, self._settings.show_score, self._settings.weights()
        )
        self._update_buttons()

    def _on_adoption_toggle(self, photo: PhotoItem, value: bool) -> None:
        if self._session is None:
            return
        self._session.set_adopted(photo, value)
        self._on_review_changed()

    def _on_review_changed(self) -> None:
        self._thumb_panel.rebuild()
        self._update_buttons()
        if self._review_win is not None:
            self._review_win.refresh()

    def _on_review(self) -> None:
        if self._session is None:
            return
        if self._review_win is not None:
            self._review_win.raise_()
            self._review_win.activateWindow()
            return
        from myphotoworks.ui.group_review_window import GroupReviewWindow

        win = GroupReviewWindow(self._session, self._settings)
        win.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        win.changed.connect(self._on_review_window_changed)
        win.destroyed.connect(lambda _o=None: setattr(self, "_review_win", None))
        self._review_win = win
        win.show()

    def _on_review_window_changed(self) -> None:
        self._thumb_panel.rebuild()
        self._update_buttons()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _update_buttons(self) -> None:
        total = len(self._thumb_panel.all_photos())
        shown = len(self._thumb_panel.photos())
        has_photos = total > 0
        self._remove_btn.setEnabled(has_photos)
        self._clear_btn.setEnabled(has_photos)
        self._preview_btn.setEnabled(shown > 0)
        self._process_btn.setEnabled(shown > 0)
        self._process_btn.setText(f"일괄 적용 ({shown}장)" if shown else "일괄 적용")
        self._settings_panel.group_tab.set_has_photos(has_photos)
        if self._session is not None:
            self._status_label.setText(
                f"표시 {shown}장 / 전체 {total}장 · {self._session.group_count()}그룹 · "
                f"채택 {self._session.adopted_count()}장"
                + (" · 채택만 보기" if self._adopted_only_cb.isChecked() else "")
            )
        elif has_photos:
            self._status_label.setText(f"{total}장 로드됨")
        else:
            self._status_label.setText("사진을 추가하세요.")

    def _set_processing(self, processing: bool) -> None:
        self._add_files_btn.setEnabled(not processing)
        self._add_folder_btn.setEnabled(not processing)
        self._remove_btn.setEnabled(not processing)
        self._clear_btn.setEnabled(not processing)
        self._preview_btn.setEnabled(not processing)
        self._process_btn.setEnabled(not processing)

    # ------------------------------------------------------------------
    # Window geometry persistence
    # ------------------------------------------------------------------

    def _restore_geometry(self) -> None:
        if geom := self._cfg.get("window_geometry"):
            try:
                from PyQt6.QtCore import QByteArray
                self.restoreGeometry(QByteArray.fromHex(geom.encode()))
            except Exception:
                pass

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if not hasattr(self, "_sysmenu_patched"):
            self._sysmenu_patched = True
            self._patch_system_menu()

    def _patch_system_menu(self) -> None:
        """Windows 시스템 메뉴(타이틀바 우클릭)에 '정보' 항목을 추가한다."""
        import ctypes

        MF_SEPARATOR = 0x0800
        MF_STRING = 0x0000
        hwnd = int(self.winId())
        hmenu = ctypes.windll.user32.GetSystemMenu(hwnd, False)
        ctypes.windll.user32.AppendMenuW(hmenu, MF_SEPARATOR, 0, None)
        ctypes.windll.user32.AppendMenuW(hmenu, MF_STRING, _SYSMENU_ABOUT_ID, "정보")

    def nativeEvent(self, event_type, message):  # noqa: N802
        # NOTE: super().nativeEvent() crashes in PyQt6 6.10.x — return (False, 0) for
        # unhandled messages instead, which tells Qt to continue default processing.
        if _WinMSG is not None and event_type == b"windows_generic_MSG":
            try:
                addr = int(message)
                if addr:
                    msg = _WinMSG.from_address(addr)
                    if msg.message == _WM_SYSCOMMAND and msg.wParam == _SYSMENU_ABOUT_ID:
                        self._on_about()
                        return True, 0
            except Exception:
                pass
        return False, 0

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0.0, QColor("#0d1117"))
        gradient.setColorAt(0.5, QColor("#161b22"))
        gradient.setColorAt(1.0, QColor("#1c2333"))
        painter.fillRect(self.rect(), gradient)

    def closeEvent(self, event) -> None:  # noqa: N802
        self._cfg["window_geometry"] = self.saveGeometry().toHex().data().decode()
        save_settings(self._cfg, self._settings)
        save_config(self._cfg)
        super().closeEvent(event)
