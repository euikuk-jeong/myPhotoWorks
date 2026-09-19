"""Open the bundled algorithm guide (a self-contained HTML file) in the default browser."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import QMessageBox, QWidget

GUIDE_NAME = "algorithm_guide.html"
GUIDE_TITLE = "그룹핑·추천 방식 설명서"


def guide_source_path() -> Path:
    """Bundled guide, both in a normal checkout and inside a PyInstaller bundle."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "myphotoworks" / "resources" / GUIDE_NAME
    return Path(__file__).resolve().parent.parent / "resources" / GUIDE_NAME


def default_guide_dir() -> Path:
    return Path.home() / ".myphotoworks" / "guide"


def prepare_guide(dest_dir: Path | None = None, source: Path | None = None) -> Path:
    """Copy the guide to a stable location and return its path.

    A one-file EXE unpacks itself into a temporary folder that disappears on exit, so the
    browser is pointed at a copy outside of it. The copy is refreshed when the bundled
    guide changes (e.g. after an update).
    """
    src = source or guide_source_path()
    if not src.is_file():
        raise FileNotFoundError(str(src))
    dest_dir = dest_dir or default_guide_dir()
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / GUIDE_NAME
    if not dest.exists() or dest.read_bytes() != src.read_bytes():
        shutil.copyfile(src, dest)
    return dest


def open_guide(parent: QWidget | None = None) -> bool:
    """Open the guide in the default browser. Shows a message box on failure."""
    try:
        path = prepare_guide()
    except OSError as e:
        QMessageBox.warning(parent, GUIDE_TITLE, f"설명서를 열 수 없습니다.\n{e}")
        return False
    if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
        QMessageBox.information(
            parent, GUIDE_TITLE,
            f"브라우저를 자동으로 열지 못했습니다.\n아래 파일을 직접 열어 주세요.\n\n{path}",
        )
        return False
    return True
