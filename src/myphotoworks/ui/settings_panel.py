"""SettingsPanel — QTabWidget with all setting tabs.

Tabs: Home | Name | Signature | PPI | Output | Configuration | Help
Phase 3 fully implements the Home tab and Output tab.
Remaining tabs show placeholders.
"""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QSpinBox,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from myphotoworks.models.settings import AppSettings


class SettingsPanel(QTabWidget):
    """Tab widget that owns and exposes AppSettings.

    Signal
    ------
    settings_changed(AppSettings)
        Emitted whenever any setting is modified.
    """

    settings_changed = pyqtSignal(object)

    def __init__(self, settings: AppSettings, parent=None) -> None:
        super().__init__(parent)
        self._settings = settings

        self.addTab(self._build_home_tab(), "Home")
        self.addTab(self._build_placeholder("Name"), "Name")
        self.addTab(self._build_placeholder("Signature"), "Signature")
        self.addTab(self._build_placeholder("PPI"), "PPI")
        self.addTab(self._build_output_tab(), "Output")
        self.addTab(self._build_placeholder("Configuration"), "Configuration")
        self.addTab(self._build_help_tab(), "Help")

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def settings(self) -> AppSettings:
        return self._settings

    # ------------------------------------------------------------------
    # Home Tab
    # ------------------------------------------------------------------

    def _build_home_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(8)

        # --- Filter group ---
        filter_group = QGroupBox("Filter")
        filter_layout = QVBoxLayout(filter_group)

        # 흑백
        self._bw_cb = QCheckBox("흑백 조절")
        self._bw_cb.setChecked(self._settings.bw_enabled)
        self._bw_cb.toggled.connect(self._on_bw_toggled)
        filter_layout.addWidget(self._bw_cb)

        # Level
        level_row = QHBoxLayout()
        level_row.addWidget(QLabel("Level"))
        self._level_min_spin = QSpinBox()
        self._level_min_spin.setRange(0, 254)
        self._level_min_spin.setValue(self._settings.level_min)
        self._level_min_spin.valueChanged.connect(self._on_level_changed)
        level_row.addWidget(self._level_min_spin)
        level_row.addWidget(QLabel("~"))
        self._level_max_spin = QSpinBox()
        self._level_max_spin.setRange(1, 255)
        self._level_max_spin.setValue(self._settings.level_max)
        self._level_max_spin.valueChanged.connect(self._on_level_changed)
        level_row.addWidget(self._level_max_spin)
        level_row.addStretch()
        filter_layout.addLayout(level_row)

        layout.addWidget(filter_group)

        # --- Auto correction group ---
        auto_group = QGroupBox("Auto Correction")
        auto_layout = QHBoxLayout(auto_group)

        self._auto_level_cb = QCheckBox("Auto Level 조절")
        self._auto_level_cb.setChecked(self._settings.auto_level)
        self._auto_level_cb.toggled.connect(self._on_auto_level_toggled)
        auto_layout.addWidget(self._auto_level_cb)

        self._auto_contrast_cb = QCheckBox("Auto Contrast 조절")
        self._auto_contrast_cb.setChecked(self._settings.auto_contrast)
        self._auto_contrast_cb.toggled.connect(self._on_auto_contrast_toggled)
        auto_layout.addWidget(self._auto_contrast_cb)

        layout.addWidget(auto_group)

        # --- Brightness / Contrast group ---
        bc_group = QGroupBox("Brightness / Contrast")
        bc_layout = QFormLayout(bc_group)

        self._brightness_slider = _LabeledSlider(-100, 100, self._settings.brightness)
        self._brightness_slider.valueChanged.connect(self._on_brightness_changed)
        bc_layout.addRow("Brightness", self._brightness_slider)

        self._contrast_slider = _LabeledSlider(-100, 100, self._settings.contrast)
        self._contrast_slider.valueChanged.connect(self._on_contrast_changed)
        bc_layout.addRow("Contrast", self._contrast_slider)

        layout.addWidget(bc_group)

        # --- Sharpen / Gaussian group ---
        sg_group = QGroupBox("Sharpen / Gaussian")
        sg_layout = QFormLayout(sg_group)

        self._sharpen_cb = QCheckBox("Sharpener")
        self._sharpen_cb.setChecked(self._settings.sharpen_enabled)
        self._sharpen_cb.toggled.connect(self._on_sharpen_toggled)
        sg_layout.addRow(self._sharpen_cb)

        self._gaussian_cb = QCheckBox("Gaussi")
        self._gaussian_cb.setChecked(self._settings.gaussian_enabled)
        self._gaussian_cb.toggled.connect(self._on_gaussian_toggled)
        sg_layout.addRow(self._gaussian_cb)

        layout.addWidget(sg_group)
        layout.addStretch()

        return tab

    # ------------------------------------------------------------------
    # Output Tab
    # ------------------------------------------------------------------

    def _build_output_tab(self) -> QWidget:
        tab = QWidget()
        layout = QFormLayout(tab)
        layout.setSpacing(10)

        # Output directory
        dir_row = QHBoxLayout()
        self._output_dir_edit = QLineEdit(str(self._settings.output_dir))
        self._output_dir_edit.setReadOnly(True)
        dir_row.addWidget(self._output_dir_edit)
        browse_btn = QPushButton("...")
        browse_btn.setFixedWidth(30)
        browse_btn.clicked.connect(self._on_browse_output_dir)
        dir_row.addWidget(browse_btn)
        layout.addRow("출력 경로", dir_row)

        # Format
        self._format_combo = QComboBox()
        self._format_combo.addItems(["JPEG", "PNG"])
        self._format_combo.setCurrentText(self._settings.output_format)
        self._format_combo.currentTextChanged.connect(self._on_format_changed)
        layout.addRow("포맷", self._format_combo)

        # Quality
        self._quality_slider = _LabeledSlider(1, 100, self._settings.output_quality)
        self._quality_slider.valueChanged.connect(self._on_quality_changed)
        layout.addRow("품질 (JPEG)", self._quality_slider)

        # Resize
        resize_row = QHBoxLayout()
        self._resize_w_spin = QSpinBox()
        self._resize_w_spin.setRange(0, 9999)
        self._resize_w_spin.setValue(self._settings.resize_width)
        self._resize_w_spin.setSuffix(" px")
        self._resize_w_spin.valueChanged.connect(self._on_resize_changed)
        resize_row.addWidget(QLabel("W"))
        resize_row.addWidget(self._resize_w_spin)

        self._resize_h_spin = QSpinBox()
        self._resize_h_spin.setRange(0, 9999)
        self._resize_h_spin.setValue(self._settings.resize_height)
        self._resize_h_spin.setSuffix(" px")
        self._resize_h_spin.valueChanged.connect(self._on_resize_changed)
        resize_row.addWidget(QLabel("H"))
        resize_row.addWidget(self._resize_h_spin)

        self._resize_cb = QCheckBox("리사이즈")
        self._resize_cb.setChecked(self._settings.resize_enabled)
        self._resize_cb.toggled.connect(self._on_resize_toggled)
        resize_row.addWidget(self._resize_cb)
        layout.addRow("크기", resize_row)

        return tab

    # ------------------------------------------------------------------
    # Help Tab
    # ------------------------------------------------------------------

    def _build_help_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        browser = QTextBrowser()
        browser.setHtml("""
        <h3>myPhotoWorks 사용법</h3>
        <ol>
          <li><b>Choose</b> 버튼으로 사진을 선택하거나 왼쪽 패널에 드래그&드롭</li>
          <li>Home 탭에서 보정 옵션 설정</li>
          <li>Output 탭에서 출력 경로·포맷·크기 설정</li>
          <li><b>처리 시작</b> 버튼으로 일괄 처리</li>
        </ol>
        <h4>단축키</h4>
        <ul>
          <li>Ctrl+O : 사진 열기</li>
          <li>Space : 프리뷰 열기</li>
        </ul>
        """)
        layout.addWidget(browser)
        return tab

    # ------------------------------------------------------------------
    # Placeholder
    # ------------------------------------------------------------------

    def _build_placeholder(self, name: str) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        label = QLabel(f"{name} 탭 — 구현 예정")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)
        return tab

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _emit(self) -> None:
        self.settings_changed.emit(self._settings)

    def _on_bw_toggled(self, checked: bool) -> None:
        self._settings.bw_enabled = checked
        self._emit()

    def _on_level_changed(self) -> None:
        mn = self._level_min_spin.value()
        mx = self._level_max_spin.value()
        if mn >= mx:
            return
        self._settings.level_min = mn
        self._settings.level_max = mx
        self._emit()

    def _on_auto_level_toggled(self, checked: bool) -> None:
        self._settings.auto_level = checked
        self._emit()

    def _on_auto_contrast_toggled(self, checked: bool) -> None:
        self._settings.auto_contrast = checked
        self._emit()

    def _on_brightness_changed(self, value: int) -> None:
        self._settings.brightness = value
        self._emit()

    def _on_contrast_changed(self, value: int) -> None:
        self._settings.contrast = value
        self._emit()

    def _on_sharpen_toggled(self, checked: bool) -> None:
        self._settings.sharpen_enabled = checked
        if checked:
            self._gaussian_cb.setChecked(False)
        self._emit()

    def _on_gaussian_toggled(self, checked: bool) -> None:
        self._settings.gaussian_enabled = checked
        if checked:
            self._sharpen_cb.setChecked(False)
        self._emit()

    def _on_browse_output_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "출력 폴더 선택",
                                                str(self._settings.output_dir))
        if path:
            self._settings.output_dir = Path(path)
            self._output_dir_edit.setText(path)
            self._emit()

    def _on_format_changed(self, fmt: str) -> None:
        self._settings.output_format = fmt
        self._emit()

    def _on_quality_changed(self, value: int) -> None:
        self._settings.output_quality = value
        self._emit()

    def _on_resize_toggled(self, checked: bool) -> None:
        self._settings.resize_enabled = checked
        self._emit()

    def _on_resize_changed(self) -> None:
        self._settings.resize_width = self._resize_w_spin.value()
        self._settings.resize_height = self._resize_h_spin.value()
        self._emit()


# ---------------------------------------------------------------------------
# Helper widget
# ---------------------------------------------------------------------------

class _LabeledSlider(QWidget):
    """Horizontal slider with a numeric label showing the current value."""

    valueChanged = pyqtSignal(int)

    def __init__(self, minimum: int, maximum: int, value: int, parent=None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(minimum, maximum)
        self._slider.setValue(value)

        self._label = QLabel(str(value))
        self._label.setFixedWidth(36)
        self._label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        layout.addWidget(self._slider)
        layout.addWidget(self._label)

        self._slider.valueChanged.connect(self._on_value_changed)

    def value(self) -> int:
        return self._slider.value()

    def _on_value_changed(self, value: int) -> None:
        self._label.setText(str(value))
        self.valueChanged.emit(value)
