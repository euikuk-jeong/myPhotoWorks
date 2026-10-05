"""Explainability, item 1 — ZoomPanView draws the overlay boxes on the photo.

``set_overlay(boxes)`` takes ``OverlayBox`` es (rect in shares of the frame). ``overlay_rects()``
returns ``(box, QRectF in widget pixels)`` for what is drawn right now: it follows zoom and pan,
and is empty while the overlay is hidden, no image is shown, or there are no boxes.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PyQt6.QtCore import QPointF  # noqa: E402
from PyQt6.QtGui import QColor, QPixmap  # noqa: E402

from myphotoworks.ui.zoom_view import HINT_H, ZoomPanView  # noqa: E402


def _box(rect=(0.25, 0.5, 0.75, 1.0), label="얼굴", source="face"):
    from myphotoworks.core.explain import OverlayBox

    return OverlayBox(label, rect, source)


def _xywh(r):
    return (r.x(), r.y(), r.width(), r.height())


@pytest.fixture
def view(qtbot):
    v = ZoomPanView()
    qtbot.addWidget(v)
    v.resize(400, 300 + HINT_H)
    v.show()
    pm = QPixmap(200, 100)            # 2:1, fitted to 400 x 200 at y = 50 (zoom 2.0)
    pm.fill(QColor(120, 120, 120))
    v.set_image("a", pm)
    return v


def test_overlay_is_on_by_default_and_empty_without_boxes(view):
    assert view.overlay_visible is True
    assert view.overlay_rects() == []


def test_box_maps_onto_the_fitted_image(view):
    b = _box()
    view.set_overlay([b])
    ((box, rect),) = view.overlay_rects()
    assert box is b
    assert _xywh(rect) == pytest.approx((100, 150, 200, 100))


def test_box_keeps_its_place_on_the_photo_when_zoomed_and_panned(view):
    view.set_overlay([_box()])
    view._zoom = view.fit_zoom() * 3          # the state the mouse wheel and drag leave behind
    view._offset = view._clamp_offset(QPointF(-40, 15))
    view.update()
    img = view._image_rect()
    ((_, r),) = view.overlay_rects()
    assert (r.left() - img.left()) / img.width() == pytest.approx(0.25)
    assert (r.right() - img.left()) / img.width() == pytest.approx(0.75)
    assert (r.top() - img.top()) / img.height() == pytest.approx(0.5)
    assert (r.bottom() - img.top()) / img.height() == pytest.approx(1.0)


def test_hidden_overlay_has_no_rects_and_comes_back(view):
    view.set_overlay([_box()])
    view.set_overlay_visible(False)
    assert view.overlay_visible is False and view.overlay_rects() == []
    view.set_overlay_visible(True)
    assert len(view.overlay_rects()) == 1


def test_setting_no_boxes_removes_them(view):
    view.set_overlay([_box()])
    view.set_overlay([])
    assert view.overlay_rects() == []


def test_clear_removes_the_overlay(view):
    view.set_overlay([_box()])
    view.clear()
    assert view.overlay_rects() == []


def test_overlay_is_painted_on_the_photo(view):
    view.set_overlay([_box()])
    ((_, r),) = view.overlay_rects()
    with_box = view.grab().toImage()
    view.set_overlay_visible(False)
    without = view.grab().toImage()
    x, y = int(r.left()), int(r.center().y())
    assert any(with_box.pixel(x + d, y) != without.pixel(x + d, y) for d in (-1, 0, 1))


def test_a_different_image_drops_the_old_boxes_but_a_refresh_keeps_them(view):
    view.set_overlay([_box()])
    pm = QPixmap(200, 100)
    pm.fill(QColor(90, 90, 90))
    view.set_image("a", pm)                   # same photo refreshed (e.g. adoption changed)
    assert len(view.overlay_rects()) == 1
    view.set_image("b", pm)                   # another photo: its boxes are not these
    assert view.overlay_rects() == []


# ---- colour and line style follow the source of the area ------------------------------------

def test_each_source_has_its_own_colour():
    from myphotoworks.ui.zoom_view import overlay_pen

    colours = {s: overlay_pen(s).color().name() for s in ("face", "af", "sharpest", "center")}
    assert len(set(colours.values())) == 4


def test_only_the_centre_fallback_is_dashed():
    from PyQt6.QtCore import Qt

    from myphotoworks.ui.zoom_view import overlay_pen

    assert overlay_pen("center").style() == Qt.PenStyle.DashLine
    for source in ("face", "af", "sharpest", "something-new"):
        assert overlay_pen(source).style() == Qt.PenStyle.SolidLine


def test_unknown_source_still_gets_a_visible_pen():
    from myphotoworks.ui.zoom_view import overlay_pen

    pen = overlay_pen("something-new")
    assert pen.color().alpha() > 0 and pen.widthF() >= 2.0


def test_a_box_without_label_is_drawn_without_text(view):
    view.set_overlay([_box(label="")])
    view.grab()                               # must not fail on the empty label
    assert len(view.overlay_rects()) == 1
