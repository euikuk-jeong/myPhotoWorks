"""Export the user's adoption decisions as evaluation labels (developer feature)."""
from __future__ import annotations

import json
import os
from pathlib import Path

from myphotoworks.models.group_session import GroupSession

DEV_ENV = "MYPHOTOWORKS_DEV"


def is_dev_mode() -> bool:
    return os.environ.get(DEV_ENV, "").strip().lower() in ("1", "true", "yes", "on")


def write_labels(session: GroupSession, path: Path, root: Path | None = None) -> dict:
    label = session.to_label_dict(root)
    Path(path).write_text(json.dumps(label, ensure_ascii=False, indent=2), encoding="utf-8")
    return label
