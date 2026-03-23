import sys

from PyQt6.QtWidgets import QApplication

from myphotoworks.ui.main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    app.setStyle("windowsvista")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
