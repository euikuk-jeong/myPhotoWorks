"""MainWindow — file list (left, large) + settings panel (right) + bottom action bar."""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
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
from myphotoworks.ui.settings_panel import SettingsPanel
from myphotoworks.ui.thumbnail_panel import ThumbnailPanel
from myphotoworks.utils.config import load_config, load_settings, save_config, save_settings

SUPPORTED_FILTER = (
    "이미지 파일 (*.jpg *.jpeg *.png *.tif *.tiff *.bmp *.webp);;"
    "모든 파일 (*)"
)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("myPhotoWorks")
        self.resize(1100, 700)

        self._cfg = load_config()
        self._settings = load_settings(self._cfg)
        self._worker = None

        self._build_ui()
        self._restore_geometry()

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
        splitter.addWidget(self._thumb_panel)

        self._settings_panel = SettingsPanel(self._settings)
        self._settings_panel.settings_changed.connect(self._on_settings_changed)
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
        QMessageBox.information(
            self,
            "일괄 적용 완료",
            f"처리가 완료되었습니다.\n\n전체 {total}개 중 {saved}개가 저장되었습니다.",
        )

    def _on_process_error(self, msg: str) -> None:
        self._status_label.setText(f"오류: {msg}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _update_buttons(self) -> None:
        count = len(self._thumb_panel.photos())
        has_photos = count > 0
        self._remove_btn.setEnabled(has_photos)
        self._clear_btn.setEnabled(has_photos)
        self._preview_btn.setEnabled(has_photos)
        self._process_btn.setEnabled(has_photos)
        if has_photos:
            self._status_label.setText(f"{count}장 로드됨")
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

    def closeEvent(self, event) -> None:  # noqa: N802
        self._cfg["window_geometry"] = self.saveGeometry().toHex().data().decode()
        save_settings(self._cfg, self._settings)
        save_config(self._cfg)
        super().closeEvent(event)
