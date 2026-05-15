# 세션 요약: 미리보기 창 개선 및 버그 수정

**날짜**: 2026-03-29
**브랜치**: `first_stage`

---

## 세션 목표

미리보기 창에서 발견된 여러 UI/기능 이슈를 순차적으로 수정한다.

---

## 수정 사항 목록

### 1. 3-pane 크기 불균등 문제 (`preview_window.py`)

**증상**: Before 창이 After-A/B 창보다 작게 표시됨

**원인 분석**:
1. `__init__`에서 `_load_current()` 호출 시 위젯 크기가 아직 0
2. 각 `_ImageView`가 독립적으로 fit-zoom을 계산 → 크기 불일치
3. splitter가 size hint 차이로 인해 불균등 초기 분배

**해결책**:
- `_first_show` 플래그 추가 → `showEvent`에서 첫 로드
- `_force_fit_all()` 중앙화: (a) `setSizes([third, third, third])`로 강제 균등, (b) 모든 pane의 layout activate, (c) 3개 pane 중 최소 fit-zoom 사용
- `resizeEvent`에서 `QTimer.singleShot(0, _force_fit_all)` 지연 호출

**핵심 코드**:
```python
def _force_fit_all(self) -> None:
    total = self._splitter.width()
    if total <= 0:
        return
    third = total // 3
    self._splitter.setSizes([third, third, third])
    for pane in (self._before_pane, self._after_a_pane, self._after_b_pane):
        if pane.layout():
            pane.layout().activate()
    panes = (self._before_pane, self._after_a_pane, self._after_b_pane)
    zoom: float | None = None
    for pane in panes:
        view = pane.image_view
        if view._pixmap and view.width() > 0 and view.height() > 0:
            z = min(view.width()/view._pixmap.width(), view.height()/view._pixmap.height())
            if zoom is None or z < zoom:
                zoom = z
    if zoom is None:
        return
    offset = QPointF(0.0, 0.0)
    for pane in panes:
        pane.image_view._zoom = zoom
        pane.image_view._offset = offset
        pane.image_view.update()
```

---

### 2. Auto Level / Auto Contrast 효과 미적용 문제 (`effects.py`)

**증상**: 야경 사진에서 Before/After가 거의 동일하게 보임

**원인 1 — Auto Level**:
절대 min/max 방식 사용 → 별 한 픽셀(255)과 검은 하늘(0)이 있으면 stretch ratio = 1.0 (무변화)

**해결**: 0.5% percentile clipping으로 outlier 제거
```python
def auto_level(image: Image.Image) -> Image.Image:
    arr = np.array(image, dtype=np.float32)
    for ch in range(3):
        lo = np.percentile(arr[:, :, ch], 0.5)
        hi = np.percentile(arr[:, :, ch], 99.5)
        if hi > lo:
            arr[:, :, ch] = (arr[:, :, ch] - lo) / (hi - lo) * 255.0
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
```

**원인 2 — Auto Contrast**:
`ImageOps.autocontrast`는 선형 히스토그램 stretch → `auto_level` 적용 후 이미 [0,255] 범위면 아무 효과 없음

**해결**: 적응형 감마 보정으로 교체 (비선형 → `auto_level`과 독립적으로 동작)
```python
def auto_contrast(image: Image.Image) -> Image.Image:
    import math
    arr = np.array(image, dtype=np.float32) / 255.0
    mean_lum = float(arr.mean())
    if mean_lum <= 0.0 or mean_lum >= 1.0:
        return image
    # gamma that maps mean_lum → 0.5
    gamma = math.log(0.5) / math.log(mean_lum)
    gamma = max(0.2, min(4.0, gamma))
    arr = np.power(np.clip(arr, 0.0, 1.0), gamma)
    return Image.fromarray(np.clip(arr * 255.0, 0, 255).astype(np.uint8))
```

