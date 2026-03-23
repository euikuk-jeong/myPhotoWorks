"""BatchWorker — QThread that processes photos sequentially."""
from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from myphotoworks.models.photo_item import PhotoItem, ProcessStatus
from myphotoworks.models.settings import AppSettings
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

    def __init__(self, photos: list[PhotoItem], settings: AppSettings) -> None:
        super().__init__()
        self._photos = photos
        self._settings = settings

    def run(self) -> None:
        total = len(self._photos)
        output_dir = self._settings.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        for i, photo in enumerate(self._photos, start=1):
            photo.status = ProcessStatus.PROCESSING
            self.photo_done.emit(photo)
            try:
                image = processor.process(photo, self._settings)

                ext = ".jpg" if self._settings.output_format == "JPEG" else ".png"
                out_path = output_dir / (photo.source_path.stem + ext)
                processor.save(image, out_path, self._settings, photo.source_path)

                photo.status = ProcessStatus.DONE
            except Exception as e:
                photo.status = ProcessStatus.ERROR
                photo.error_message = str(e)

            self.photo_done.emit(photo)
            self.progress.emit(i, total)

        self.finished.emit()
