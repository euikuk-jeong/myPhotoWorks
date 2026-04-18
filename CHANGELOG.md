# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
