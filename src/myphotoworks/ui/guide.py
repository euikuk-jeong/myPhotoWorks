"""Open the online algorithm guide (published from the repository's guide/ folder)."""
from __future__ import annotations

from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import QMessageBox, QWidget

GUIDE_TITLE = "그룹핑·추천 방식 설명서"
GUIDE_FILE = "algorithm_guide.html"
# GitHub Pages site built from the guide/ folder (.github/workflows/guide-pages.yml)
GUIDE_URL = f"https://euikuk-jeong.github.io/myPhotoWorks/{GUIDE_FILE}"


def open_guide(parent: QWidget | None = None) -> bool:
    """Open the guide in the default browser. Shows the address if that is not possible."""
    if QDesktopServices.openUrl(QUrl(GUIDE_URL)):
        return True
    QMessageBox.information(
        parent, GUIDE_TITLE,
        "브라우저를 자동으로 열지 못했습니다.\n"
        f"아래 주소를 브라우저에 붙여넣어 주세요.\n\n{GUIDE_URL}",
    )
    return False
