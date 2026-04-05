# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.9.2] - 2026-04-06

### Added
- EXIF Orientation 태그 기반 이미지 자동 회전 적용
  - 미리보기 창 (Before 패널, After-A/B 패널, 프리패치 캐시)
  - 메인 화면 썸네일 패널
  - 일괄 처리(배치) 경로 (`processor.py` 직접 로드 시)
  - 레이아웃은 기존 좌→우 3분할 유지, 이미지 픽셀만 올바른 방향으로 보정

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

[Unreleased]: https://github.com/euikuk-jeong/myPhotoWorks/compare/v0.9.2...HEAD
[0.9.2]: https://github.com/euikuk-jeong/myPhotoWorks/compare/v0.9.1...v0.9.2
[0.9.1]: https://github.com/euikuk-jeong/myPhotoWorks/compare/v0.9.0...v0.9.1
[0.9.0]: https://github.com/euikuk-jeong/myPhotoWorks/releases/tag/v0.9.0
