"""Face detection that finds small faces and drops false ones (``core/face_detect.py``).

Real photos (dev8 review, 2026-10-05) showed what the whole-frame BlazeFace short-range detector
gets wrong: it shrinks the frame to 128 px, so a face under about a tenth of the width is
invisible (children in a museum, a profile face), and its false positives (a display panel, a
shadow-play screen, a camera lens) score 0.52 - 0.67. Looking at overlapping tiles of a larger
decode shows small faces at 0.85 - 0.97 and leaves the false ones weak or gone.

``detect_faces(path, raw, engine) -> list[box in the pixels of raw]``

1. whole-frame detection on ``raw`` (the analysis copy); a detection counts from
   ``MIN_FACE_SCORE`` (0.7) and while its box is at most ``MAX_FACE_WIDTH_RATIO`` (0.45) of the
   frame wide (a face over half the frame is a pattern, not a face);
2. unless the whole frame found faces and every detection is kept and ``STRONG_FACE_SCORE``
   (0.8) or more (a weak or dropped one means "look closer"), the photo is decoded at
   ``TILE_LONG_SIDE`` (2048) and ``tile_rects`` (``TILE_FRACTION`` 0.5 of the frame,
   ``TILE_OVERLAP`` 0.5, so 9 tiles) are searched too; tile detections are mapped back and
   filtered the same way; a tile detection cut by an inner tile edge (``cut_by_tile_edge``) is
   half a face and is ignored: the overlapping neighbour tile has the whole face;
3. overlapping boxes are merged by ``nms`` (``NMS_IOU`` 0.3), the higher score wins.

An engine may offer ``detect_scored(rgb) -> [(box, score)]``; one with only ``detect`` gives
boxes that count as score 1.0 (no tiles). A tile decode that fails keeps the whole-frame result.
"""
import numpy as np
import pytest
from PIL import Image

from myphotoworks.core.analysis_image import load_analysis_image

WHOLE_W = 512            # width of the analysis copy of a landscape photo


class PatchEngine:
    """Sees a magenta patch as a face when it spans at least ``min_share`` of the image width,
    like a detector that cannot see small faces. Score ``score``; ``whole_score`` (if given)
    replaces the visibility rule for the whole frame (the 512 px copy). Records every call."""

    def __init__(self, min_share=0.15, score=0.9, whole_score=None):
        self.min_share, self.score, self.whole_score = min_share, score, whole_score
        self.calls = []

    def detect_scored(self, rgb):
        self.calls.append(rgb.shape)
        mask = (rgb[..., 0] > 200) & (rgb[..., 1] < 70) & (rgb[..., 2] > 200)
        ys, xs = np.where(mask)
        if xs.size == 0:
            return []
        box = (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)
        if rgb.shape[1] == WHOLE_W and self.whole_score is not None:
            return [(box, self.whole_score)]
        if (box[2] - box[0]) / rgb.shape[1] < self.min_share:
            return []
        return [(box, self.score)]

    def detect(self, rgb):
        return [b for b, _ in self.detect_scored(rgb)]

    def blendshapes(self, rgb, face_box=None):
        return None


def photo(tmp_path, patch=None, size=(2400, 1600)):
    """A grey JPEG with one magenta patch ``(x0, y0, x1, y1)`` in full-size pixels."""
    img = Image.new("RGB", size, (90, 90, 90))
    if patch:
        img.paste((255, 0, 255), patch)
    path = tmp_path / "p.jpg"
    img.save(path, "JPEG", quality=95)
    return path


def detect(path, engine):
    from myphotoworks.core.face_detect import detect_faces

    return detect_faces(path, load_analysis_image(path), engine)


def near(box, share_box, size=(512, 341), tol=0.03):
    """``box`` (pixels) is the share box ``(x0, y0, x1, y1)`` of the frame within ``tol``."""
    w, h = size
    got = (box[0] / w, box[1] / h, box[2] / w, box[3] / h)
    return all(abs(a - b) <= tol for a, b in zip(got, share_box, strict=True))


