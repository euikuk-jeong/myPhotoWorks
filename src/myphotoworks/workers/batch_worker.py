"""BatchWorker — QThread that processes photos sequentially."""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from myphotoworks.models.photo_item import PhotoItem, ProcessStatus
from myphotoworks.models.settings import AppSettings, OutputPathMode
from myphotoworks.processing import processor


class BatchWorker(QThread):
    """Process a list of PhotoItems off the UI thread.

    Signals
    -------
    progress(current, total)
    photo_done(PhotoItem)
    finished()
    error(message)
    """

    progress = pyqtSignal(int, int)
    photo_done = pyqtSignal(object)
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(
        self,
        photos: list[PhotoItem],
        settings: AppSettings,
        first_file_dir: Path | None = None,
    ) -> None:
        super().__init__()
        self._photos = photos
        self._settings = settings
        # FIRST_FILE 모드에서 사용할 기준 디렉터리
        self._first_file_dir = first_file_dir or (
            photos[0].source_path.parent if photos else Path(".")
        )

    def run(self) -> None:
        total = len(self._photos)

        for i, photo in enumerate(self._photos, start=1):
            photo.status = ProcessStatus.PROCESSING
            self.photo_done.emit(photo)
            try:
                image = processor.process(photo, self._settings)
                out_path = self._resolve_output_path(photo)
                out_path.parent.mkdir(parents=True, exist_ok=True)
                processor.save(image, out_path, self._settings, photo.source_path)
                photo.status = ProcessStatus.DONE
            except Exception as e:
                photo.status = ProcessStatus.ERROR
                photo.error_message = str(e)
                self.error.emit(str(e))

            self.photo_done.emit(photo)
            self.progress.emit(i, total)

        self.finished.emit()

    def _resolve_output_path(self, photo: PhotoItem) -> Path:
        mode = self._settings.output_path_mode
        stem = self._settings.output_prefix + photo.source_path.stem + self._settings.output_suffix

        if mode == OutputPathMode.FIRST_FILE:
            out_dir = self._first_file_dir / "output"
        elif mode == OutputPathMode.PER_FILE:
            out_dir = photo.source_path.parent / "output"
        else:  # CUSTOM
            out_dir = self._settings.output_custom_dir

        return out_dir / (stem + ".jpg")
