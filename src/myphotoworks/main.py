import logging
import sys
from pathlib import Path

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from myphotoworks.ui.main_window import MainWindow
from myphotoworks.ui.styles import load_glass_theme

def _get_resource_path(relative: str) -> Path:
    """Return the absolute path to a bundled resource (works both in dev and PyInstaller)."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
    return base / "myphotoworks" / relative if hasattr(sys, "_MEIPASS") else Path(__file__).parent / relative


_ICON_PATH = _get_resource_path("resources/myphotoworks.ico")


def _set_windows_appid() -> None:
    """Set the Windows AppUserModelID so the taskbar/titlebar icon is displayed correctly."""
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("myphotoworks.app")  # type: ignore[attr-defined]
    except Exception:
        pass


def main() -> None:
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s.%(msecs)03d %(levelname)-5s %(name)s  %(message)s",
        datefmt="%H:%M:%S",
    )
    # Silence noisy PIL/Pillow debug logs (TiffImagePlugin tag dumps, etc.)
    logging.getLogger("PIL").setLevel(logging.WARNING)
    _set_windows_appid()
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(load_glass_theme())
    if _ICON_PATH.exists():
        app.setWindowIcon(QIcon(str(_ICON_PATH)))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
