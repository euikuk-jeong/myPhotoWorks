"""Recommendation v2, stage 3 — reading the AF point from a file (plan §6-2).

``utils/exif_reader.read_af_point(path) -> (x, y) | None`` returns the AF point as shares of the
*upright* (displayed) frame, only when it can be trusted:

    * Make is FUJIFILM, the MakerNote is readable and FocusMode is Auto
    * the EXIF pixel dimensions exist and the point lies inside them
    * the file still has the shape the camera wrote (same aspect ratio as the EXIF dimensions;
      a downscaled copy is fine, a crop is not)

Manual lenses, scans (no EXIF), other makers and edited / cropped files all give ``None``, so
the subject chain skips them on its own. ``read_hints(path).af_point`` carries the same value
(``core.grouping.ExifHints.af_point``, default ``None``). Nothing here ever raises.
"""
import piexif
import pytest
from PIL import Image

from tests.synthetic import fuji_jpeg, fuji_makernote, texture, to_rgb_image


def _af(path):
    from myphotoworks.utils.exif_reader import read_af_point

    return read_af_point(path)


def test_an_autofocus_photo_gives_the_point_as_a_share_of_the_frame(tmp_path):
    path = fuji_jpeg(tmp_path / "a.jpg", focus_pixel=(1200, 900))
    assert _af(path) == pytest.approx((0.3, 0.3))


def test_the_point_is_turned_into_the_upright_frame(tmp_path):
    """Stored point (0.2, 0.7), orientation 6 (shown rotated 90 deg clockwise): (0.3, 0.2)."""
    path = fuji_jpeg(tmp_path / "a.jpg", focus_pixel=(800, 2100), orientation=6)
    assert _af(path) == pytest.approx((0.3, 0.2))


def test_a_downscaled_copy_keeps_the_point(tmp_path):
    path = fuji_jpeg(tmp_path / "a.jpg", gray=texture(192, 256), focus_pixel=(1200, 900))
    assert _af(path) == pytest.approx((0.3, 0.3))


def test_manual_focus_gives_none(tmp_path):
    assert _af(fuji_jpeg(tmp_path / "m.jpg", focus_mode=1)) is None


def test_another_maker_gives_none(tmp_path):
    assert _af(fuji_jpeg(tmp_path / "c.jpg", make=b"Canon")) is None


def test_a_cropped_file_gives_none(tmp_path):
    cropped = fuji_jpeg(tmp_path / "c.jpg", gray=texture(384, 400))       # 1.04 vs 1.33
    assert _af(cropped) is None


def test_missing_exif_dimensions_give_none(tmp_path):
    assert _af(fuji_jpeg(tmp_path / "d.jpg", exif_size=None)) is None


def test_a_point_outside_the_exif_frame_gives_none(tmp_path):
    assert _af(fuji_jpeg(tmp_path / "o.jpg", focus_pixel=(5000, 900))) is None


def test_no_focus_pixel_gives_none(tmp_path):
    assert _af(fuji_jpeg(tmp_path / "n.jpg", focus_pixel=None)) is None


def test_a_corrupt_makernote_gives_none(tmp_path):
    path = fuji_jpeg(tmp_path / "x.jpg", makernote=b"FUJIFILM" + b"\xff" * 30)
    assert _af(path) is None


def test_scans_and_other_files_give_none_without_raising(tmp_path):
    to_rgb_image(texture()).save(tmp_path / "scan.jpg", "JPEG")           # no EXIF at all
    Image.new("RGB", (64, 48)).save(tmp_path / "x.png")
    plain = tmp_path / "plain.jpg"
    to_rgb_image(texture()).save(
        plain, "JPEG", exif=piexif.dump({"0th": {piexif.ImageIFD.Make: b"FUJIFILM"}}))
    (tmp_path / "broken.jpg").write_bytes(b"not an image")
    for name in ("scan.jpg", "x.png", "plain.jpg", "broken.jpg", "missing.jpg"):
        assert _af(tmp_path / name) is None


# ---- ExifHints ------------------------------------------------------------------------------


def test_exif_hints_have_an_af_point_that_defaults_to_none():
    from myphotoworks.core.grouping import ExifHints

    assert ExifHints().af_point is None
    assert ExifHints(focal=35.0, af_point=(0.3, 0.4)).af_point == (0.3, 0.4)


def test_read_hints_carries_the_af_point(tmp_path):
    from myphotoworks.utils.exif_reader import read_hints

    af = fuji_jpeg(tmp_path / "a.jpg", focus_pixel=(1200, 900))
    mf = fuji_jpeg(tmp_path / "m.jpg", focus_mode=1)
    assert read_hints(af).af_point == pytest.approx((0.3, 0.3))
    assert read_hints(mf).af_point is None


def test_read_hints_still_reads_the_other_hints(tmp_path):
    """Regression guard: focal length and lens come along as before."""
    from myphotoworks.utils.exif_reader import read_hints

    path = tmp_path / "f.jpg"
    exif = {"0th": {piexif.ImageIFD.Make: b"FUJIFILM"},
            "Exif": {piexif.ExifIFD.FocalLength: (35, 1), piexif.ExifIFD.FNumber: (28, 10),
                     piexif.ExifIFD.MakerNote: fuji_makernote(0, (1200, 900)),
                     piexif.ExifIFD.PixelXDimension: 4000, piexif.ExifIFD.PixelYDimension: 3000}}
    to_rgb_image(texture()).save(path, "JPEG", exif=piexif.dump(exif))
    hints = read_hints(path)
    assert (hints.focal, hints.aperture) == (35.0, 2.8)
    assert hints.af_point == pytest.approx((0.3, 0.3))
