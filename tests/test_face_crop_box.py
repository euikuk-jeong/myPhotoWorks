"""Stage-3 refinement — the landmarker is told where the detected face is (code review of PR #44).

A face near the frame edge has a clamped crop, so it is not at the crop centre and a neighbour in
the margin can be nearer to the centre than the face itself. Now:

    analysis_image.face_crops(path, boxes, analysis_size) -> list[FaceCrop]
        ``FaceCrop(image, face_box)``: the crop (as ``load_face_crops``) and the detected face's
        box in the pixels of that image (after clamping and shrinking); ``load_face_crops`` stays
        the images only.
    FaceEngine.blendshapes(rgb, face_box=None)
        ``face_box`` = where the detected face is inside ``rgb``; ``None`` = the crop centre.
    MediaPipeFaceEngine._nearest_to_centre(result, target=(0.5, 0.5))   index of the landmarker
        face whose landmarks are closest to ``target`` (shares of the crop)
    MediaPipeFaceEngine._face_target(face_box, shape) -> (x, y)         the box centre as shares
        of an image of ``shape`` = (height, width)
"""
from types import SimpleNamespace as NS

import numpy as np
import pytest
from PIL import Image

from tests.synthetic import FACE, FakeFaceEngine, blend, texture


def _marked(tmp_path, face):
    """4x original: red face rectangle on blue; ``face`` is in the 512 x 384 analysis grid."""
    arr = np.zeros((1536, 2048, 3), dtype="uint8")
    arr[..., 2] = 255
    x0, y0, x1, y1 = (4 * v for v in face)
    arr[y0:y1, x0:x1] = (255, 0, 0)
    path = tmp_path / "marked.png"
    Image.fromarray(arr).save(path)
    return path


def _is_red(px):
    return px[0] > 180 and px[2] < 80


def _is_blue(px):
    return px[2] > 180 and px[0] < 80


# ---- face_crops -----------------------------------------------------------------------------


def test_face_crops_return_the_crop_and_the_face_box_inside_it(tmp_path):
    from myphotoworks.core.analysis_image import face_crops

    (crop,) = face_crops(_marked(tmp_path, FACE), [FACE], (512, 384))
    x0, y0, x1, y1 = crop.face_box
    img = crop.image
    assert 0 <= x0 < x1 <= img.width and 0 <= y0 < y1 <= img.height
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    assert _is_red(img.getpixel((cx, cy)))                           # the box is on the face ...
    assert _is_red(img.getpixel((x0 + 3, y0 + 3))) and _is_red(img.getpixel((x1 - 4, y1 - 4)))
    assert _is_blue(img.getpixel((max(0, x0 - 4), cy)))              # ... and tight around it
    assert _is_blue(img.getpixel((min(img.width - 1, x1 + 4), cy)))


def test_a_face_in_the_middle_of_the_frame_sits_in_the_middle_of_its_crop(tmp_path):
    from myphotoworks.core.analysis_image import face_crops

    (crop,) = face_crops(_marked(tmp_path, FACE), [FACE], (512, 384))
    x0, y0, x1, y1 = crop.face_box
    assert abs((x0 + x1) / 2 - crop.image.width / 2) <= 3
    assert abs((y0 + y1) / 2 - crop.image.height / 2) <= 3


def test_a_face_at_the_frame_edge_is_off_centre_in_its_clamped_crop(tmp_path):
    from myphotoworks.core.analysis_image import face_crops

    edge = (0, 100, 120, 220)                                      # touching the left border
    (crop,) = face_crops(_marked(tmp_path, edge), [edge], (512, 384))
    x0, _y0, x1, _y1 = crop.face_box
    assert x0 <= 2                                                 # starts at the crop's edge
    assert (x0 + x1) / 2 < crop.image.width * 0.45                 # clearly left of the centre
    assert _is_red(crop.image.getpixel(((x0 + x1) // 2, crop.image.height // 2)))


def test_every_face_of_a_group_gets_its_own_box(tmp_path):
    from myphotoworks.core.analysis_image import face_crops

    a, b = (60, 60, 160, 160), (300, 200, 400, 300)
    arr = np.zeros((1536, 2048, 3), dtype="uint8")
    arr[..., 2] = 255
    for x0, y0, x1, y1 in (a, b):
        arr[4 * y0:4 * y1, 4 * x0:4 * x1] = (255, 0, 0)
    path = tmp_path / "two.png"
    Image.fromarray(arr).save(path)
    crops = face_crops(path, [a, b], (512, 384))
    assert len(crops) == 2
    for crop in crops:
        x0, y0, x1, y1 = crop.face_box
        assert _is_red(crop.image.getpixel(((x0 + x1) // 2, (y0 + y1) // 2)))


def test_load_face_crops_still_returns_the_images_only(tmp_path):
    from myphotoworks.core.analysis_image import face_crops, load_face_crops

    path = _marked(tmp_path, FACE)
    images = load_face_crops(path, [FACE], (512, 384))
    assert isinstance(images[0], Image.Image)
    assert images[0].size == face_crops(path, [FACE], (512, 384))[0].image.size


def test_no_faces_give_no_crops(tmp_path):
    from myphotoworks.core.analysis_image import face_crops

    assert face_crops(tmp_path / "missing.jpg", [], (512, 384)) == []


# ---- the pipeline hands the box to the engine -----------------------------------------------


def test_the_pipeline_tells_the_engine_where_each_face_is(tmp_path):
    from datetime import datetime

    from myphotoworks.core.pipeline import analyze_photo

    path = tmp_path / "big.jpg"
    Image.fromarray(texture(1536, 2048, cell=16).astype("uint8")).convert("RGB").save(path, "JPEG")
    left, mid = (0, 100, 120, 220), FACE
    engine = FakeFaceEngine(boxes=[left, mid], shapes=[blend(), blend()])
    analyze_photo(path, datetime(2026, 1, 1), face_engine=engine)
    assert len(engine.face_boxes) == 2 and all(b is not None for b in engine.face_boxes)
    for (w, h), (x0, y0, x1, y1) in zip(engine.crop_sizes, engine.face_boxes, strict=True):
        assert 0 <= x0 < x1 <= w and 0 <= y0 < y1 <= h
    edge_box, mid_box = engine.face_boxes
    assert edge_box[0] <= 2 < mid_box[0]                   # the edge face starts at the crop edge


# ---- choosing the landmarker face -----------------------------------------------------------


def _face(cx, cy):
    return [NS(x=cx - 0.05, y=cy), NS(x=cx + 0.05, y=cy)]


def _result(*centres):
    return NS(face_blendshapes=[[] for _ in centres], face_landmarks=[_face(*c) for c in centres])


def test_the_landmarker_face_nearest_to_the_given_target_is_chosen():
    from myphotoworks.core.faces import MediaPipeFaceEngine

    pick = MediaPipeFaceEngine._nearest_to_centre
    result = _result((0.2, 0.5), (0.7, 0.5))
    assert pick(result) == 1                                    # default target: the crop centre
    assert pick(result, (0.2, 0.5)) == 0                        # the detected face is at the left
    assert pick(result, target=(0.75, 0.5)) == 1


def test_the_target_is_the_centre_of_the_face_box_as_shares_of_the_crop():
    from myphotoworks.core.faces import MediaPipeFaceEngine

    target = MediaPipeFaceEngine._face_target
    assert target((10, 20, 50, 60), (100, 200)) == pytest.approx((0.15, 0.4))
    assert target(None, (100, 200)) == (0.5, 0.5)
