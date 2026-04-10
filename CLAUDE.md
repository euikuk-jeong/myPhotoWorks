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

- `doc/context/` 하위 세션 요약 `.md` 파일은 git에 포함한다.
- `CHANGELOG.md`, `README.md` 등 프로젝트 문서 `.md` 파일도 git에 포함한다.
- When staging files, always include `doc/context/*.md` and project `.md` files.

## Todo 관리 규칙

대화 중 발생하는 할 일·아이디어·개선 사항은 `doc/todo/todo.md` 파일로 관리한다.

### Todo 추가 시점
- 대화 중 "나중에", "다음에", "추후", "TODO", "개선 필요" 등의 표현이 나올 때
- 분석 결과 수정이 필요하지만 현재 세션에서 처리하지 않기로 한 항목
- 사용자가 명시적으로 todo로 남겨달라고 요청할 때

### todo.md 형식

```markdown
# Todo

## 미완료

- [ ] 항목 설명 <!-- YYYY-MM-DD 추가 -->

## 완료

- [x] 항목 설명 <!-- YYYY-MM-DD 완료 -->
```

- 날짜는 `<!-- YYYY-MM-DD -->` 주석 형식으로 줄 끝에 표기
- 새 항목은 "미완료" 섹션 맨 위에 추가
- `doc/todo/` 디렉토리가 없으면 생성 후 파일 작성

### Git Rules (todo)
- `doc/todo/todo.md` 파일은 git에 포함한다.
- When staging files, always include `doc/todo/todo.md`.

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
4. `doc/todo/todo.md` 확인 후 이번 세션에서 완료한 항목을 `[x]`로 표시
5. 파일 저장 후 경로를 사용자에게 알림
