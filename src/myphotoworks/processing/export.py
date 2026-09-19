"""Copy adopted photos into a folder (original files, unmodified)."""
from __future__ import annotations

import shutil
from pathlib import Path

from myphotoworks.models.photo_item import PhotoItem


def _unique_target(dest_dir: Path, name: str) -> Path:
    target = dest_dir / name
    stem, suffix, n = target.stem, target.suffix, 1
    while target.exists():
        target = dest_dir / f"{stem}_{n}{suffix}"
        n += 1
    return target


def export_adopted(photos: list[PhotoItem], dest_dir: Path) -> tuple[int, list[str]]:
    """Copy every adopted photo into ``dest_dir``.

    Existing files are never overwritten (a numeric suffix is added). Returns
    (copied_count, error_messages).
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    copied, errors = 0, []
    for p in photos:
        if not p.is_adopted:
            continue
        try:
            shutil.copy2(p.source_path, _unique_target(dest_dir, p.source_path.name))
            copied += 1
        except OSError as e:
            errors.append(f"{p.source_path.name}: {e}")
    return copied, errors
