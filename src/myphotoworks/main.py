import logging
import sys
from pathlib import Path

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from myphotoworks.ui.main_window import MainWindow

_ICON_PATH = Path(__file__).parent / "resources" / "myphotoworks.ico"


def main() -> None:
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s.%(msecs)03d %(levelname)-5s %(name)s  %(message)s",
        datefmt="%H:%M:%S",
    )
    # Silence noisy PIL/Pillow debug logs (TiffImagePlugin tag dumps, etc.)
    logging.getLogger("PIL").setLevel(logging.WARNING)
    app = QApplication(sys.argv)
    app.setStyle("windowsvista")
    if _ICON_PATH.exists():
        app.setWindowIcon(QIcon(str(_ICON_PATH)))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
