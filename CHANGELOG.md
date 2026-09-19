# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **그룹핑·추천 방식 설명서(HTML)**: 그림(인포그래픽)과 예제로 그룹핑·촬영 시각/EXIF·선명도/노출/색감 점수·추천·채택 방식과 설정 요령, 한계를 설명. 그룹 탭 맨 위 "알고리즘 설명서 보기" 버튼으로 기본 브라우저에서 열림 (오프라인, 앱에 포함)
- 그룹 리뷰 창의 큰 사진 영역에서 마우스 휠로 확대/축소(커서 위치 기준), 왼쪽 버튼 드래그로 이동, 가운데 버튼 클릭으로 화면 맞춤·위치 초기화. 확대하면 고해상도 이미지를 백그라운드로 불러와 흐림 여부를 자세히 확인할 수 있음. 같은 사진에서 채택을 바꿔도 확대 상태 유지, 다른 사진으로 이동하면 화면 맞춤으로 초기화

### Changed
- 그룹 리뷰 창 [위/아래 그룹과 병합]: 병합 후 합쳐진 그룹에서 추천 1장만 채택되도록 변경 (이전에는 두 그룹의 채택이 그대로 합쳐짐). 되돌리기(Ctrl+Z)로 병합 전 채택 상태 복원
- 그룹 리뷰 창 하단 사진 목록: 사진이 많을 때 옆으로 스크롤하지 않고 여러 줄로 배치되어 아래로 스크롤. 사진 영역과 목록 사이 경계를 드래그해 목록 높이를 조절 가능
- 그룹 탭을 ① 그룹핑 설정 / ② 그룹핑 실행·결과 / ③ 추천 설정 세 개의 박스로 구획 분리
- 유사도 임계값 표현을 일반 사용자용으로 변경: "얼마나 비슷해야 묶을까요?" + 깐깐하게 ↔ 너그럽게 + 단계별(아주 깐깐함~아주 너그러움) 쉬운 설명과 조정 요령
- EXIF(초점거리·렌즈·조리개) 참고 옵션을 기본 켜짐으로 변경. 사진 대부분에 정보가 없으면 자동으로 무시하고 별도 경고를 표시하지 않음 (기존 설정 파일도 새 기본값으로 이전)
- 옵션 설명 문구를 쉬운 말로 정리

### Fixed
- 그룹핑 방식 드롭다운 목록과 툴팁이 밝은 배경에 밝은 글자로 표시되어 읽기 어렵던 문제
- 시간 간격 입력칸(`QDoubleSpinBox`)과 접이식 헤더 버튼(`QToolButton`)의 테마 스타일 누락

## [1.1.0] - 2026-09-19

### Added
- **Lumis Flow — 사진 그룹핑·추천**
  - 시각 유사도(dHash + 색 히스토그램)로 비슷한 사진을 그룹핑. 촬영 시각은 신뢰될 때만 보조 신호로 사용(연사 허용, 필름 스캔처럼 시각이 몰린 데이터는 자동 제외)
  - 그룹핑 방식(자동 / 시각 우선 / 유사도만), 유사도 임계값·시각 간격 조정
  - 순서 무관 전체 비교(떨어져 있는 같은 장면 묶기), EXIF 초점거리·렌즈·조리개 참고 옵션(값이 일관될 때만 적용)
  - 선명도·노출·색감 품질 점수와 추천 이유 표시, 추천 가중치 조정(고급). 가중치 변경은 이미지 재분석 없이 즉시 반영
  - 메인 화면 `[그룹별 보기]` / `[채택만 보기]`. 표시 목록이 미리보기·일괄 적용 대상이 되며 `[일괄 적용 (N장)]`으로 표시
  - 카드 체크박스·Space 키로 여러 장 채택
  - 그룹 리뷰 창: 큰 미리보기, 점수 막대, 필름스트립, 채택 일괄 버튼, 그룹 이동·병합·분리(드래그 포함), 되돌리기(작업 1건 단위), 채택 사진 내보내기
  - 보정 설정 변경 시 `[점수 다시 계산]`으로 노출·색감만 재계산(그룹·수동 편집 유지)
  - 그룹핑 후 사진 추가·삭제 시 기존 그룹 결과 유지(추가한 사진은 그룹핑 전 단독 사진으로 표시)
