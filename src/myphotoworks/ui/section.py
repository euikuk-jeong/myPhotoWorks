"""Section — a settings group drawn as a full-width header band that folds its content.

Drop-in for QGroupBox: callers still do ``QVBoxLayout(section)`` and ``section.title()``.
The header is a child button laid over the top ``HEADER_H`` pixels; the caller's layout
must leave that space free (SettingsPanel sets the layout margins).
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QGroupBox, QSizePolicy, QToolButton, QWidget

HEADER_H = 30


class Section(QGroupBox):
    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._title = title
        self._hidden_while_collapsed: list[QWidget] = []
        self._header = QToolButton(self)
        self._header.setObjectName("sectionHeader")  # band style in light_table.qss
        self._header.setText(title)
        self._header.setCheckable(True)
        self._header.setChecked(True)
        self._header.setArrowType(Qt.ArrowType.DownArrow)
        self._header.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._header.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._header.setCursor(Qt.CursorShape.PointingHandCursor)
        self._header.toggled.connect(self._set_expanded)

    # QGroupBox API used by callers and tests
    def title(self) -> str:  # noqa: D401 - Qt naming
        return self._title

    def setTitle(self, title: str) -> None:  # noqa: N802
        self._title = title
        self._header.setText(title)

    def is_expanded(self) -> bool:
        return self._header.isChecked()

    def set_expanded(self, expanded: bool) -> None:
        self._header.setChecked(expanded)

    def _content(self) -> list[QWidget]:
        direct = Qt.FindChildOption.FindDirectChildrenOnly
        return [w for w in self.findChildren(QWidget, options=direct) if w is not self._header]

    def _set_expanded(self, expanded: bool) -> None:
        self._header.setArrowType(Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow)
        if expanded:
            # restore only what was visible before folding (some content is hidden on purpose)
            for w in self._hidden_while_collapsed:
                w.setVisible(True)
            self._hidden_while_collapsed = []
        else:
            self._hidden_while_collapsed = [w for w in self._content() if w.isVisibleTo(self)]
            for w in self._hidden_while_collapsed:
                w.setVisible(False)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._header.setGeometry(0, 0, self.width(), HEADER_H)