# ---- constants ---------------------------------------------------------------------------------

def test_the_tunables():
    from myphotoworks.core import face_detect as fd

    assert (fd.MIN_FACE_SCORE, fd.STRONG_FACE_SCORE) == (0.7, 0.8)
    assert fd.MAX_FACE_WIDTH_RATIO == 0.45
    assert (fd.TILE_FRACTION, fd.TILE_OVERLAP, fd.TILE_LONG_SIDE) == (0.5, 0.5, 2048)
    assert fd.NMS_IOU == 0.3


# ---- tiles and merging -------------------------------------------------------------------------

def test_tiles_are_a_three_by_three_grid_of_half_size_overlapping_tiles():
    from myphotoworks.core.face_detect import tile_rects

    rects = tile_rects((2000, 1000))
    assert len(rects) == 9
    assert rects[0] == (0, 0, 1000, 500) and rects[-1] == (1000, 500, 2000, 1000)
    assert sorted({r[0] for r in rects}) == [0, 500, 1000]
    assert sorted({r[1] for r in rects}) == [0, 250, 500]
    assert all((r[2] - r[0], r[3] - r[1]) == (1000, 500) for r in rects)


def test_tiles_cover_an_odd_sized_frame_to_its_edges():
    from myphotoworks.core.face_detect import tile_rects

    rects = tile_rects((2047, 1365))
    assert max(r[2] for r in rects) == 2047 and max(r[3] for r in rects) == 1365
    assert all(0 <= r[0] < r[2] <= 2047 and 0 <= r[1] < r[3] <= 1365 for r in rects)


def test_a_box_cut_by_an_inner_tile_edge_is_half_a_face():
    from myphotoworks.core.face_detect import cut_by_tile_edge

    frame, tile = (2048, 1365), (512, 341, 1536, 1024)          # a tile in the middle
    assert cut_by_tile_edge((700, 500, 900, 700), tile, frame) is False      # clear of the edges
    assert cut_by_tile_edge((1300, 500, 1536, 700), tile, frame) is True     # right edge
    assert cut_by_tile_edge((600, 341, 800, 500), tile, frame) is True       # top edge
    assert cut_by_tile_edge((512, 500, 700, 700), tile, frame) is True       # left edge
    assert cut_by_tile_edge((700, 900, 900, 1024), tile, frame) is True      # bottom edge


def test_a_box_at_the_edge_of_the_frame_is_not_cut():
    from myphotoworks.core.face_detect import cut_by_tile_edge

    frame, tile = (2048, 1365), (0, 0, 1024, 683)               # the top left tile
    assert cut_by_tile_edge((0, 0, 200, 200), tile, frame) is False          # frame edges
    assert cut_by_tile_edge((800, 100, 1024, 300), tile, frame) is True      # inner right edge


def test_iou():
    from myphotoworks.core.face_detect import box_iou

    assert box_iou((0, 0, 10, 10), (0, 0, 10, 10)) == pytest.approx(1.0)
    assert box_iou((0, 0, 10, 10), (20, 20, 30, 30)) == 0.0
    assert box_iou((0, 0, 10, 10), (5, 0, 15, 10)) == pytest.approx(1 / 3)


def test_nms_keeps_the_higher_score_of_overlapping_boxes_and_the_distant_ones():
    from myphotoworks.core.face_detect import nms

    kept = nms([((0, 0, 10, 10), 0.8), ((1, 1, 11, 11), 0.9), ((50, 50, 60, 60), 0.7)])
    assert kept == [((1, 1, 11, 11), 0.9), ((50, 50, 60, 60), 0.7)]


# ---- detect_faces ------------------------------------------------------------------------------