- `core/` 패키지: `analysis_image`, `similarity`, `grouping`, `scoring`, `pipeline` (GUI 의존성 없음)
- `GroupSession`, `GroupWorker`, `RescoreWorker`

### Known limitations
- 그룹핑 기본값(유사도 임계값 등)과 촬영 시각 신뢰 판정은 합성 이미지 기준이며 실제 사진(필름 스캔·연사 등)으로 튜닝하지 않았습니다. 결과가 맞지 않으면 그룹 탭의 유사도 임계값 슬라이더와 그룹 리뷰 창의 그룹 수정으로 조정하세요.
- 분석용 축소본(장변 512px)에서는 약한 블러가 "흐림" 배지로 표시되지 않을 수 있습니다.

### Changed
- `ThumbnailPanel`: 표시 목록 필터, 그룹 헤더, 카드 오버레이(체크박스·추천 별·점수·흐림 배지), 썸네일 로딩을 시그널 기반으로 변경
- `SettingsPanel`: 4번째 "그룹" 탭 추가
- `AppSettings` / 설정 파일: 그룹핑 관련 항목 추가(기존 설정 파일은 기본값으로 호환)

## [0.9.7] - 2026-04-18

### Added
- 후지필름 Film Simulation 레시피 보정 기능 (7종 번들: Provia, Velvia, Astia, Classic Chrome, Pro Neg. Hi, Eterna, Acros)
- `CorrectionMode` enum으로 보정 방식 통합 — 보정 없음 / Auto Level / Auto Contrast / Auto Level+Contrast / 레시피
- 보정 탭 드롭다운 UI: 색상 아이콘(FilmSim별) + 비활성 섹션 헤더 "── Fujifilm Recipes ──"
- 레시피 정보 테이블 패널 (필름 시뮬레이션, 화이트밸런스, 톤 커브, 채도, 선명도, 그레인) — SettingsPanel·미리보기 공통
- `src/fuji_fp1/` 폴더: FP1 XML 파일 보관, 임포트 시 자동 스캔·파싱으로 레시피 목록 생성
- `Fp1Parser` 클래스: FilmSimulation 문자열 매핑, WB 프리셋→켈빈 변환, 레거시 Saturation 태그 지원
- 미리보기 150ms 디바운스 + `QRunnable` 백그라운드 렌더링으로 UI 프리즈 방지

### Changed
- `AppSettings`: `auto_level`/`auto_contrast` bool 필드 → `correction_mode: CorrectionMode` + `recipe_name: str`으로 대체
- `config.py`: 구 설정 파일(`auto_level`/`auto_contrast` bool) 자동 마이그레이션
- Clarity 효과: `GaussianBlur(radius=10)` → `BoxBlur(radius=8)` (~10배 속도 개선)
- 미리보기 하단 바: 모든 패널(원본·A·B) 동일 고정 높이 + 레시피 정보를 `QTableWidget`으로 통일

## [0.9.6] - 2026-04-11

### Added
- 메인 화면 아이템 우클릭 컨텍스트 메뉴에 "정보" 항목 추가
- Windows 시스템 메뉴(타이틀바 우클릭)에 "정보" 항목 추가
- F1 단축키로 정보 다이얼로그 호출
- 미리보기 창: 마우스 가운데 버튼으로 화면 맞춤(Home과 동일 동작)

### Changed
- 메인 화면 메뉴바 제거 (정보는 F1 / 우클릭 메뉴로 접근)
- 미리보기 창: 상태 표시 레이블 제거 → 윈도우 타이틀에 `N/전체 — 파일명` 표시
- 미리보기 창: 버튼 바에 구분 배경색 적용 (파란 그라디언트 + 상단 구분선)
- `auto_level`: 채널별 독립 스트레칭 → 루미넌스 기반 단일 LUT 적용 (색상 캐스트 제거)
- `auto_contrast`: 감마 커브 방식 → `ImageOps.autocontrast(cutoff=1)` 선형 min-max 스트레칭

