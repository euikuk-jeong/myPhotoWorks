"""MethodDialog — "추천 방식": the chain of criteria of the selected group and the rules around it.

The text comes from ``core.explain.chain_overview`` (written from the same criteria and constants
the recommendation uses) and ``group_walkthrough`` ("이 그룹에서는": how the chain went through
this very group). A button opens the online guide for the full story.
"""
from __future__ import annotations

from collections.abc import Sequence

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from myphotoworks.core.explain import Overview
from myphotoworks.ui.guide import open_guide


class MethodDialog(QDialog):
    def __init__(
        self,
        overview: Overview,
        parent: QWidget | None = None,
        walkthrough: Sequence[str] = (),
    ) -> None:
        super().__init__(parent)
        self.setModal(False)
        self.setMinimumWidth(460)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 16)
        layout.setSpacing(8)
        self._heading = QLabel()
        self._heading.setObjectName("viewTitle")
        layout.addWidget(self._heading)
        self._steps = QLabel()
        self._steps.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self._steps)
        self._walk_heading = QLabel()
        self._walk_heading.setObjectName("sectionTitle")
        layout.addWidget(self._walk_heading)
        self._walk = QLabel()
        self._walk.setWordWrap(True)
        self._walk.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self._walk)
        self._notes: list[QLabel] = []
        self._notes_box = QVBoxLayout()
        self._notes_box.setSpacing(6)
        layout.addLayout(self._notes_box)
        layout.addStretch(1)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        guide = QPushButton("설명서 열기")
        guide.clicked.connect(lambda: open_guide(self))
        close = QPushButton("닫기")
        close.clicked.connect(self.close)
        buttons.addWidget(guide)
        buttons.addWidget(close)
        layout.addLayout(buttons)
        self.set_overview(overview, walkthrough)

    def set_overview(self, overview: Overview, walkthrough: Sequence[str] = ()) -> None:
        """Show another overview in this dialog (the selected group changed). ``walkthrough`` is
        how the chain went through the group; without it the section is hidden."""
        self.setWindowTitle(overview.title)
        self._heading.setText(overview.title)
        self._steps.setText("\n".join(overview.steps))
        self._walk_heading.setText("이 그룹에서는" if walkthrough else "")
        self._walk_heading.setVisible(bool(walkthrough))
        self._walk.setText("\n".join(walkthrough))
        self._walk.setVisible(bool(walkthrough))
        for label in self._notes:
            self._notes_box.removeWidget(label)
            label.deleteLater()
        self._notes = []
        for note in overview.notes:
            label = QLabel(note)
            label.setObjectName("hint-label")
            label.setWordWrap(True)
            label.setTextFormat(Qt.TextFormat.PlainText)
            self._notes_box.addWidget(label)
            self._notes.append(label)
