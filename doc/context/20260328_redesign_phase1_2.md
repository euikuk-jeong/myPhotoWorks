# 세션 요약: 요구사항 재정립 및 UI 전면 재설계

**날짜**: 2026-03-28
**브랜치**: `first_stage`

---

## 세션 목표

기존 Phase 1~3 코드가 요구사항 없이 작성된 상태였으므로, 사용자 인터뷰를 통해 요구사항을 정리하고 전체 코드를 요구사항 기반으로 재설계·재작성한다.

---

## 1. 요구사항 수집 (사용자 인터뷰)

### 사용 목적
- 개인용 사진 일괄 리사이즈/보정 도구
- 기존 도구(photoWorks) 대비 기능 축소 + 미리보기 강화

### 참고 UI
| 파일 | 내용 |
|---|---|
| `doc/reference/photoworks_main.png` | 메인 창 레이아웃 참고 |
| `doc/reference/photoworks_preview.png` | 미리보기 창 레이아웃 참고 |

### 핵심 기능

#### 보정
| 기능 | 비고 |
|---|---|
| Auto Level | 체크박스 on/off |
| Auto Contrast | 체크박스 on/off |
| 밝기 / 대비 | +-수치 입력 (-100~+100) |

#### 리사이즈
| 항목 | 내용 |
|---|---|
| 활성화 여부 | 체크박스 |
| 기준 축 | 긴 축 / 짧은 축 드롭다운 |
| 픽셀값 | 직접 입력 + 프리셋 드롭다운 (1080/1920/2048/2560/3840) |

#### 출력
| 항목 | 내용 |
|---|---|
| 저장 경로 | ① 첫 번째 파일 기준 output 폴더 ② 각 파일별 output 폴더 ③ 직접 지정 |
| 파일명 | 원본명 + prefix/suffix 옵션 |
| 포맷 | JPG 고정, 품질 슬라이더+스핀박스 (1~100%) |
| EXIF | 항상 보존 |

### 워크플로우
```
파일 선택 → 보정/리사이즈 옵션 설정 → [미리보기] 또는 [일괄 적용]
```

---

## 2. 미리보기 창 설계 (핵심 신규 기능)

### 레이아웃
```
┌──────────────┬──────────────┬──────────────┐
│  Before      │  After-A     │  After-B     │
│  (원본)       │  [보정 설정]  │  [보정 설정]  │
│              │  (인라인 하단) │  (인라인 하단) │
├──────────────┴──────────────┴──────────────┤
│  EXIF 정보 (스크롤) │ A 보정 설정 │ B 보정 설정  │
├─────────────────────────────────────────────┤
│ [이전] [스킵] [1선택] [2선택] [3선택] [삭제] [다음] [EXIF] │
└─────────────────────────────────────────────┘
```

### 단축키
| 키 | 동작 |
|---|---|
| `1` | Before 기준 리사이즈만 적용해서 저장 후 다음 |
| `2` | After-A 설정으로 저장 후 다음 |
| `3` | After-B 설정으로 저장 후 다음 |
| `Space` / `` ` `` | 저장 없이 스킵 후 다음 |
| `Del` | 원본 파일 삭제 후 다음 |
| `←` / `→` | 이전 / 다음 이동 |
| `E` | EXIF 플로팅 창 토글 |

### 미리보기 렌더링 원칙
- **색보정은 실시간 적용** — After-A/B의 인라인 설정 변경 시 즉시 반영
- **리사이즈는 미리보기에서 미적용** — 저장 시에만 적용 (세 창의 이미지 크기 동일 보장)

---

## 3. 이미지 뷰어 (zoom/pan)

### 동작
- 창 크기에 맞게 자동 fit (위젯 크기 확정 시 자동 계산)
- 마우스 스크롤: 마우스 커서 위치 중심으로 확대/축소 (15% 단계, 범위 5%~2000%)
- 마우스 드래그: 이미지 패닝
- 세 창(Before/After-A/After-B) 줌·패닝 완전 동기화

### Auto-fit 설계
| 상태 | 동작 |
|---|---|
| 새 사진 로드 | `_auto_fit = True` → 위젯 크기 확정 시 fit 계산 |
| 사용자 줌/패닝 | `_auto_fit = False` → 이후 윈도우 리사이즈에도 유지 |
| 다음 사진 이동 | `_auto_fit = True` 리셋 → 새 사진 fit |

---

## 4. 설정 영속성

### 저장 위치
`~/.myphotoworks/config.json`

### 저장 시점
앱 종료 시 `closeEvent`에서 저장

### 저장 항목
보정 옵션 전체(Auto Level/Contrast, 밝기/대비), 리사이즈 설정 전체, 출력 경로 모드·prefix·suffix·품질

### 로드 시점
앱 시작 시 `MainWindow.__init__`에서 로드 → `SettingsPanel`에 반영

---

## 5. 변경된 파일 목록

| 파일 | 변경 유형 | 내용 |
|---|---|---|
| `doc/requirements.md` | 신규 | 요구사항 전체 문서 |
| `models/settings.py` | 재작성 | `ResizeAxis`, `OutputPathMode` enum 추가, 불필요 필드 제거 |
| `processing/resize.py` | 재작성 | `resize_by_axis(image, axis, px)` — 긴축/짧은축 기반 리사이즈 |
| `processing/processor.py` | 재작성 | 간소화, `apply_effects` 파라미터, `save()` 분리 |
| `workers/batch_worker.py` | 재작성 | 출력 경로 3모드, prefix/suffix, 진행 시그널 |
| `ui/thumbnail_panel.py` | 수정 | `remove_selected()` 추가, 고정 너비 제거 |
| `ui/settings_panel.py` | 재작성 | 보정/리사이즈/출력 3탭 |
| `ui/exif_panel.py` | 신규 | 플로팅 EXIF 정보 창 (Tool 타입, 위치 이동 가능) |
| `ui/preview_window.py` | 신규 | 3분할 미리보기, zoom/pan, 단축키 전체 |
| `ui/main_window.py` | 재작성 | 4버튼 상단바, 넓은 썸네일 패널, 상태바+프로그레스바 |
| `utils/config.py` | 수정 | `save_settings()`, `load_settings()` 추가 |
| `src/myphotoworks/__main__.py` | 신규 | `python -m myphotoworks` 진입점 |

---

## 6. 테스트 현황

| 파일 | 테스트 수 | 커버리지 대상 |
|---|---|---|
| `test_effects.py` | 기존 | `processing/effects.py` |
| `test_resize.py` | 10 | `resize_by_axis` 전체 (긴축/짧은축/비율/최솟값) |
| `test_settings.py` | 8 | `AppSettings` 기본값, enum 값, 복사 독립성 |
| `test_processor.py` | 12 | `process()`, `save()`, 미리보기 no-resize 동작 |
| `test_batch_worker.py` | 8 | 출력 경로 3모드, prefix/suffix, 일괄 실행 |
| `test_config.py` | 9 | `save_settings`/`load_settings` 라운드트립, 에러 폴백 |

**총 70개 테스트, 전체 통과**

---

## 7. 미결 사항

- 미리보기 창 추가 기능 (별도 논의 예정)
- Phase 4: 전체 통합 테스트 및 패키징
