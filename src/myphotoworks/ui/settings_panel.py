"""SettingsPanel — 보정 / 리사이즈 / 출력 3탭."""
from __future__ import annotations

import copy
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
    QRadioButton,
    QSlider,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from myphotoworks.models.settings import AppSettings, OutputPathMode, ResizeAxis

RESIZE_PRESETS = [1080, 1920, 2048, 2560, 3840]


class SettingsPanel(QTabWidget):
    """Tab widget owning AppSettings.

    Signal
    ------
    settings_changed(AppSettings)  — emitted on any change.
    """

    settings_changed = pyqtSignal(object)

    def __init__(self, settings: AppSettings, parent=None) -> None:
        super().__init__(parent)
        self._settings = settings
        self.addTab(self._build_effects_tab(), "보정")
        self.addTab(self._build_resize_tab(), "리사이즈")
        self.addTab(self._build_output_tab(), "출력")

    def settings(self) -> AppSettings:
        return self._settings

    def load_settings(self, settings: AppSettings) -> None:
        """Replace current settings and refresh all widgets."""
        self._settings = copy.copy(settings)
        self._refresh_effects()
        self._refresh_resize()
        self._refresh_output()

    # ------------------------------------------------------------------
    # 보정 탭
    # ------------------------------------------------------------------

    def _build_effects_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Auto corrections
        auto_group = QGroupBox("자동 보정")
        auto_layout = QVBoxLayout(auto_group)

        self._auto_level_cb = QCheckBox("Auto Level")
        self._auto_level_cb.setChecked(self._settings.auto_level)
        self._auto_level_cb.toggled.connect(self._on_auto_level)
        auto_layout.addWidget(self._auto_level_cb)

        self._auto_contrast_cb = QCheckBox("Auto Contrast")
        self._auto_contrast_cb.setChecked(self._settings.auto_contrast)
        self._auto_contrast_cb.toggled.connect(self._on_auto_contrast)
        auto_layout.addWidget(self._auto_contrast_cb)

        layout.addWidget(auto_group)

        # Brightness / Contrast
        bc_group = QGroupBox("밝기 / 대비")
        bc_layout = QFormLayout(bc_group)

        self._brightness_slider = _LabeledSlider(-100, 100, self._settings.brightness)
        self._brightness_slider.valueChanged.connect(self._on_brightness)
        bc_layout.addRow("밝기", self._brightness_slider)

        self._contrast_slider = _LabeledSlider(-100, 100, self._settings.contrast)
        self._contrast_slider.valueChanged.connect(self._on_contrast)
        bc_layout.addRow("대비", self._contrast_slider)

        layout.addWidget(bc_group)
        return tab

    def _refresh_effects(self) -> None:
        self._auto_level_cb.setChecked(self._settings.auto_level)
        self._auto_contrast_cb.setChecked(self._settings.auto_contrast)
        self._brightness_slider.setValue(self._settings.brightness)
        self._contrast_slider.setValue(self._settings.contrast)

    # ------------------------------------------------------------------
    # 리사이즈 탭
    # ------------------------------------------------------------------

    def _build_resize_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        resize_group = QGroupBox("리사이즈 설정")
        form = QFormLayout(resize_group)

        # 리사이즈 활성화 체크박스
        self._resize_cb = QCheckBox("리사이즈 적용")
        self._resize_cb.setChecked(self._settings.resize_enabled)
        self._resize_cb.toggled.connect(self._on_resize_toggled)
        form.addRow(self._resize_cb)

        # 기준 축
        self._axis_combo = QComboBox()
        self._axis_combo.addItem("긴 축", ResizeAxis.LONG)
        self._axis_combo.addItem("짧은 축", ResizeAxis.SHORT)
        idx = 0 if self._settings.resize_axis == ResizeAxis.LONG else 1
        self._axis_combo.setCurrentIndex(idx)
        self._axis_combo.currentIndexChanged.connect(self._on_axis_changed)
        form.addRow("기준 축", self._axis_combo)

        # 픽셀값 — 직접 입력 + 프리셋
        px_row = QHBoxLayout()
        self._px_spin = QSpinBox()
        self._px_spin.setRange(1, 99999)
        self._px_spin.setValue(self._settings.resize_px)
        self._px_spin.setSuffix(" px")
        self._px_spin.valueChanged.connect(self._on_px_changed)
        px_row.addWidget(self._px_spin)

        self._preset_combo = QComboBox()
        self._preset_combo.addItem("프리셋")
        for p in RESIZE_PRESETS:
            self._preset_combo.addItem(str(p))
        self._preset_combo.currentIndexChanged.connect(self._on_preset_selected)
        px_row.addWidget(self._preset_combo)

        form.addRow("픽셀값", px_row)
        layout.addWidget(resize_group)

        self._update_resize_controls()
        return tab

    def _refresh_resize(self) -> None:
        self._resize_cb.setChecked(self._settings.resize_enabled)
        idx = 0 if self._settings.resize_axis == ResizeAxis.LONG else 1
        self._axis_combo.setCurrentIndex(idx)
        self._px_spin.setValue(self._settings.resize_px)
        self._update_resize_controls()

    def _update_resize_controls(self) -> None:
        enabled = self._settings.resize_enabled
        self._axis_combo.setEnabled(enabled)
        self._px_spin.setEnabled(enabled)
        self._preset_combo.setEnabled(enabled)

    # ------------------------------------------------------------------
    # 출력 탭
    # ------------------------------------------------------------------

    def _build_output_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # 저장 경로
        path_group = QGroupBox("저장 경로")
        path_layout = QVBoxLayout(path_group)

        self._radio_first = QRadioButton("첫 번째 파일 기준 output 폴더")
        self._radio_per = QRadioButton("각 파일별 output 폴더")
        self._radio_custom = QRadioButton("직접 지정")

        mode = self._settings.output_path_mode
        self._radio_first.setChecked(mode == OutputPathMode.FIRST_FILE)
        self._radio_per.setChecked(mode == OutputPathMode.PER_FILE)
        self._radio_custom.setChecked(mode == OutputPathMode.CUSTOM)

        self._radio_first.toggled.connect(self._on_path_mode_changed)
        self._radio_per.toggled.connect(self._on_path_mode_changed)
        self._radio_custom.toggled.connect(self._on_path_mode_changed)

        path_layout.addWidget(self._radio_first)
        path_layout.addWidget(self._radio_per)
        path_layout.addWidget(self._radio_custom)

        custom_row = QHBoxLayout()
        self._custom_dir_edit = QLineEdit(str(self._settings.output_custom_dir))
        self._custom_dir_edit.setReadOnly(True)
        custom_row.addWidget(self._custom_dir_edit)
        browse_btn = QPushButton("...")
        browse_btn.setFixedWidth(30)
        browse_btn.clicked.connect(self._on_browse_custom_dir)
        custom_row.addWidget(browse_btn)
        path_layout.addLayout(custom_row)

        layout.addWidget(path_group)
        self._update_custom_dir_controls()

        # 파일명
        name_group = QGroupBox("파일명")
        name_form = QFormLayout(name_group)

        self._prefix_edit = QLineEdit(self._settings.output_prefix)
        self._prefix_edit.setPlaceholderText("없음")
        self._prefix_edit.textChanged.connect(self._on_prefix_changed)
        name_form.addRow("Prefix", self._prefix_edit)

        self._suffix_edit = QLineEdit(self._settings.output_suffix)
        self._suffix_edit.setPlaceholderText("없음")
        self._suffix_edit.textChanged.connect(self._on_suffix_changed)
        name_form.addRow("Suffix", self._suffix_edit)

        layout.addWidget(name_group)

        # 품질
        quality_group = QGroupBox("JPG 품질")
        quality_layout = QHBoxLayout(quality_group)

        self._quality_slider = QSlider(Qt.Orientation.Horizontal)
        self._quality_slider.setRange(1, 100)
        self._quality_slider.setValue(self._settings.output_quality)
        self._quality_slider.valueChanged.connect(self._on_quality_slider)

        self._quality_spin = QSpinBox()
        self._quality_spin.setRange(1, 100)
        self._quality_spin.setValue(self._settings.output_quality)
        self._quality_spin.setSuffix(" %")
        self._quality_spin.setFixedWidth(65)
        self._quality_spin.valueChanged.connect(self._on_quality_spin)

        quality_layout.addWidget(self._quality_slider)
        quality_layout.addWidget(self._quality_spin)

        layout.addWidget(quality_group)
        return tab

    def _refresh_output(self) -> None:
        mode = self._settings.output_path_mode
        self._radio_first.setChecked(mode == OutputPathMode.FIRST_FILE)
        self._radio_per.setChecked(mode == OutputPathMode.PER_FILE)
        self._radio_custom.setChecked(mode == OutputPathMode.CUSTOM)
        self._custom_dir_edit.setText(str(self._settings.output_custom_dir))
        self._prefix_edit.setText(self._settings.output_prefix)
        self._suffix_edit.setText(self._settings.output_suffix)
        self._quality_slider.setValue(self._settings.output_quality)
        self._quality_spin.setValue(self._settings.output_quality)
        self._update_custom_dir_controls()

    def _update_custom_dir_controls(self) -> None:
        enabled = self._settings.output_path_mode == OutputPathMode.CUSTOM
        self._custom_dir_edit.setEnabled(enabled)

    # ------------------------------------------------------------------
    # Slots — effects
    # ------------------------------------------------------------------

    def _on_auto_level(self, checked: bool) -> None:
        self._settings.auto_level = checked
        self._emit()

    def _on_auto_contrast(self, checked: bool) -> None:
        self._settings.auto_contrast = checked
        self._emit()

    def _on_brightness(self, value: int) -> None:
        self._settings.brightness = value
        self._emit()

    def _on_contrast(self, value: int) -> None:
        self._settings.contrast = value
        self._emit()

    # ------------------------------------------------------------------
    # Slots — resize
    # ------------------------------------------------------------------

    def _on_resize_toggled(self, checked: bool) -> None:
        self._settings.resize_enabled = checked
        self._update_resize_controls()
        self._emit()

    def _on_axis_changed(self, index: int) -> None:
        self._settings.resize_axis = self._axis_combo.currentData()
        self._emit()

    def _on_px_changed(self, value: int) -> None:
        self._settings.resize_px = value
        self._emit()

    def _on_preset_selected(self, index: int) -> None:
        if index == 0:
            return
        px = RESIZE_PRESETS[index - 1]
        self._px_spin.setValue(px)
        self._preset_combo.setCurrentIndex(0)

    # ------------------------------------------------------------------
    # Slots — output
    # ------------------------------------------------------------------

    def _on_path_mode_changed(self) -> None:
        if self._radio_first.isChecked():
            self._settings.output_path_mode = OutputPathMode.FIRST_FILE
        elif self._radio_per.isChecked():
            self._settings.output_path_mode = OutputPathMode.PER_FILE
        else:
            self._settings.output_path_mode = OutputPathMode.CUSTOM
        self._update_custom_dir_controls()
        self._emit()

    def _on_browse_custom_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, "출력 폴더 선택", str(self._settings.output_custom_dir)
        )
        if path:
            self._settings.output_custom_dir = Path(path)
            self._custom_dir_edit.setText(path)
            self._emit()

    def _on_prefix_changed(self, text: str) -> None:
        self._settings.output_prefix = text
        self._emit()

    def _on_suffix_changed(self, text: str) -> None:
        self._settings.output_suffix = text
        self._emit()

    def _on_quality_slider(self, value: int) -> None:
        self._quality_spin.blockSignals(True)
        self._quality_spin.setValue(value)
        self._quality_spin.blockSignals(False)
        self._settings.output_quality = value
        self._emit()

    def _on_quality_spin(self, value: int) -> None:
        self._quality_slider.blockSignals(True)
        self._quality_slider.setValue(value)
        self._quality_slider.blockSignals(False)
        self._settings.output_quality = value
        self._emit()

    def _emit(self) -> None:
        self.settings_changed.emit(self._settings)


