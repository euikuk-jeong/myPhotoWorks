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

## Git Rules

- **Markdown files (`.md`) are not committed to git.** This includes context documents under `doc/context/` and any other session notes. The `.gitignore` already excludes `/doc/context/`.
- When staging files, never include `.md` files unless explicitly instructed by the user.
