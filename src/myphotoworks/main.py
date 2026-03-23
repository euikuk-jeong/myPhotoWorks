import sys

from PyQt6.QtWidgets import QApplication, QMainWindow, QLabel
from PyQt6.QtCore import Qt


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("myPhotoWorks")
        self.resize(900, 600)

        placeholder = QLabel("myPhotoWorks — UI 준비 중")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCentralWidget(placeholder)


def main() -> None:
    app = QApplication(sys.argv)
    app.setStyle("windowsvista")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