# ---------------------------------------------------------------------------
# Helper widget
# ---------------------------------------------------------------------------

class _LabeledSlider(QWidget):
    """Horizontal slider with a numeric spin box showing the current value."""

    valueChanged = pyqtSignal(int)

    def __init__(self, minimum: int, maximum: int, value: int, parent=None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(minimum, maximum)
        self._slider.setValue(value)

        self._spin = QSpinBox()
        self._spin.setRange(minimum, maximum)
        self._spin.setValue(value)
        self._spin.setFixedWidth(52)

        layout.addWidget(self._slider)
        layout.addWidget(self._spin)

        self._slider.valueChanged.connect(self._on_slider)
        self._spin.valueChanged.connect(self._on_spin)

    def value(self) -> int:
        return self._slider.value()

    def setValue(self, value: int) -> None:
        self._slider.blockSignals(True)
        self._spin.blockSignals(True)
        self._slider.setValue(value)
        self._spin.setValue(value)
        self._slider.blockSignals(False)
        self._spin.blockSignals(False)

    def _on_slider(self, value: int) -> None:
        self._spin.blockSignals(True)
        self._spin.setValue(value)
        self._spin.blockSignals(False)
        self.valueChanged.emit(value)

    def _on_spin(self, value: int) -> None:
        self._slider.blockSignals(True)
        self._slider.setValue(value)
        self._slider.blockSignals(False)
        self.valueChanged.emit(value)
