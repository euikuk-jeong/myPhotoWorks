"""GroupTab — grouping options, run/status and recommendation settings (4th tab)."""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSlider,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from myphotoworks.core.grouping import GroupingMode
from myphotoworks.core.scoring import DEFAULT_WEIGHTS, normalize_weights
from myphotoworks.models.settings import AppSettings
from myphotoworks.ui.guide import open_guide

_MODES = [
    ("자동 (권장)", GroupingMode.AUTO),
    ("시각 우선", GroupingMode.TIME_FIRST),
    ("유사도만", GroupingMode.SIMILARITY_ONLY),
]
_MODE_HINT = {
    GroupingMode.AUTO: "촬영 시각이 믿을 만하면 참고하고, 아니면 사진 모양으로 묶습니다.",
    GroupingMode.TIME_FIRST: "촬영 시각 간격이 기준입니다. 시각이 없는 사진만 모양으로 묶습니다.",
    GroupingMode.SIMILARITY_ONLY: "촬영 시각은 무시하고 사진 모양이 비슷한 것끼리만 묶습니다.",
}

# (max slider value, short name, plain-language explanation)
_SIMILARITY_LEVELS = [
    (20, "아주 깐깐함", "거의 똑같은 컷만 묶어요. 그룹이 많아지고 사진이 낱개로 남기 쉬워요."),
    (40, "깐깐함", "구도가 거의 같은 연속 컷만 묶어요."),
    (60, "보통 (권장)", "같은 장면을 연달아 찍은 사진을 묶어요."),
    (80, "너그러움", "구도가 조금 달라도 같은 장면이면 묶어요."),
    (100, "아주 너그러움", "분위기만 비슷해도 묶어요. 그룹이 적어지고 다른 장면이 섞일 수 있어요."),
]


def similarity_level(value: int) -> tuple[str, str]:
    """(short name, plain-language explanation) for a slider value."""
    for upper, name, text in _SIMILARITY_LEVELS:
        if value <= upper:
            return name, text
    return _SIMILARITY_LEVELS[-1][1], _SIMILARITY_LEVELS[-1][2]


def _note(text: str) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    label.setObjectName("hint-label")
    return label