def test_a_small_face_is_found_in_a_tile(tmp_path):
    path = photo(tmp_path, patch=(800, 600, 1100, 900))       # 12.5 % of the width
    engine = PatchEngine()
    whole = engine.detect(np.asarray(load_analysis_image(path)))
    assert whole == []                                        # the whole frame misses it
    (box,) = detect(path, engine)
    assert near(box, (800 / 2400, 600 / 1600, 1100 / 2400, 900 / 1600))


def test_a_confident_whole_frame_face_needs_no_tiles(tmp_path):
    path = photo(tmp_path, patch=(800, 500, 1640, 1300))      # 35 % of the width
    engine = PatchEngine()
    (box,) = detect(path, engine)
    assert near(box, (800 / 2400, 500 / 1600, 1640 / 2400, 1300 / 1600))
    assert len(engine.calls) == 1


class TwoFaceEngine:
    """Magenta patch A and cyan patch B. Each is seen when it spans at least 15 % of the image
    width (score 0.9); on the 512 px frame B is reported at ``weak`` whatever its size (a weak
    detection, like a real second face of a group photo)."""

    def __init__(self, weak=0.56):
        self.weak, self.calls = weak, 0

    @staticmethod
    def _box(mask):
        ys, xs = np.where(mask)
        if xs.size == 0:
            return None
        return (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)

    def detect_scored(self, rgb):
        self.calls += 1
        a = self._box((rgb[..., 0] > 200) & (rgb[..., 1] < 70) & (rgb[..., 2] > 200))
        b = self._box((rgb[..., 0] < 70) & (rgb[..., 1] > 200) & (rgb[..., 2] > 200))
        found = []
        for box, weak in ((a, None), (b, self.weak)):
            if box is None:
                continue
            if rgb.shape[1] == WHOLE_W and weak is not None:
                found.append((box, weak))
            elif (box[2] - box[0]) / rgb.shape[1] >= 0.15:
                found.append((box, 0.9))
        return found

    def detect(self, rgb):
        return [b for b, _ in self.detect_scored(rgb)]

    def blendshapes(self, rgb, face_box=None):
        return None


def test_a_confident_face_next_to_a_weak_one_still_gets_the_tiles(tmp_path):
    """Group photo: the big face is certain, the second only 0.56 on the whole frame."""
    img = Image.new("RGB", (2400, 1600), (90, 90, 90))
    img.paste((255, 0, 255), (800, 500, 1640, 1000))          # A: 35 % of the width
    img.paste((0, 255, 255), (1800, 1100, 2100, 1400))        # B: 12.5 %
    path = tmp_path / "group.jpg"
    img.save(path, "JPEG", quality=95)
    boxes = detect(path, TwoFaceEngine())
    assert len(boxes) == 2
    assert any(near(b, (800 / 2400, 500 / 1600, 1640 / 2400, 1000 / 1600)) for b in boxes)
    assert any(near(b, (1800 / 2400, 1100 / 1600, 2100 / 2400, 1400 / 1600)) for b in boxes)


def test_a_face_box_wider_than_45_percent_of_the_frame_is_dropped(tmp_path):
    path = photo(tmp_path, patch=(500, 300, 1800, 1300))      # 54 % of the width: a pattern
    assert detect(path, PatchEngine()) == []


def test_a_whole_frame_detection_below_the_score_is_dropped(tmp_path):
    path = photo(tmp_path, patch=(800, 600, 1100, 900))
    engine = PatchEngine(min_share=2.0, whole_score=0.65)     # the tiles see nothing
    assert detect(path, engine) == []


def test_a_weak_whole_frame_box_and_a_strong_tile_box_of_one_face_become_one(tmp_path):
    path = photo(tmp_path, patch=(800, 600, 1100, 900))
    engine = PatchEngine(score=0.9, whole_score=0.75)
    (box,) = detect(path, engine)
    assert near(box, (800 / 2400, 600 / 1600, 1100 / 2400, 900 / 1600))
    assert len(engine.calls) == 10                            # the frame and nine tiles


