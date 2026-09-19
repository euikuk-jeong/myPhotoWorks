# myPhotoWorks

> 카메라로 촬영한 사진을 일괄 처리(리사이즈, Auto Level, Auto Contrast 적용 후 저장)하는 Windows Python 데스크톱 앱.

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

## 개요

**myPhotoWorks**는 PyQt6 기반의 Windows 데스크톱 애플리케이션입니다.
다수의 사진을 불러와 리사이즈, 색상 보정(Auto Level / Auto Contrast), 워터마크 적용 후 지정된 경로에 일괄 저장하는 워크플로를 제공합니다.

### PhotoWorks에 대한 감사와 경위

이 프로젝트는 오랫동안 사랑받아 온 **PhotoWorks** 애플리케이션에 깊은 존경과 감사의 마음을 담아 시작되었습니다.
PhotoWorks는 사진 일괄 처리 분야에서 많은 사용자에게 신뢰받아 온 훌륭한 도구로, 그 기능과 UX에서 큰 영감을 받았습니다.

**myPhotoWorks**는 PhotoWorks의 핵심 워크플로를 기반으로, Python / PyQt6 환경에서 직접 확장·재구현한 프로젝트입니다.
원본 PhotoWorks 애플리케이션은 아래 링크에서 다운로드할 수 있습니다.

> PhotoWorks 원본 다운로드: [https://cafe.naver.com/photoworks2](https://cafe.naver.com/photoworks2)

## 주요 기능

- 사진 다중 선택 로드 및 썸네일 목록 표시
- 리사이즈 (너비/높이 지정, 비율 유지 옵션)
- **Auto Level** — RGB 채널별 히스토그램 스트레치
- **Auto Contrast** — 루미넌스 기반 대비 자동 보정
- 밝기 / 대비 수동 조정
- EXIF 정보 표시 (촬영일, ISO, 파일 크기 등)
- 출력 포맷 선택 (JPEG), 품질 설정
- 배치 처리 진행 상황 표시
- **Lumis Flow (사진 그룹핑·추천)** — 비슷한 사진(연사·필름 스캔)을 자동으로 묶고, 선명도·노출·색감 점수로 추천 사진을 골라줍니다.
  - 그룹 탭: 그룹핑 방식(자동 / 시각 우선 / 유사도만), 유사도 임계값, 순서 무관 전체 비교, EXIF 참고, 추천 가중치(고급)
  - 메인 화면: `[그룹별 보기]`, `[채택만 보기]` — 표시 목록이 곧 미리보기·일괄 적용 대상입니다
  - 그룹 리뷰 창: 여러 장 채택, 그룹 이동·병합·분리, 되돌리기(Ctrl+Z), 채택 사진 내보내기

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

## 다운로드 및 실행

[Releases](https://github.com/euikuk-jeong/myPhotoWorks/releases) 페이지에서 최신 `myPhotoWorks.exe`를 다운로드하여 실행하세요.

> **Windows SmartScreen 경고가 뜨는 경우**
>
> 코드 서명 인증서 없이 배포되는 오픈소스 프로젝트이기 때문에 처음 실행 시 아래와 같은 경고가 표시될 수 있습니다.
>
> 1. "Windows의 PC 보호" 창에서 **"추가 정보"** 클릭
> 2. **"실행"** 버튼 클릭

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
│       ├── ui/                   # GUI 모듈 (메인 창, 프리뷰 창, 썸네일 패널, 그룹 탭/리뷰 창 등)
│       ├── core/                 # 그룹핑·유사도·스코어링 (GUI 의존성 없음)
│       ├── processing/           # 이미지 처리 (effects, resize, processor, 그룹핑 실행, 내보내기)
│       ├── models/               # PhotoItem, AppSettings, GroupSession
│       ├── workers/              # QThread 워커 (배치 처리, 그룹핑)
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