- 어두운 이미지(mean < 0.5): gamma < 1 → 중간 톤 밝아짐
- 밝은 이미지(mean > 0.5): gamma > 1 → 중간 톤 어두워짐
- 검정(0)과 흰색(255) 포인트는 정확히 보존

---

### 3. After-A / After-B 동일 이미지 출력 문제 (`preview_window.py`)

**증상**: 서로 다른 설정을 해도 두 After 창이 같은 이미지를 표시

**원인**: `_EffectsBar` 초기화 시 같은 `AppSettings` 객체를 공유

**해결**: `copy.copy(self._base_settings)`로 각각 독립 복사본 사용

---

### 4. EXIF 정보 확장 (`exif_reader.py`, `exif_panel.py`)

**기존**: 5개 필드 (filename, size, date, camera, shutter, aperture, focal_length, iso, exposure_bias)

**추가된 필드**:
- 파일 시스템: `file_size`, `file_date`
- IFD0: `make`, `model` (separate), `software`, `orientation`
- ExifIFD: `flash`, `metering_mode`, `program_mode`, `comment`
- Lookup table: `_METERING`, `_PROGRAM`, `_ORIENTATION`

**총 19개 행**으로 확장:
번호, 파일이름, 파일크기, 파일날짜, 카메라 제조사, 카메라 모델명, 소프트웨어, 촬영날짜, 해상도, Orientation, 플래시 사용, 초점 거리, 셔터속도, 조리개 값, ISO 값, 노출보정, 측광 모드, 프로그램 모드, 코멘트

---

### 5. EXIF 패널 테이블 형식 변환 (`exif_panel.py`)

`QScrollArea` + Form 레이아웃 → `QTableWidget` (2열: 항목/정보)

- `alternatingRowColors(True)`
- `ResizeToContents` (항목 열) + `stretchLastSection` (정보 열)
- `update_photo(path, index, total)` — `index > 0`이면 "번호" 행 추가

---

### 6. 미리보기 이미지 영역 배경색 흰색으로 변경 (`preview_window.py`)

`_ImageView.__init__`에서 palette 설정:
```python
self.setAutoFillBackground(True)
palette = self.palette()
palette.setColor(palette.ColorRole.Window, Qt.GlobalColor.white)
self.setPalette(palette)
```

---

### 7. Before 창 ExifBar 헤더 제거 (`preview_window.py`)

`_ExifBar`의 `QTableWidget` 수평 헤더 숨김:
```python
self._table.horizontalHeader().setVisible(False)
```

---

## 수정 파일 목록

| 파일 | 변경 내용 |
|---|---|
| `src/myphotoworks/ui/preview_window.py` | 3-pane 균등 크기, 흰 배경, ExifBar 헤더 제거, After-A/B 독립 설정 |
| `src/myphotoworks/ui/exif_panel.py` | QTableWidget 기반 전면 재작성, 19개 필드 |
| `src/myphotoworks/utils/exif_reader.py` | 파일정보 + IFD0 + ExifIFD 확장, helper 함수 추가 |
| `src/myphotoworks/processing/effects.py` | auto_level percentile, auto_contrast 감마 보정 |
| `src/myphotoworks/ui/main_window.py` | `_open_preview()`: showEvent 기반 첫 로드로 변경 |
| `tests/test_effects.py` | TestAutoContrast 테스트 케이스 재설계 (감마 기반) |

---

### 8. Home 키 단축키 추가 (`preview_window.py`)

**기능**: `Home` 키를 누르면 현재 창 크기에 맞게 이미지 크기와 위치를 초기화

**구현**:
```python
elif key == Qt.Key.Key_Home:
    self._user_has_zoomed = False
    self._force_fit_all()
```
- `_user_has_zoomed = False` → 이후 resize 이벤트에서도 자동 재맞춤 복원
- 상태바 힌트에 `Home:화면맞춤` 추가

---

## 테스트

```
uv run pytest  →  72 tests, all passed
```