### Fixed
- PyQt6 6.10.x에서 `nativeEvent` 오버라이드 시 `super()` 호출로 인한 앱 크래시 수정
- QSS `content: ""` 속성으로 인한 시작 시 "Unknown property content" 경고 8회 출력 제거

## [0.9.3] - 2026-04-10

### Added
- Glassmorphism UI 테마 적용
  - 어두운 그라디언트 배경 (`#0d1117 → #161b22 → #1c2333`) 전체 적용
  - 반투명 유리 질감 패널: `rgba(255,255,255,0.08)` 배경 + `rgba(255,255,255,0.18)` 테두리
  - `glass_theme.qss` 파일로 전체 위젯 스타일 중앙 관리
  - 버튼 hover/press 상태별 glass 효과 및 accent 색상(`rgba(88,166,255,0.90)`) 적용
  - 스크롤바, 슬라이더, 입력 필드, 탭, GroupBox 등 모든 위젯 재스타일링

### Changed
- 앱 스타일을 `windowsvista` → `Fusion`으로 변경 (QSS 커스터마이징 호환성 향상)
- `MainWindow`, `PreviewWindow`, `AboutDialog`에 `paintEvent` 추가로 그라디언트 배경 렌더링
- 미리보기 창 이미지 뷰 배경색 흰색 → 어두운 톤(`#0f141e`)으로 변경
- 인라인 `setStyleSheet` 호출을 QSS `objectName` 셀렉터 방식으로 통합

## [0.9.2] - 2026-04-06

### Added
- EXIF Orientation 태그 기반 이미지 자동 회전 적용
  - 미리보기 창 (Before 패널, After-A/B 패널, 프리패치 캐시)
  - 메인 화면 썸네일 패널
  - 일괄 처리(배치) 경로 (`processor.py` 직접 로드 시)
  - 레이아웃은 기존 좌→우 3분할 유지, 이미지 픽셀만 올바른 방향으로 보정
  - 저장 시 EXIF Orientation 태그를 1(Normal)로 초기화하여 이중 회전 방지

## [0.9.1] - 2026-03-30

### Fixed
- 손상된(truncated) JPEG 파일 로드 시 미리보기 창 크래시 현상 수정
  - `PIL.ImageFile.LOAD_TRUNCATED_IMAGES = True` 설정으로 부분 로드 허용
  - `_load_current` 동기 경로에 `OSError` 예외 처리 추가 — 실패 시 경고 다이얼로그 표시

## [0.9.0] - 2026-03-30

### Added
- 사진 일괄 처리 기능 (리사이즈, Auto Level, Auto Contrast)
- 썸네일 패널 및 파일 목록 관리
- EXIF 정보 표시 패널
- 미리보기 창 (이전/다음 탐색)
- 설정 저장 및 복원 (창 크기, 마지막 경로 등)
- 정보(About) 다이얼로그 (버전, 저작권, 아이콘 포함)
- Windows 실행 파일(PyInstaller) 빌드 지원

[Unreleased]: https://github.com/euikuk-jeong/myPhotoWorks/compare/v0.9.7...HEAD
[0.9.7]: https://github.com/euikuk-jeong/myPhotoWorks/compare/v0.9.6...v0.9.7
[0.9.6]: https://github.com/euikuk-jeong/myPhotoWorks/compare/v0.9.3...v0.9.6
[0.9.3]: https://github.com/euikuk-jeong/myPhotoWorks/compare/v0.9.2...v0.9.3
[0.9.2]: https://github.com/euikuk-jeong/myPhotoWorks/compare/v0.9.1...v0.9.2
[0.9.1]: https://github.com/euikuk-jeong/myPhotoWorks/compare/v0.9.0...v0.9.1
[0.9.0]: https://github.com/euikuk-jeong/myPhotoWorks/releases/tag/v0.9.0
