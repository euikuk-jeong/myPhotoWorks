"""Fujifilm AF point from the EXIF MakerNote (stage 3, pure parsing, no files).

A FUJIFILM MakerNote is ``"FUJIFILM"`` + a little-endian offset (from the start of the note) to a
TIFF-like IFD: a 2-byte entry count, then 12-byte entries (tag, type, count, value / offset).
Two tags matter: 0x1021 FocusMode (SHORT: 0 = Auto, 1 = Manual, 65535 = Movie) and 0x1023
FocusPixel (two SHORTs, x and y in pixels of the EXIF pixel dimensions). Anything unreadable gives
``None``; nothing here raises.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass

TAG_FOCUS_MODE = 0x1021
TAG_FOCUS_PIXEL = 0x1023
_HEADER = b"FUJIFILM"
_TYPE_SHORT = 3
_FOCUS_AUTO = 0


@dataclass(frozen=True)
class FujiFocus:
    af: bool                                  # FocusMode is Auto
    pixel: tuple[int, int] | None = None      # FocusPixel, None when missing or (0, 0)
    mode: int | None = None                   # the raw FocusMode value (for the debug export)


def parse_fuji_focus(makernote: bytes) -> FujiFocus | None:
    """FocusMode / FocusPixel of a FUJIFILM MakerNote; ``None`` if it is not a readable one, is
    cut short, or has no FocusMode."""
    try:
        if len(makernote) < 14 or not makernote.startswith(_HEADER):
            return None
        (offset,) = struct.unpack_from("<I", makernote, len(_HEADER))
        if offset + 2 > len(makernote):
            return None
        (count,) = struct.unpack_from("<H", makernote, offset)
        first = offset + 2
        if count == 0 or first + 12 * count > len(makernote):
            return None
        mode = pixel = None
        for i in range(count):
            pos = first + 12 * i
            tag, typ, n = struct.unpack_from("<HHI", makernote, pos)
            if typ != _TYPE_SHORT:
                continue
            if tag == TAG_FOCUS_MODE and n >= 1:
                (mode,) = struct.unpack_from("<H", makernote, pos + 8)
            elif tag == TAG_FOCUS_PIXEL and n == 2:
                pixel = struct.unpack_from("<HH", makernote, pos + 8)
        if mode is None:
            return None
        return FujiFocus(mode == _FOCUS_AUTO, pixel if pixel and pixel != (0, 0) else None, mode)
    except (struct.error, ValueError):
        return None


# stored-frame share (x, y) -> upright (displayed) frame, per EXIF orientation
_ORIENTATION = {
    2: lambda x, y: (1 - x, y),
    3: lambda x, y: (1 - x, 1 - y),
    4: lambda x, y: (x, 1 - y),
    5: lambda x, y: (y, x),
    6: lambda x, y: (1 - y, x),
    7: lambda x, y: (1 - y, 1 - x),
    8: lambda x, y: (y, 1 - x),
}


def normalize_focus_point(
    pixel: tuple[int, int], exif_size: tuple[int, int] | None, orientation: int | None = 1
) -> tuple[float, float] | None:
    """The focus pixel as shares (0..1) of the upright frame, or ``None`` when ``exif_size`` is
    unusable or the point lies outside it. ``orientation`` is the EXIF value (1 / ``None`` =
    stored upright)."""
    if not exif_size or exif_size[0] <= 0 or exif_size[1] <= 0:
        return None
    w, h = exif_size
    x, y = pixel
    if not (0 <= x < w and 0 <= y < h):
        return None
    return _ORIENTATION.get(orientation or 1, lambda a, b: (a, b))(x / w, y / h)
