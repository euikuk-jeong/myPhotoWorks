"""Recommendation v2, stage 3 — Fujifilm AF point from the MakerNote (plan §6-2), pure parsing.

New ``core/afpoint.py`` API under test (no files, no Qt):

    FujiFocus(af: bool, pixel: (x, y) | None)                 frozen value
    parse_fuji_focus(makernote: bytes) -> FujiFocus | None    FocusMode (tag 0x1021: 0 = Auto,
        1 = Manual, 65535 = Movie) and FocusPixel (tag 0x1023: two SHORTs) of a FUJIFILM
        MakerNote ("FUJIFILM" + little-endian IFD offset + IFD). ``None`` for anything that is
        not a readable Fujifilm MakerNote or has no FocusMode; never raises. A FocusPixel of
        (0, 0) means "no point".
    normalize_focus_point(pixel, exif_size, orientation=1) -> (x, y) | None
        pixel -> share of the EXIF pixel dimensions (0..1) -> turned into the upright (displayed)
        frame by the EXIF orientation (1..8; ``None`` = 1). ``None`` when the point lies outside
        the frame or the size is unusable.

The test bytes (``tests.synthetic.fuji_makernote``) follow the layout the cameras write; a real
camera sample still has to confirm the coordinate reference (see the stage-3 report).
"""
import pytest

from tests.synthetic import fuji_makernote


def _parse(blob):
    from myphotoworks.core.afpoint import parse_fuji_focus

    return parse_fuji_focus(blob)


# ---- parse_fuji_focus -----------------------------------------------------------------------


def test_autofocus_and_the_focus_pixel_are_read():
    from myphotoworks.core.afpoint import FujiFocus

    assert _parse(fuji_makernote(0, (1200, 900))) == FujiFocus(True, (1200, 900))


def test_manual_focus_is_not_autofocus():
    focus = _parse(fuji_makernote(1, (1200, 900)))
    assert focus.af is False


def test_movie_focus_mode_is_not_autofocus():
    assert _parse(fuji_makernote(65535, (1200, 900))).af is False


def test_a_missing_focus_pixel_leaves_the_point_open():
    focus = _parse(fuji_makernote(0, None))
    assert focus.af is True and focus.pixel is None


def test_a_zero_focus_pixel_means_no_point():
    assert _parse(fuji_makernote(0, (0, 0))).pixel is None


def test_without_a_focus_mode_nothing_can_be_said():
    assert _parse(fuji_makernote(None, (1200, 900))) is None


def test_the_order_of_the_entries_does_not_matter():
    from myphotoworks.core.afpoint import FujiFocus

    assert _parse(fuji_makernote(0, (321, 654), reverse=True)) == FujiFocus(True, (321, 654))


@pytest.mark.parametrize("blob", [
    b"", b"FUJIFILM", b"FUJIFILM\x0c\x00\x00\x00", b"NIKON\x00\x02\x10\x00\x00" + b"\x00" * 40,
    b"\x00" * 64, b"FUJIFILM" + b"\xff" * 4 + b"\x00" * 20,
], ids=["empty", "header-only", "no-ifd", "other-maker", "zeros", "offset-beyond-data"])
def test_anything_that_is_not_a_fuji_makernote_gives_none(blob):
    assert _parse(blob) is None


def test_a_truncated_makernote_never_raises():
    full = fuji_makernote(0, (1200, 900))
    for length in range(len(full)):
        _parse(full[:length])                                  # must not raise
    assert _parse(full[:11]) is None                           # header incomplete


def test_an_absurd_entry_count_gives_none():
    blob = bytearray(fuji_makernote(0, (1200, 900)))
    blob[12:14] = b"\xff\xff"                                  # claims 65535 entries
    assert _parse(bytes(blob)) is None


def test_the_focus_value_is_a_frozen_value():
    from dataclasses import FrozenInstanceError

    focus = _parse(fuji_makernote(0, (1, 2)))
    with pytest.raises(FrozenInstanceError):
        focus.af = False


# ---- normalize_focus_point ------------------------------------------------------------------


def _norm(pixel, size=(4000, 3000), orientation=1):
    from myphotoworks.core.afpoint import normalize_focus_point

    return normalize_focus_point(pixel, size, orientation)


def test_the_point_becomes_a_share_of_the_exif_size():
    assert _norm((1200, 900)) == pytest.approx((0.3, 0.3))
    assert _norm((1200, 900), orientation=None) == pytest.approx((0.3, 0.3))


@pytest.mark.parametrize(("orientation", "expected"), [
    (1, (0.2, 0.7)), (2, (0.8, 0.7)), (3, (0.8, 0.3)), (4, (0.2, 0.3)),
    (5, (0.7, 0.2)), (6, (0.3, 0.2)), (7, (0.3, 0.8)), (8, (0.7, 0.8)),
])
def test_the_point_follows_the_exif_orientation_into_the_upright_frame(orientation, expected):
    """Stored frame point (0.2, 0.7); 6 = shown rotated 90 deg clockwise, 8 = counter-clockwise."""
    assert _norm((800, 2100), orientation=orientation) == pytest.approx(expected)


@pytest.mark.parametrize("pixel", [(4000, 100), (100, 3000), (-5, 100), (100, -1), (9999, 9999)])
def test_a_point_outside_the_frame_gives_none(pixel):
    assert _norm(pixel) is None


def test_the_last_pixel_is_still_inside():
    x, y = _norm((3999, 2999))
    assert 0.99 < x < 1.0 and 0.99 < y < 1.0


@pytest.mark.parametrize("size", [(0, 3000), (4000, 0), (-1, 5), None])
def test_an_unusable_size_gives_none(size):
    assert _norm((1200, 900), size=size) is None
