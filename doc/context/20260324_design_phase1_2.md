# 세션 요약: 설계 및 Phase 1~2 구현

**날짜**: 2026-03-24
**브랜치**: `first_stage`

---

## 세션 목표

Python Windows 데스크톱 앱 **myPhotoWorks** 의 초기 설계를 수립하고 Phase 1~2를 구현한다.

---

## 1. 참고 UI 분석

| 파일 | 내용 |
|---|---|
| `doc/reference/photoworks_main.png` | 메인 창: 좌측 썸네일 목록 + 우측 탭 패널 (Home / Name / Signature / PPI / Output / Configuration / Help) |
| `doc/reference/photoworks_preview.png` | 프리뷰 창: 대형 이미지 + 우측 EXIF 패널 + 하단 탭 (FrameEffect / Color Model / Text / Option) + 이전/다음 버튼 + 날짜 워터마크 |

---

## 2. 기술 스택 결정

| 역할 | 선택 | 이유 |
|---|---|---|
| GUI | **PyQt6** | 네이티브 Windows 스타일, Signal/Slot, QThread 지원. GPL v3 — MIT 오픈소스와 호환 |
| 이미지 처리 | **Pillow + NumPy** | Auto Contrast 내장(`ImageOps`), Auto Level은 NumPy 5줄로 구현. OpenCV는 오버스펙이라 제외 |
| EXIF | **piexif** | 촬영일/ISO/Comment 추출 및 저장 시 보존 |
| 패키지 관리 | **uv** | `.gitignore`에 `uv.lock` 항목 이미 포함됨 |

---

## 3. 아키텍처 설계

### 프로젝트 구조
```
src/myphotoworks/
├── main.py               # QApplication 진입점
├── ui/                   # GUI (메인 창, 프리뷰 창, 썸네일 패널, 설정 패널, EXIF 패널)
├── processing/           # 이미지 처리 (effects, resize, processor)
├── models/               # PhotoItem, AppSettings dataclass
├── workers/              # QThread 배치 처리 워커
└── utils/                # exif_reader, config (JSON 설정 저장)
```

### 이펙트 체인 순서 (processor.py)
1. 흑백 변환
2. Level 클리핑 (min/max)
3. Auto Level (채널별 히스토그램 스트레치)
4. Auto Contrast (루미넌스 스트레치)
5. Brightness / Contrast
6. Sharpen 또는 Gaussian blur
7. 워터마크 오버레이
8. 리사이즈

### Signal/Slot 흐름
```
ThumbnailPanel.photo_selected       → MainWindow → ExifPanel.update()
ThumbnailPanel.photo_double_clicked → PreviewWindow 오픈
SettingsPanel.settings_changed      → PreviewWindow.refresh_preview (200ms debounce)
BatchWorker.photo_done              → ThumbnailPanel 상태 배지 업데이트
BatchWorker.progress                → MainWindow 진행바 업데이트
```

---

## 4. 핵심 알고리즘

### Auto Level (`effects.py`)
```python
def auto_level(image):
    arr = np.array(image, dtype=np.float32)
    for ch in range(3):
        mn, mx = arr[:,:,ch].min(), arr[:,:,ch].max()
        if mx > mn:
            arr[:,:,ch] = (arr[:,:,ch] - mn) / (mx - mn) * 255.0
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
```
- RGB 각 채널을 **독립적으로** 0~255 범위로 스트레치
- Auto Contrast(`ImageOps.autocontrast`)와 다른 점: Auto Contrast는 루미넌스 기준, Auto Level은 채널 독립

---

## 5. Phase 1~2 구현 결과

### Phase 1 — 프로젝트 스캐폴드
- [x] `pyproject.toml` 작성 (hatchling 빌드, src-layout)
- [x] `src/myphotoworks/` 패키지 디렉토리 뼈대
- [x] `main.py` — 빈 QMainWindow 실행 확인
- [x] `CLAUDE.md` 업데이트 (실행/테스트/린트 커맨드)
- [x] `README.md` 업데이트

### Phase 2 — 이미지 처리 코어
- [x] `models/photo_item.py` — `PhotoItem` dataclass + `ProcessStatus` Enum
- [x] `models/settings.py` — `AppSettings` dataclass (전체 설정값)
- [x] `processing/effects.py` — `auto_level`, `auto_contrast`, `apply_level`, `apply_bw`, `apply_brightness_contrast`, `apply_sharpen`, `apply_gaussian`, `apply_watermark`
- [x] `processing/resize.py` — 비율 유지 LANCZOS 리사이즈
- [x] `processing/processor.py` — 전체 파이프라인 + EXIF 보존 저장
- [x] `utils/exif_reader.py` — EXIF 추출 (촬영일, ISO, Comment, 파일크기)
- [x] `utils/config.py` — `~/.myphotoworks/config.json` 저장/로드

### 테스트 결과
```
uv run pytest → 26/26 passed (1.49s)
```
- `tests/test_effects.py` — 19개 테스트 (BW, Level, AutoLevel, AutoContrast, Brightness, Sharpen, Gaussian, Watermark)
- `tests/test_resize.py` — 7개 테스트 (비율 유지, 너비/높이 제약, 정확한 크기)

### 커밋
```
5e7beb4  Add Phase 1-2: project scaffold, image processing core, and updated docs
         23 files changed, 1137 insertions(+), 21 deletions(-)
```

---

## 6. 다음 단계

### Phase 3 — 메인 창 UI
- `ThumbnailPanel` (QListWidget, 드래그앤드롭)
- `SettingsPanel` QTabWidget — Home 탭 우선
- `MainWindow` 조립 + Choose 버튼 (QFileDialog)
- 썸네일 비동기 생성 (QThreadPool)

### Phase 4 — 프리뷰 창
- `ExifPanel` + `PreviewWindow`
- 실시간 프리뷰 (settings_changed → reprocess → QPixmap)

### Phase 5 — 배치 처리 & 출력
- `BatchWorker` (QThread) + 진행바
- Output 탭 UI + 저장

### Phase 6 — 나머지 탭 & 마무리
- Name / Signature / PPI / Configuration / Help 탭
- 에러 처리, 윈도우 레이아웃 저장/복원

---

## 7. 주요 커맨드

```bash
uv sync                          # 의존성 설치
uv run python -m myphotoworks   # 앱 실행
uv run pytest                    # 테스트
uv run ruff check .              # 린트
```
