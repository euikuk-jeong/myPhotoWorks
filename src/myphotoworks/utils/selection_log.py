"""Selection log: what was recommended and what the user adopted, kept on this computer only.

One schema-1 label file (``GroupSession.to_label_dict()`` plus ``logged_at``) is written per saved
review into ``~/.myphotoworks/selection_logs``. Only relative file names and the choices are
stored - no pixel data. The files are what ``dev/eval_metrics`` reads, so a log folder is
evaluated like any exported label. Nothing here raises: a log that cannot be written is simply
not written.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from myphotoworks.models.group_session import GroupSession

logger = logging.getLogger(__name__)


def selection_log_dir() -> Path:
    return Path.home() / ".myphotoworks" / "selection_logs"


def _create_unique(directory: Path, stem: str):
    """Open ``<stem>.json`` for writing, or ``<stem>-1.json``, ... if it exists already."""
    n = 0
    while True:
        path = directory / (f"{stem}.json" if n == 0 else f"{stem}-{n}.json")
        try:
            return path, path.open("x", encoding="utf-8")
        except FileExistsError:
            n += 1


def save_selection_log(
    session: GroupSession, directory: Path | None = None, now: datetime | None = None
) -> Path | None:
    """Write the review as a label file; ``None`` when nothing was reviewed (no group of two or
    more photos was opened or edited) or the file could not be written."""
    try:
        label = session.to_label_dict()
        if not any(g["reviewed"] for g in label["groups"]):
            return None
        now = now or datetime.now()
        label["logged_at"] = now.isoformat(timespec="seconds")
        target = Path(directory) if directory is not None else selection_log_dir()
        target.mkdir(parents=True, exist_ok=True)
        path, handle = _create_unique(target, now.strftime("%Y%m%d-%H%M%S"))
        with handle:
            json.dump(label, handle, ensure_ascii=False, indent=2)
        return path
    except Exception as e:
        logger.warning("selection log not saved: %s", e)
        return None


def load_selection_logs(directory: Path | None = None) -> list[dict]:
    """Saved labels, oldest first. Files that are not labels (or not JSON) are skipped."""
    target = Path(directory) if directory is not None else selection_log_dir()
    entries = []
    for path in sorted(target.glob("*.json")) if target.is_dir() else []:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict) and "schema" in data and isinstance(data.get("groups"), list):
            entries.append(data)
    return sorted(entries, key=lambda d: str(d.get("logged_at", "")))
