# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`myPhotoWorks` is a customized Python application built on the photoWorks framework/library. The project is in early development — no implementation exists yet.

## Tech Stack

- **Language**: Python (inferred from `.gitignore` configuration)
- **Potential package managers**: poetry, pdm, pipenv, or uv

## Tech Stack

- **GUI**: PyQt6
- **Image processing**: Pillow + NumPy
- **EXIF**: piexif
- **Package manager**: uv

## Commands

```bash
# Install dependencies
uv sync

# Run the application
uv run python -m myphotoworks

# Run tests
uv run pytest

# Lint
uv run ruff check .
```

## Project Structure

```
src/myphotoworks/
├── main.py               # QApplication entry point
├── ui/                   # GUI modules (PyQt6)
├── processing/           # Image processing (effects, resize, processor)
├── models/               # PhotoItem, AppSettings dataclasses
├── workers/              # QThread batch worker
└── utils/                # exif_reader, config
tests/                    # pytest unit tests
```

## 테스트 규칙

코드를 수정하거나 새 기능을 추가할 때는 반드시 관련 단위 테스트를 함께 작성한다.

- 새 함수/메서드 추가 시 → 해당 함수의 단위 테스트 작성
- 기존 코드 수정 시 → 수정된 동작을 검증하는 테스트 추가 또는 업데이트
- 테스트 파일 위치: `tests/` 디렉토리, 파일명은 `test_<모듈명>.py`
- 테스트 프레임워크: pytest
- GUI 코드(PyQt6)는 테스트가 어려운 경우 로직 부분만이라도 테스트 작성

## Git Rules

- **Markdown files (`.md`) are not committed to git.** This includes context documents under `doc/context/` and any other session notes. The `.gitignore` already excludes `/doc/context/`.
- When staging files, never include `.md` files unless explicitly instructed by the user.

## 세션 종료 규칙

사용자가 "종료", "끝", "bye", "exit", "마무리" 등 세션을 마치려는 의사를 표현하면:

1. 현재 대화에서 수행한 주요 작업을 한국어로 요약
2. 파일명 형식: `doc/context/YYYYMMDD_HHMM_요약제목.md`
   - 날짜/시간은 실제 현재 시각 사용
   - 요약제목은 작업 내용을 2~4단어로 압축
3. 파일 내용 구성:
   - 날짜/시간
   - 작업 목록 (bullet points)
   - 주요 결정 사항 또는 변경 내용
   - 미완료 작업 또는 다음 단계 (있을 경우)
4. 파일 저장 후 경로를 사용자에게 알림
