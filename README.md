# myPhotoWorks

> 카메라로 촬영한 사진을 일괄 처리(리사이즈, Auto Level, Auto Contrast 적용 후 저장)하는 Windows Python 데스크톱 앱.

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

## 개요

**myPhotoWorks**는 PyQt6 기반의 Windows 데스크톱 애플리케이션입니다.
다수의 사진을 불러와 리사이즈, 색상 보정(Auto Level / Auto Contrast), 워터마크 적용 후 지정된 경로에 일괄 저장하는 워크플로를 제공합니다.

## 주요 기능

- 사진 다중 선택 로드 및 썸네일 목록 표시
- 리사이즈 (너비/높이 지정, 비율 유지 옵션)
- **Auto Level** — RGB 채널별 히스토그램 스트레치
- **Auto Contrast** — 루미넌스 기반 대비 자동 보정
- 밝기 / 대비 수동 조정
- 흑백 변환, 선명도(Sharpen), 가우시안 블러
- 타임스탬프 / 텍스트 워터마크 오버레이
- EXIF 정보 표시 (촬영일, ISO, 파일 크기 등)
- 출력 포맷 선택 (JPEG / PNG), 품질 설정
- 배치 처리 진행 상황 표시

## 기술 스택 및 의존성

| 역할 | 라이브러리 | 버전 | 라이선스 |
|---|---|---|---|
| GUI | PyQt6 | ≥ 6.6.0 | GPL v3 |
| 이미지 처리 | Pillow | ≥ 10.0.0 | HPND (MIT-like) |
| 이미지 처리 | NumPy | ≥ 1.26.0 | BSD 3-Clause |
| EXIF | piexif | ≥ 1.1.3 | MIT |
| 패키지 관리 | uv | — | MIT |
| EXE 빌드 | PyInstaller | (dev) | GPL v2 (with bootloader exception) |

> **라이선스 참고**: PyQt6이 GPL v3를 사용하므로 본 애플리케이션을 배포할 경우 GPL v3 조건을 따라야 합니다. 소스 비공개 상업 배포가 필요한 경우 PyQt6 상업 라이선스 구매 또는 PySide6(LGPL v3)로의 전환이 필요합니다. 현재 이 프로젝트는 **개인 사용 목적**으로 개발되고 있습니다.

## 요구 사항

- Python 3.11+
- Windows 10 / 11
- [uv](https://github.com/astral-sh/uv) 패키지 관리자

## 설치

```bash
git clone https://github.com/euikuk-jeong/myPhotoWorks.git
cd myPhotoWorks
uv sync
```

## 실행

```bash
uv run python -m myphotoworks
```

## 개발

```bash
# 테스트 실행
uv run pytest

# 린트
uv run ruff check .
```

## 프로젝트 구조

```
myPhotoWorks/
├── pyproject.toml
├── src/
│   └── myphotoworks/
│       ├── main.py               # QApplication 진입점
│       ├── ui/                   # GUI 모듈 (메인 창, 프리뷰 창, 썸네일 패널 등)
│       ├── processing/           # 이미지 처리 (effects, resize, processor)
│       ├── models/               # PhotoItem, AppSettings dataclass
│       ├── workers/              # QThread 배치 처리 워커
│       └── utils/                # EXIF 읽기, 설정 저장/로드
└── tests/                        # pytest 단위 테스트
```

## Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a new branch (`git checkout -b feature/your-feature`)
3. Commit your changes (`git commit -m 'Add your feature'`)
4. Push to the branch (`git push origin feature/your-feature`)
5. Open a Pull Request

## License

본 프로젝트의 자체 코드는 MIT License로 작성되었으나, 런타임 의존성인 PyQt6이 GPL v3를 적용하고 있어 배포 시에는 GPL v3 조건이 적용됩니다. 자세한 내용은 [LICENSE](LICENSE) 파일을 참조하세요.
