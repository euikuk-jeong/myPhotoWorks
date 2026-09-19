"""GroupWorker — QThread that analyses and groups photos off the UI thread."""
from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from myphotoworks.models.photo_item import PhotoItem
from myphotoworks.models.settings import AppSettings
from myphotoworks.processing.group_runner import (
    Cancelled,
    refresh_correction_scores,
    run_grouping,
)


class GroupWorker(QThread):
    """Signals
    -------
    progress(stage, current, total)
    done(GroupSession, GroupingResult)
    cancelled()
    error(message)
    """

    progress = pyqtSignal(str, int, int)
    done = pyqtSignal(object, object)
    cancelled = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, photos: list[PhotoItem], settings: AppSettings) -> None:
        super().__init__()
        self._photos = list(photos)
        self._settings = settings

    def run(self) -> None:
        try:
            session, result = run_grouping(
                self._photos,
                self._settings,
                progress=lambda stage, cur, total: self.progress.emit(stage, cur, total),
                is_cancelled=self.isInterruptionRequested,
            )
        except Cancelled:
            self.cancelled.emit()
            return
        except Exception as e:
            self.error.emit(str(e))
            return
        self.done.emit(session, result)


class RescoreWorker(QThread):
    """Recompute exposure / colour scores after correction settings changed."""

    progress = pyqtSignal(str, int, int)
    done = pyqtSignal(int)
    error = pyqtSignal(str)

    def __init__(self, photos: list[PhotoItem], settings: AppSettings) -> None:
        super().__init__()
        self._photos = list(photos)
        self._settings = settings

    def run(self) -> None:
        try:
            n = refresh_correction_scores(
                self._photos,
                self._settings,
                progress=lambda stage, cur, total: self.progress.emit(stage, cur, total),
                is_cancelled=self.isInterruptionRequested,
            )
        except Cancelled:
            self.done.emit(0)
            return
        except Exception as e:
            self.error.emit(str(e))
            return
        self.done.emit(n)