class GroupTab(QWidget):
    """Signals
    -------
    changed()            — a setting changed (persist it)
    weights_changed()    — recommendation weights changed (rescore, no decoding)
    display_changed()    — reason/score display options changed
    run_requested() / cancel_requested() / review_requested() / rescore_requested()
    """

    changed = pyqtSignal()
    weights_changed = pyqtSignal()
    display_changed = pyqtSignal()
    run_requested = pyqtSignal()
    cancel_requested = pyqtSignal()
    review_requested = pyqtSignal()
    rescore_requested = pyqtSignal()

    def __init__(self, settings: AppSettings, parent=None) -> None:
        super().__init__(parent)
        self._settings = settings
        self._running = False
        self._done = False
        self._has_photos = False
        self._build()
        self.refresh()

    # ------------------------------------------------------------------ build

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 4, 8, 8)
        root.setSpacing(6)
        self._guide_btn = QPushButton("알고리즘 설명서 보기 (그림으로 쉽게 이해하기)")
        self._guide_btn.setToolTip(
            "사진을 어떻게 묶고 추천하는지 그림과 예제로 설명한 문서를 브라우저에서 엽니다."
        )
        self._guide_btn.clicked.connect(lambda: open_guide(self))
        root.addWidget(self._guide_btn)
        root.addWidget(self._build_settings_box())
        root.addWidget(self._build_run_box())
        root.addWidget(self._build_recommend_box())
        root.addStretch()

    def _build_settings_box(self) -> QGroupBox:
        self._settings_box = QGroupBox("① 그룹핑 설정")
        box = QVBoxLayout(self._settings_box)
        box.setSpacing(8)

        box.addWidget(QLabel("그룹핑 방식"))
        self._mode_combo = QComboBox()
        for label, mode in _MODES:
            self._mode_combo.addItem(label, mode)
        self._mode_combo.currentIndexChanged.connect(self._on_mode)
        box.addWidget(self._mode_combo)
        self._mode_hint = _note("")
        box.addWidget(self._mode_hint)

        row = QHBoxLayout()
        row.addWidget(QLabel("사진이 얼마나 비슷해야 묶을까요?"))
        box.addLayout(row)
        self._sim_slider = QSlider(Qt.Orientation.Horizontal)
        self._sim_slider.setRange(0, 100)
        self._sim_slider.setSingleStep(5)
        self._sim_slider.setPageStep(10)
        self._sim_slider.valueChanged.connect(self._on_similarity)
        box.addWidget(self._sim_slider)
        ends = QHBoxLayout()
        ends.addWidget(_note("◀ 깐깐하게"))
        ends.addStretch()
        ends.addWidget(_note("너그럽게 ▶"))
        box.addLayout(ends)
        self._sim_value = QLabel()
        self._sim_value.setWordWrap(True)
        box.addWidget(self._sim_value)
        self._sim_text = _note("")
        box.addWidget(self._sim_text)
        box.addWidget(_note(
            "결과가 너무 잘게 나뉘면 오른쪽으로, 다른 장면이 섞이면 왼쪽으로 옮겨 보세요."
        ))

        row = QHBoxLayout()
        row.addWidget(QLabel("같은 순간으로 볼 시간 간격"))
        row.addStretch()
        self._gap_spin = QDoubleSpinBox()
        self._gap_spin.setRange(0.5, 10.0)
        self._gap_spin.setSingleStep(0.5)
        self._gap_spin.setDecimals(1)
        self._gap_spin.setSuffix(" 초")
        self._gap_spin.valueChanged.connect(self._on_gap)
        row.addWidget(self._gap_spin)
        box.addLayout(row)
        self._gap_hint = _note("이 시간 안에 찍힌 사진은 같은 순간으로 판단합니다. (그룹핑 방식이 "
                               "'유사도만'이면 사용하지 않아요)")
        box.addWidget(self._gap_hint)

        self._global_cb = QCheckBox("떨어져 있는 같은 장면도 묶기")
        self._global_cb.setToolTip(
            "순서와 상관없이 전체 사진을 서로 비교합니다.\n"
            "스캔 순서가 뒤섞인 필름 등에 유용하지만, 비슷한 다른 장면이 묶일 수 있습니다."
        )
        self._global_cb.toggled.connect(self._on_global)
        box.addWidget(self._global_cb)

        self._exif_cb = QCheckBox("EXIF(초점거리·렌즈·조리개) 참고")
        self._exif_cb.setToolTip(
            "촬영 정보가 서로 크게 다르면 다른 장면으로 판단하는 데 참고합니다.\n"
            "사진 대부분에 정보가 있을 때만 적용되고, 없으면 자동으로 무시합니다."
        )
        self._exif_cb.toggled.connect(self._on_exif)
        box.addWidget(self._exif_cb)
        return self._settings_box

    def _build_run_box(self) -> QGroupBox:
        self._run_box = QGroupBox("② 그룹핑 실행 · 결과")
        box = QVBoxLayout(self._run_box)
        box.setSpacing(8)

        self._run_btn = QPushButton("그룹핑 실행")
        self._run_btn.setFixedHeight(32)
        self._run_btn.clicked.connect(self.run_requested)
        box.addWidget(self._run_btn)

        self._progress_frame = QFrame()
        pf = QVBoxLayout(self._progress_frame)
        pf.setContentsMargins(0, 0, 0, 0)
        self._stage_label = QLabel()
        self._progress = QProgressBar()
        self._cancel_btn = QPushButton("취소")
        self._cancel_btn.clicked.connect(self.cancel_requested)
        pf.addWidget(self._stage_label)
        pf.addWidget(self._progress)
        pf.addWidget(self._cancel_btn)
        self._progress_frame.setVisible(False)
        box.addWidget(self._progress_frame)

        self._result_label = QLabel("결과 요약이 여기에 표시됩니다.")
        self._result_label.setWordWrap(True)
        box.addWidget(self._result_label)
        self._judge_label = _note("")
        self._judge_label.setVisible(False)
        box.addWidget(self._judge_label)

        self._stale_frame = QFrame()
        sf = QVBoxLayout(self._stale_frame)
        sf.setContentsMargins(0, 0, 0, 0)
        stale_lbl = QLabel("보정 설정이 바뀌어 노출·색감 점수가 최신이 아닙니다.")
        stale_lbl.setWordWrap(True)
        self._stale_btn = QPushButton("점수 다시 계산")
        self._stale_btn.clicked.connect(self.rescore_requested)
        sf.addWidget(stale_lbl)
        sf.addWidget(self._stale_btn)
        self._stale_frame.setVisible(False)
        box.addWidget(self._stale_frame)

        self._review_btn = QPushButton("그룹 리뷰 열기")
        self._review_btn.setFixedHeight(30)
        self._review_btn.clicked.connect(self.review_requested)
        box.addWidget(self._review_btn)
        self._review_hint = _note("그룹핑 후 사용할 수 있습니다.")
        box.addWidget(self._review_hint)
        return self._run_box

    def _build_recommend_box(self) -> QGroupBox:
        self._recommend_box = QGroupBox("③ 추천 설정")
        box = QVBoxLayout(self._recommend_box)
        box.setSpacing(8)

        box.addWidget(QLabel("사진에 표시할 정보"))
        self._reason_cb = QCheckBox("추천 이유 표시")
        self._score_cb = QCheckBox("품질 점수 표시")
        self._reason_cb.toggled.connect(self._on_display)
        self._score_cb.toggled.connect(self._on_display)
        box.addWidget(self._reason_cb)
        box.addWidget(self._score_cb)

        self._adv_btn = QToolButton()
        self._adv_btn.setText("추천 기준 가중치 (고급)")
        self._adv_btn.setCheckable(True)
        self._adv_btn.setArrowType(Qt.ArrowType.RightArrow)
        self._adv_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._adv_btn.toggled.connect(self._on_adv_toggled)
        box.addWidget(self._adv_btn)

        self._adv_box = QWidget()
        adv = QVBoxLayout(self._adv_box)
        adv.setContentsMargins(0, 0, 0, 0)
        adv.addWidget(_note("추천 사진을 고를 때 무엇을 더 중요하게 볼지 정합니다."))
        self._w_sliders: list[QSlider] = []
        self._w_labels: list[QLabel] = []
        for name in ("선명도", "노출", "색감"):
            r = QHBoxLayout()
            r.addWidget(QLabel(name))
            s = QSlider(Qt.Orientation.Horizontal)
            s.setRange(0, 100)
            s.valueChanged.connect(self._on_weight)
            lbl = QLabel()
            lbl.setFixedWidth(44)
            r.addWidget(s, 1)
            r.addWidget(lbl)
            adv.addLayout(r)
            self._w_sliders.append(s)
            self._w_labels.append(lbl)
        adv.addWidget(_note("합계 100%로 자동 조정 · 직접 수정한 그룹의 채택은 유지됩니다"))
        self._reset_btn = QPushButton("기본값 복원")
        self._reset_btn.clicked.connect(self._on_reset_weights)
        adv.addWidget(self._reset_btn, 0, Qt.AlignmentFlag.AlignLeft)
        self._adv_box.setVisible(False)
        box.addWidget(self._adv_box)
        return self._recommend_box

    # ------------------------------------------------------------- settings io

    def set_settings(self, settings: AppSettings) -> None:
        self._settings = settings
        self.refresh()

    def refresh(self) -> None:
        s = self._settings
        self._block(True)
        idx = self._mode_combo.findData(s.grouping_mode)
        self._mode_combo.setCurrentIndex(max(0, idx))
        self._sim_slider.setValue(s.similarity_slider)
        self._gap_spin.setValue(s.time_gap)
        for slider, w in zip(self._w_sliders, s.weights(), strict=True):
            slider.setValue(round(w * 100))
        self._global_cb.setChecked(s.global_clustering)
        self._exif_cb.setChecked(s.use_exif_hints)
        self._reason_cb.setChecked(s.show_reason)
        self._score_cb.setChecked(s.show_score)
        self._block(False)
        self._update_labels()
        self._apply_enabled()

    def _block(self, on: bool) -> None:
        for w in (self._mode_combo, self._sim_slider, self._gap_spin, self._reason_cb,
                  self._score_cb, self._global_cb, self._exif_cb, *self._w_sliders):
            w.blockSignals(on)

    def _update_labels(self) -> None:
        s = self._settings
        name, text = similarity_level(s.similarity_slider)
        self._sim_value.setText(f"현재: {name}")
        self._sim_text.setText(text)
        self._mode_hint.setText(_MODE_HINT[s.grouping_mode])
        norm = normalize_weights(s.weights())
        for lbl, w in zip(self._w_labels, norm, strict=True):
            lbl.setText(f"{round(w * 100)}%")

    # ---------------------------------------------------------------- handlers

    def _on_mode(self, _index: int) -> None:
        self._settings.grouping_mode = self._mode_combo.currentData()
        self._update_labels()
        self._apply_enabled()
        self.changed.emit()

    def _on_similarity(self, value: int) -> None:
        self._settings.similarity_slider = value
        self._update_labels()
        self.changed.emit()

    def _on_global(self, checked: bool) -> None:
        self._settings.global_clustering = checked
        self.changed.emit()

    def _on_exif(self, checked: bool) -> None:
        self._settings.use_exif_hints = checked
        self.changed.emit()

    def set_stale(self, stale: bool) -> None:
        self._stale_frame.setVisible(stale)

    def _on_gap(self, value: float) -> None:
        self._settings.time_gap = float(value)
        self.changed.emit()

    def _on_weight(self, _value: int) -> None:
        a, b, c = (s.value() / 100.0 for s in self._w_sliders)
        self._settings.weight_sharpness = a
        self._settings.weight_exposure = b
        self._settings.weight_color = c
        self._update_labels()
        self.changed.emit()
        self.weights_changed.emit()

    def _on_reset_weights(self) -> None:
        for s, w in zip(self._w_sliders, DEFAULT_WEIGHTS, strict=True):
            s.blockSignals(True)
            s.setValue(round(w * 100))
            s.blockSignals(False)
        self._on_weight(0)

    def _on_display(self, _checked: bool) -> None:
        self._settings.show_reason = self._reason_cb.isChecked()
        self._settings.show_score = self._score_cb.isChecked()
        self.changed.emit()
        self.display_changed.emit()

    def _on_adv_toggled(self, checked: bool) -> None:
        self._adv_btn.setArrowType(
            Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow
        )
        self._adv_box.setVisible(checked)

    # ------------------------------------------------------------------ state

    def set_has_photos(self, has: bool) -> None:
        self._has_photos = has
        self._apply_enabled()

    def set_running(self, running: bool) -> None:
        self._running = running
        self._progress_frame.setVisible(running)
        if running:
            self._progress.setRange(0, 0)
            self._stage_label.setText("준비 중…")
        self._apply_enabled()

    def set_progress(self, stage: str, current: int, total: int) -> None:
        self._progress.setRange(0, max(1, total))
        self._progress.setValue(current)
        self._stage_label.setText(f"{stage}… {current} / {total}")

    def set_done(self, done: bool) -> None:
        self._done = done
        self._run_btn.setText("다시 그룹핑" if done else "그룹핑 실행")
        self._apply_enabled()

    def show_result(self, summary: str, judge_message: str, warning: str = "") -> None:
        self._result_label.setText(f"{summary}\n{warning}" if warning else summary)
        self._judge_label.setText(judge_message)
        self._judge_label.setVisible(bool(judge_message))

    def clear_result(self) -> None:
        self._result_label.setText("결과 요약이 여기에 표시됩니다.")
        self._judge_label.setVisible(False)

    def _apply_enabled(self) -> None:
        idle = not self._running
        self._settings_box.setEnabled(idle)
        self._gap_spin.setEnabled(
            idle and self._settings.grouping_mode != GroupingMode.SIMILARITY_ONLY
        )
        self._gap_hint.setEnabled(self._gap_spin.isEnabled())
        self._run_btn.setEnabled(idle and self._has_photos)
        self._review_btn.setEnabled(idle and self._done)
        self._stale_btn.setEnabled(idle)
        self._review_hint.setVisible(not (idle and self._done))
        self._review_hint.setText(
            "그룹핑 진행 중에는 사용할 수 없습니다." if self._running
            else "그룹핑 후 사용할 수 있습니다."
        )
