"""EXIF metadata extraction."""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import piexif

# ── lookup tables ────────────────────────────────────────────────────────────

_METERING = {
    0: "Unknown", 1: "Average", 2: "Center-weighted",
    3: "Spot", 4: "Multi-spot", 5: "Multi-segment",
    6: "Partial", 255: "Other",
}

_PROGRAM = {
    0: "Not defined", 1: "Manual", 2: "Program auto",
    3: "Aperture priority", 4: "Shutter priority",
    5: "Creative", 6: "Action", 7: "Portrait", 8: "Landscape",
}

_ORIENTATION = {
    1: "Normal", 2: "Mirrored", 3: "180°", 4: "Mirrored 180°",
    5: "Mirrored 90° CW", 6: "90° CW", 7: "Mirrored 90° CCW", 8: "90° CCW",
}

# ── helpers ──────────────────────────────────────────────────────────────────

def _rational(val) -> float | None:
    if isinstance(val, (tuple, list)) and len(val) == 2 and val[1] != 0:
        return val[0] / val[1]
    return None


def _decode(raw) -> str:
    if isinstance(raw, bytes):
        return raw.decode("utf-8", errors="replace").rstrip("\x00").strip()
    return str(raw).strip()


def _fmt_aperture(val) -> str:
    f = _rational(val)
    return f"f/{f:.1f}" if f is not None else ""


def _fmt_shutter(val) -> str:
    f = _rational(val)
    if f is None:
        return ""
    if 0 < f < 1:
        return f"1/{round(1 / f)}s"
    return f"{f:.1f}s"


def _fmt_focal(val) -> str:
    f = _rational(val)
    return f"{f:.0f}mm" if f is not None else ""


def _fmt_ev(val) -> str:
    f = _rational(val)
    if f is None:
        return ""
    sign = "+" if f >= 0 else ""
    return f"{sign}{f:.1f} EV"


def _fmt_flash(val) -> str:
    if val is None:
        return ""
    return "Yes" if (val & 1) else "No"


# ── public API ────────────────────────────────────────────────────────────────

def read_exif(path: Path) -> dict[str, str]:
    """Read EXIF + file metadata.

    Keys
    ----
    filename, file_size, file_date,
    make, model, software,
    date, size, orientation,
    flash, focal_length, shutter, aperture, iso,
    exposure_bias, metering_mode, program_mode,
    comment

    All values are strings; missing fields are empty strings.
    """
    result: dict[str, str] = {k: "" for k in (
        "filename", "file_size", "file_date",
        "make", "model", "software",
        "date", "size", "orientation",
        "flash", "focal_length", "shutter", "aperture", "iso",
        "exposure_bias", "metering_mode", "program_mode",
        "comment",
    )}
    result["filename"] = path.name

    # ── file-system info ─────────────────────────────────────────────────────
    try:
        stat = os.stat(path)
        result["file_size"] = f"{stat.st_size:,} bytes"
        result["file_date"] = datetime.fromtimestamp(stat.st_mtime).strftime("%Y:%m:%d %H:%M:%S")
    except Exception:
        pass

    # ── image dimensions ─────────────────────────────────────────────────────
    try:
        from PIL import Image
        with Image.open(path) as img:
            result["size"] = f"{img.width} x {img.height}"
    except Exception:
        pass

    # ── EXIF ─────────────────────────────────────────────────────────────────
    try:
        exif_data = piexif.load(str(path))
    except Exception:
        return result

    ifd0 = exif_data.get("0th", {})
    exif_ifd = exif_data.get("Exif", {})

    result["make"] = _decode(ifd0.get(piexif.ImageIFD.Make, b""))
    result["model"] = _decode(ifd0.get(piexif.ImageIFD.Model, b""))
    result["software"] = _decode(ifd0.get(piexif.ImageIFD.Software, b""))

    ori = ifd0.get(piexif.ImageIFD.Orientation)
    if ori is not None:
        result["orientation"] = _ORIENTATION.get(ori, str(ori))

    raw_date = exif_ifd.get(piexif.ExifIFD.DateTimeOriginal)
    if raw_date:
        result["date"] = _decode(raw_date)

    raw_iso = exif_ifd.get(piexif.ExifIFD.ISOSpeedRatings)
    if raw_iso is not None:
        result["iso"] = str(raw_iso)

    result["shutter"] = _fmt_shutter(exif_ifd.get(piexif.ExifIFD.ExposureTime))
    result["aperture"] = _fmt_aperture(exif_ifd.get(piexif.ExifIFD.FNumber))
    result["focal_length"] = _fmt_focal(exif_ifd.get(piexif.ExifIFD.FocalLength))
    result["exposure_bias"] = _fmt_ev(exif_ifd.get(piexif.ExifIFD.ExposureBiasValue))
    result["flash"] = _fmt_flash(exif_ifd.get(piexif.ExifIFD.Flash))

    met = exif_ifd.get(piexif.ExifIFD.MeteringMode)
    if met is not None:
        result["metering_mode"] = _METERING.get(met, str(met))

    prog = exif_ifd.get(piexif.ExifIFD.ExposureProgram)
    if prog is not None:
        result["program_mode"] = _PROGRAM.get(prog, str(prog))

    raw_comment = exif_ifd.get(piexif.ExifIFD.UserComment)
    if raw_comment and len(raw_comment) > 8:
        try:
            result["comment"] = raw_comment[8:].decode("utf-8", errors="replace").rstrip("\x00").strip()
        except Exception:
            pass

    return result
