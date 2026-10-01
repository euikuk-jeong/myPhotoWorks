"""Recommendation v2, stage 2 — second decode of a face from the original (plan Q10, §5-2).

New ``core/analysis_image.py`` API under test:

    FACE_CROP_MARGIN                                  share of the face size added on each side
    load_face_crop(path, box, analysis_size) -> RGB Image
        ``box`` is in the pixel grid of the analysis copy (``analysis_size`` = its (w, h));
        the crop comes from the original, so a face is much larger than in the 512 px copy.

The crop frame is the EXIF-rotated frame, exactly like ``load_analysis_image``.
"""
import numpy as np
import piexif
import pytest
from PIL import Image

from tests.synthetic import FACE, texture


def _big_png(tmp_path, w=2048, h=1536):
    path = tmp_path / "big.png"
    # smooth gradient: cheap to encode, shape is all the tests look at
    g = np.tile(np.linspace(0, 255, w), (h, 1))
    Image.fromarray(g.astype("uint8")).convert("RGB").save(path)
    return path


def test_the_crop_is_taken_from_the_original_at_higher_resolution_than_the_analysis_copy(tmp_path):
    from myphotoworks.core.analysis_image import load_face_crop

    path = tmp_path / "big.jpg"
    Image.fromarray(texture(1536, 2048, cell=16).astype("uint8")).convert("RGB").save(path, "JPEG")
    crop = load_face_crop(path, FACE, (512, 384))
    face_w = FACE[2] - FACE[0]
    assert crop.mode == "RGB"
    assert crop.width >= 1.5 * face_w and crop.height >= 1.5 * (FACE[3] - FACE[1])


def test_the_crop_adds_a_margin_around_the_face(tmp_path):
    """Scale-free check (an implementation may cap the crop size): the face is painted red on a
    blue original; in the crop it must span ``1 / (1 + 2 * margin)`` of the width."""
    from myphotoworks.core.analysis_image import FACE_CROP_MARGIN, load_face_crop

    arr = np.zeros((1536, 2048, 3), dtype="uint8")
    arr[..., 2] = 255                                                  # blue background
    x0, y0, x1, y1 = (4 * v for v in FACE)                             # original = 4x the copy
    arr[y0:y1, x0:x1] = (255, 0, 0)                                    # red face
    path = tmp_path / "marked.png"
    Image.fromarray(arr).save(path)

    crop = np.asarray(load_face_crop(path, FACE, (512, 384)))
    row = crop[crop.shape[0] // 2]
    red_share = float(((row[:, 0] > 180) & (row[:, 2] < 80)).mean())
    assert red_share == pytest.approx(1 / (1 + 2 * FACE_CROP_MARGIN), abs=0.05)


def test_a_face_at_the_border_is_clamped_to_the_image(tmp_path):
    from myphotoworks.core.analysis_image import load_face_crop

    path = _big_png(tmp_path)
    for box in [(0, 0, 60, 60), (452, 324, 512, 384)]:           # top-left and bottom-right corner
        crop = load_face_crop(path, box, (512, 384))
        assert 0 < crop.width <= 2048 and 0 < crop.height <= 1536


def test_the_crop_uses_the_exif_rotated_frame(tmp_path):
    """400x200 file, left half red / right half blue, EXIF orientation 6 (shown rotated 90 deg
    clockwise): the displayed image is 200x400 with red on top and blue at the bottom."""
    from myphotoworks.core.analysis_image import load_face_crop

    img = Image.new("RGB", (400, 200), (255, 0, 0))
    img.paste((0, 0, 255), (200, 0, 400, 200))
    path = tmp_path / "rot.jpg"
    exif = piexif.dump({"0th": {piexif.ImageIFD.Orientation: 6}})
    img.save(path, "JPEG", quality=95, exif=exif)

    crop = load_face_crop(path, (0, 300, 200, 400), (200, 400))   # bottom of the displayed frame
    r, _g, b = crop.getpixel((crop.width // 2, crop.height // 2))
    assert b > 150 and r < 100
    crop = load_face_crop(path, (0, 0, 200, 100), (200, 400))     # top of the displayed frame
    r, _g, b = crop.getpixel((crop.width // 2, crop.height // 2))
    assert r > 150 and b < 100


def test_several_faces_are_cropped_from_one_decode_of_the_original(tmp_path, monkeypatch):
    from myphotoworks.core import analysis_image
    from myphotoworks.core.analysis_image import load_face_crop, load_face_crops

    path = tmp_path / "group.jpg"
    Image.fromarray(texture(1536, 2048, cell=16).astype("uint8")).convert("RGB").save(path, "JPEG")
    boxes = [FACE, (300, 60, 380, 140), (30, 250, 110, 330)]
    opened = []
    real_open = analysis_image.Image.open
    monkeypatch.setattr(analysis_image.Image, "open",
                        lambda *a, **k: opened.append(a) or real_open(*a, **k))
    crops = load_face_crops(path, boxes, (512, 384))
    assert len(opened) == 1 and len(crops) == 3
    assert all(c.mode == "RGB" and c.width > 0 and c.height > 0 for c in crops)
    single = load_face_crop(path, boxes[1], (512, 384))
    assert single.width >= 1.5 * 80 and crops[1].width >= 1.5 * 80       # still high resolution


def test_no_faces_need_no_decode(tmp_path):
    from myphotoworks.core.analysis_image import load_face_crops

    assert load_face_crops(tmp_path / "missing.jpg", [], (512, 384)) == []