def test_a_photo_without_faces_costs_one_frame_and_nine_tiles(tmp_path):
    path = photo(tmp_path)
    engine = PatchEngine()
    assert detect(path, engine) == []
    assert len(engine.calls) == 10
    tiles = engine.calls[1:]
    assert len({shape[:2] for shape in tiles}) == 1 and tiles[0][1] == 1024


def test_tile_boxes_are_mapped_back_to_the_frame_not_the_tile(tmp_path):
    path = photo(tmp_path, patch=(1800, 1100, 2100, 1400))    # lower right
    (box,) = detect(path, PatchEngine())
    assert near(box, (1800 / 2400, 1100 / 1600, 2100 / 2400, 1400 / 1600))


def test_a_failing_tile_decode_keeps_the_whole_frame_result(tmp_path):
    from myphotoworks.core.face_detect import detect_faces

    raw = Image.new("RGB", (WHOLE_W, 341), (90, 90, 90))
    raw.paste((255, 0, 255), (100, 80, 170, 150))
    engine = PatchEngine(whole_score=0.75)                    # weak: tiles would be tried
    boxes = detect_faces(tmp_path / "missing.jpg", raw, engine)
    assert len(boxes) == 1 and near(boxes[0], (100 / 512, 80 / 341, 170 / 512, 150 / 341))


def test_an_engine_with_only_detect_is_taken_as_confident(tmp_path):
    class Legacy:
        calls = 0

        def detect(self, rgb):
            Legacy.calls += 1
            return [(100, 80, 200, 180)]

    path = photo(tmp_path)
    assert detect(path, Legacy()) == [(100, 80, 200, 180)]
    assert Legacy.calls == 1


def test_boxes_are_clipped_to_the_frame(tmp_path):
    class Wide:
        def detect_scored(self, rgb):
            return [((-5, -4, 60, 70), 0.95)]

    (box,) = detect(photo(tmp_path), Wide())
    assert box == (0, 0, 60, 70)


# ---- the pipeline uses it ---------------------------------------------------------------------

def test_analyze_faces_finds_a_face_only_the_tiles_can_see(tmp_path):
    from myphotoworks.core.pipeline import analyze_faces

    path = photo(tmp_path, patch=(800, 600, 1100, 900))
    faces = analyze_faces(path, load_analysis_image(path), PatchEngine())
    assert len(faces) == 1
    assert near(faces[0][0], (800 / 2400, 600 / 1600, 1100 / 2400, 900 / 1600))


def test_analyze_faces_gives_no_faces_for_the_false_whole_frame_detection(tmp_path):
    from myphotoworks.core.pipeline import analyze_faces

    path = photo(tmp_path, patch=(500, 300, 1800, 1300))
    assert analyze_faces(path, load_analysis_image(path), PatchEngine()) == []


# ---- the MediaPipe adapter ---------------------------------------------------------------------

def test_the_mediapipe_adapter_returns_scores():
    from types import SimpleNamespace

    from myphotoworks.core.faces import MediaPipeFaceEngine

    def det(x, y, w, h, score):
        return SimpleNamespace(bounding_box=SimpleNamespace(origin_x=x, origin_y=y, width=w,
                                                            height=h),
                               categories=[SimpleNamespace(score=score)])

    class Detector:
        def detect(self, image):
            return SimpleNamespace(detections=[det(10, 20, 30, 40, 0.83), det(-5, 2, 20, 20, 0.6)])

    class Mp:
        class ImageFormat:
            SRGB = 1

        @staticmethod
        def Image(image_format, data):  # noqa: N802
            return data

    import threading

    engine = object.__new__(MediaPipeFaceEngine)
    engine._lock, engine._mp, engine._detector = threading.Lock(), Mp, Detector()
    rgb = np.zeros((100, 100, 3), np.uint8)
    assert engine.detect_scored(rgb) == [((10, 20, 40, 60), 0.83), ((0, 2, 15, 22), 0.6)]
    assert engine.detect(rgb) == [(10, 20, 40, 60), (0, 2, 15, 22)]
