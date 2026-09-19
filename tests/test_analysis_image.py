import piexif
import pytest
from PIL import Image

from myphotoworks.core.analysis_image import load_analysis_image


def _save(path, size, fmt="JPEG", **kwargs):
    Image.new("RGB", size, (120, 80, 40)).save(path, fmt, **kwargs)
    return path


def test_downscales_to_long_side(tmp_path):
    p = _save(tmp_path / "a.jpg", (4000, 3000))
    img = load_analysis_image(p, 512)
    assert max(img.size) <= 512
    assert img.mode == "RGB"


def test_keeps_aspect_ratio(tmp_path):
    p = _save(tmp_path / "a.png", (2000, 1000), "PNG")
    img = load_analysis_image(p, 500)
    assert img.size == (500, 250)


def test_does_not_upscale(tmp_path):
    p = _save(tmp_path / "small.png", (100, 60), "PNG")
    assert load_analysis_image(p, 512).size == (100, 60)


def test_applies_exif_rotation(tmp_path):
    p = tmp_path / "rot.jpg"
    exif = piexif.dump({"0th": {piexif.ImageIFD.Orientation: 6}})
    Image.new("RGB", (400, 200), (10, 10, 10)).save(p, "JPEG", exif=exif)
    w, h = load_analysis_image(p, 512).size
    assert (w, h) == (200, 400)


def test_non_jpeg_and_rgba_converted(tmp_path):
    p = tmp_path / "a.png"
    Image.new("RGBA", (50, 50), (1, 2, 3, 4)).save(p)
    assert load_analysis_image(p).mode == "RGB"


def test_invalid_long_side(tmp_path):
    p = _save(tmp_path / "a.png", (10, 10), "PNG")
    with pytest.raises(ValueError):
        load_analysis_image(p, 0)


def test_corrupt_file_raises(tmp_path):
    p = tmp_path / "bad.jpg"
    p.write_bytes(b"not an image")
    with pytest.raises(OSError):
        load_analysis_image(p)


def test_core_has_no_pyqt():
    import pathlib

    import myphotoworks.core as core

    for f in pathlib.Path(core.__file__).parent.glob("*.py"):
        assert "PyQt6" not in f.read_text(encoding="utf-8")
