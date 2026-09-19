"""SettingsPanel — 보정 / 리사이즈 / 출력 / 그룹 4탭."""
from __future__ import annotations

import copy
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from myphotoworks.models.settings import (
    AppSettings, CorrectionMode, OutputPathMode, ResizeAxis,
)
from myphotoworks.recipes.builtin_recipes import (
    BUILTIN_RECIPES, build_correction_combo_items, populate_correction_combo,
)

RESIZE_PRESETS = [1080, 1920, 2048, 2560, 3840]

# Maps combo index → (CorrectionMode, recipe_key) for SettingsPanel / _EffectsBar
_COMBO_ITEMS = build_correction_combo_items()


class SettingsPanel(QTabWidget):
    """Tab widget owning AppSettings.

    Signal
    ------
    settings_changed(AppSettings)  — emitted on any change.
    """

    settings_changed = pyqtSignal(object)
    weights_changed = pyqtSignal()
    display_changed = pyqtSignal()
    group_run_requested = pyqtSignal()
    group_cancel_requested = pyqtSignal()
    group_review_requested = pyqtSignal()
    group_rescore_requested = pyqtSignal()

    def __init__(self, settings: AppSettings, parent=None) -> None:
        super().__init__(parent)
        self._settings = settings
        self.addTab(self._build_effects_tab(), "보정")
        self.addTab(self._build_resize_tab(), "리사이즈")
        self.addTab(self._build_output_tab(), "출력")
        self._build_group_tab()

    def settings(self) -> AppSettings:
        return self._settings

    def load_settings(self, settings: AppSettings) -> None:
        """Replace current settings and refresh all widgets."""
        self._settings = copy.copy(settings)
        self._refresh_effects()
        self._refresh_resize()
        self._refresh_output()
        self.group_tab.set_settings(self._settings)

    # ------------------------------------------------------------------
    # 그룹 탭
    # ------------------------------------------------------------------

    def _build_group_tab(self) -> None:
        from myphotoworks.ui.group_tab import GroupTab

        self.group_tab = GroupTab(self._settings)
        self.group_tab.changed.connect(self._emit)
        self.group_tab.weights_changed.connect(self.weights_changed)
        self.group_tab.display_changed.connect(self.display_changed)
        self.group_tab.run_requested.connect(self.group_run_requested)
        self.group_tab.cancel_requested.connect(self.group_cancel_requested)
        self.group_tab.review_requested.connect(self.group_review_requested)
        self.group_tab.rescore_requested.connect(self.group_rescore_requested)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        scroll.viewport().setStyleSheet("background: transparent;")
        self.group_tab.setStyleSheet("GroupTab { background: transparent; }")
        scroll.setWidget(self.group_tab)
        self.addTab(scroll, "그룹")

    # ------------------------------------------------------------------
    # 보정 탭
    # ------------------------------------------------------------------

    def _build_effects_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Correction mode dropdown
        mode_group = QGroupBox("보정 방식")
        mode_layout = QVBoxLayout(mode_group)
        self._mode_combo = QComboBox()
        populate_correction_combo(self._mode_combo)
        self._mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        mode_layout.addWidget(self._mode_combo)
        layout.addWidget(mode_group)

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

        # Recipe info (shown only when RECIPE mode is selected)
        self._recipe_info_group = QGroupBox("레시피 정보")
        self._recipe_info_layout = QFormLayout(self._recipe_info_group)
        self._recipe_info_labels: dict[str, QLabel] = {}
        for field_name in ("필름 시뮬레이션", "화이트밸런스", "톤 커브", "채도", "선명도", "그레인"):
            lbl = QLabel("—")
            lbl.setWordWrap(True)
            self._recipe_info_layout.addRow(field_name, lbl)
            self._recipe_info_labels[field_name] = lbl
        layout.addWidget(self._recipe_info_group)

        self._sync_mode_combo()
        self._update_recipe_info()
        return tab

    def _refresh_effects(self) -> None:
        self._sync_mode_combo()
        self._brightness_slider.setValue(self._settings.brightness)
        self._contrast_slider.setValue(self._settings.contrast)
        self._update_recipe_info()

    def _sync_mode_combo(self) -> None:
        """Set combo selection to match current settings without firing signals."""
        target_mode = self._settings.correction_mode
        target_key = self._settings.recipe_name

        self._mode_combo.blockSignals(True)
        for i, item in enumerate(_COMBO_ITEMS):
            if item.is_separator:
                continue
            if item.mode == target_mode and item.recipe_key == target_key:
                # Find actual combo index (separators occupy an index too)
                self._mode_combo.setCurrentIndex(i)
                break
        self._mode_combo.blockSignals(False)

    def _update_recipe_info(self) -> None:
        """Show or hide the recipe info group based on current mode."""
        is_recipe = self._settings.correction_mode == CorrectionMode.RECIPE
        self._recipe_info_group.setVisible(is_recipe)
        if not is_recipe:
            return

        rd = BUILTIN_RECIPES.get(self._settings.recipe_name)
        if rd is None:
            return

        self._recipe_info_labels["필름 시뮬레이션"].setText(rd.film_sim.value)
        self._recipe_info_labels["화이트밸런스"].setText(
            f"{rd.wb_kelvin}K  R:{rd.wb_shift_r:+d}  B:{rd.wb_shift_b:+d}"
        )
        self._recipe_info_labels["톤 커브"].setText(
            f"S:{rd.tone_shadow:+d}  H:{rd.tone_highlight:+d}"
        )
        self._recipe_info_labels["채도"].setText(f"{rd.color:+d}")
        self._recipe_info_labels["선명도"].setText(f"{rd.sharpness:+d}")
        self._recipe_info_labels["그레인"].setText(rd.grain_effect)

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

        from PyQt6.QtWidgets import QCheckBox
        self._resize_cb = QCheckBox("리사이즈 적용")
        self._resize_cb.setChecked(self._settings.resize_enabled)
        self._resize_cb.toggled.connect(self._on_resize_toggled)
        form.addRow(self._resize_cb)

        self._axis_combo = QComboBox()
        self._axis_combo.addItem("긴 축", ResizeAxis.LONG)
        self._axis_combo.addItem("짧은 축", ResizeAxis.SHORT)
        idx = 0 if self._settings.resize_axis == ResizeAxis.LONG else 1
        self._axis_combo.setCurrentIndex(idx)
        self._axis_combo.currentIndexChanged.connect(self._on_axis_changed)
        form.addRow("기준 축", self._axis_combo)

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

    def _on_mode_changed(self, index: int) -> None:
        if index < 0 or index >= len(_COMBO_ITEMS):
            return
        item = _COMBO_ITEMS[index]
        if item.is_separator:
            # Prevent selecting a separator — revert to previous valid selection
            self._sync_mode_combo()
            return
        self._settings.correction_mode = item.mode
        self._settings.recipe_name = item.recipe_key
        self._update_recipe_info()
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
