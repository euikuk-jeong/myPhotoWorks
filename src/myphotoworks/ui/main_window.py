"""MainWindow — two-panel layout: ThumbnailPanel (left) + SettingsPanel (right)."""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
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
from myphotoworks.utils.config import load_config, save_config

SUPPORTED_FILTER = (
    "이미지 파일 (*.jpg *.jpeg *.png *.tif *.tiff *.bmp *.webp);;"
    "모든 파일 (*)"
)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("myPhotoWorks")
        self.resize(960, 640)

        self._settings = AppSettings()
        self._cfg = load_config()

        # Restore last output directory
        if last_dir := self._cfg.get("last_output_dir"):
            self._settings.output_dir = Path(last_dir)

        self._build_ui()
        self._restore_geometry()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(4, 4, 4, 4)
        root_layout.setSpacing(4)

        # --- Top button bar ---
        btn_bar = QHBoxLayout()

        self._choose_btn = QPushButton("Choose")
        self._choose_btn.setFixedHeight(28)
        self._choose_btn.clicked.connect(self._on_choose)
        btn_bar.addWidget(self._choose_btn)

        self._clear_btn = QPushButton("Clear")
        self._clear_btn.setFixedHeight(28)
        self._clear_btn.clicked.connect(self._on_clear)
        btn_bar.addWidget(self._clear_btn)

        btn_bar.addStretch()

        self._process_btn = QPushButton("처리 시작")
        self._process_btn.setFixedHeight(28)
        self._process_btn.setEnabled(False)
        self._process_btn.clicked.connect(self._on_process)
        btn_bar.addWidget(self._process_btn)

        root_layout.addLayout(btn_bar)

        # --- Splitter: thumbnail panel | settings panel ---
        splitter = QSplitter(Qt.Orientation.Horizontal)

        self._thumb_panel = ThumbnailPanel()
        self._thumb_panel.photo_selected.connect(self._on_photo_selected)
        self._thumb_panel.photo_double_clicked.connect(self._on_photo_double_clicked)
        splitter.addWidget(self._thumb_panel)

        self._settings_panel = SettingsPanel(self._settings)
        self._settings_panel.settings_changed.connect(self._on_settings_changed)
        splitter.addWidget(self._settings_panel)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        root_layout.addWidget(splitter)

        # --- Status bar ---
        status_bar = QStatusBar()
        self.setStatusBar(status_bar)

        self._status_label = QLabel("사진을 선택하세요.")
        status_bar.addWidget(self._status_label, 1)

        self._progress_bar = QProgressBar()
        self._progress_bar.setFixedWidth(200)
        self._progress_bar.setVisible(False)
        status_bar.addPermanentWidget(self._progress_bar)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_choose(self) -> None:
        last_dir = self._cfg.get("last_open_dir", str(Path.home()))
        paths, _ = QFileDialog.getOpenFileNames(
            self, "사진 선택", last_dir, SUPPORTED_FILTER
        )
        if not paths:
            return

        photo_paths = [Path(p) for p in paths]
        self._thumb_panel.add_photos(photo_paths)

        self._cfg["last_open_dir"] = str(photo_paths[0].parent)
        save_config(self._cfg)

        count = len(self._thumb_panel.photos())
        self._status_label.setText(f"{count}장 로드됨")
        self._process_btn.setEnabled(count > 0)

    def _on_clear(self) -> None:
        self._thumb_panel.clear_all()
        self._status_label.setText("사진을 선택하세요.")
        self._process_btn.setEnabled(False)

    def _on_photo_selected(self, photo: PhotoItem) -> None:
        self._status_label.setText(photo.source_path.name)

    def _on_photo_double_clicked(self, photo: PhotoItem) -> None:
        # Preview window — Phase 4에서 구현
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(
            self,
            "프리뷰",
            f"{photo.source_path.name}\n\n(프리뷰는 Phase 4에서 구현 예정)",
        )

    def _on_settings_changed(self, settings: AppSettings) -> None:
        self._settings = settings
        last_out = str(settings.output_dir)
        self._cfg["last_output_dir"] = last_out
        save_config(self._cfg)

    def _on_process(self) -> None:
        photos = self._thumb_panel.photos()
        if not photos:
            return

        from myphotoworks.workers.batch_worker import BatchWorker
        self._worker = BatchWorker(photos, self._settings)
        self._worker.progress.connect(self._on_progress)
        self._worker.photo_done.connect(self._thumb_panel.update_status)
        self._worker.finished.connect(self._on_process_finished)
        self._worker.error.connect(self._on_process_error)

        self._progress_bar.setRange(0, len(photos))
        self._progress_bar.setValue(0)
        self._progress_bar.setVisible(True)
        self._process_btn.setEnabled(False)
        self._choose_btn.setEnabled(False)
        self._worker.start()

    def _on_progress(self, current: int, total: int) -> None:
        self._progress_bar.setValue(current)
        self._status_label.setText(f"처리 중... {current}/{total}")

    def _on_process_finished(self) -> None:
        self._progress_bar.setVisible(False)
        self._process_btn.setEnabled(True)
        self._choose_btn.setEnabled(True)
        total = len(self._thumb_panel.photos())
        self._status_label.setText(f"완료: {total}장 처리됨")

    def _on_process_error(self, msg: str) -> None:
        self._progress_bar.setVisible(False)
        self._process_btn.setEnabled(True)
        self._choose_btn.setEnabled(True)
        self._status_label.setText(f"오류: {msg}")

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
        save_config(self._cfg)
        super().closeEvent(event)
