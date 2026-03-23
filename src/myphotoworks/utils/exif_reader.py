"""EXIF metadata extraction."""
from __future__ import annotations

from pathlib import Path

import piexif


_EXIF_DATE_TAG = piexif.ExifIFD.DateTimeOriginal
_EXIF_ISO_TAG = piexif.ExifIFD.ISOSpeedRatings
_EXIF_USER_COMMENT_TAG = piexif.ExifIFD.UserComment


def read_exif(path: Path) -> dict[str, str]:
    """Read EXIF data from a JPEG file.

    Returns a dict with keys: date, filename, size, iso, comment.
    Missing or unreadable fields are returned as empty strings.
    """
    result: dict[str, str] = {
        "date": "",
        "filename": path.name,
        "size": "",
        "iso": "",
        "comment": "",
    }

    try:
        from PIL import Image
        with Image.open(path) as img:
            result["size"] = f"{img.width} x {img.height}"
    except Exception:
        pass

    try:
        exif_data = piexif.load(str(path))
    except Exception:
        return result

    exif_ifd = exif_data.get("Exif", {})

    # DateTimeOriginal
    raw_date = exif_ifd.get(_EXIF_DATE_TAG)
    if raw_date:
        try:
            result["date"] = raw_date.decode("ascii", errors="replace")
        except Exception:
            pass

    # ISO
    raw_iso = exif_ifd.get(_EXIF_ISO_TAG)
    if raw_iso is not None:
        result["iso"] = str(raw_iso)

    # UserComment (first 8 bytes are charset marker, skip them)
    raw_comment = exif_ifd.get(_EXIF_USER_COMMENT_TAG)
    if raw_comment and len(raw_comment) > 8:
        try:
            result["comment"] = raw_comment[8:].decode("utf-8", errors="replace").rstrip("\x00")
        except Exception:
            pass

    return result
