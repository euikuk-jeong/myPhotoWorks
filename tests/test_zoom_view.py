import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PyQt6.QtCore import QEvent, QPoint, QPointF, Qt  # noqa: E402
from PyQt6.QtGui import QColor, QMouseEvent, QPixmap, QWheelEvent  # noqa: E402

from myphotoworks.ui.zoom_view import MAX_ZOOM, ZoomPanView  # noqa: E402


def pixmap(w=1000, h=500):
    pm = QPixmap(w, h)
    pm.fill(QColor("#336699"))
    return pm


def wheel(view, x, y, delta=120):
    ev = QWheelEvent(
        QPointF(x, y), QPointF(x, y), QPoint(0, 0), QPoint(0, delta),
        Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase, False,
    )
    view.wheelEvent(ev)


def mouse(view, kind, x, y, button=Qt.MouseButton.LeftButton, buttons=None):
    ev = QMouseEvent(
        kind, QPointF(x, y), QPointF(x, y), button,
        buttons if buttons is not None else button, Qt.KeyboardModifier.NoModifier,
    )
    {QEvent.Type.MouseButtonPress: view.mousePressEvent,
     QEvent.Type.MouseMove: view.mouseMoveEvent,
     QEvent.Type.MouseButtonRelease: view.mouseReleaseEvent}[kind](ev)


@pytest.fixture
def view(qtbot):
    v = ZoomPanView()
    qtbot.addWidget(v)
    v.resize(500, 400)
    v.show()
    v.set_image("a", pixmap())
    return v


def test_starts_fitted_and_centred(view):
    assert view.zoom == pytest.approx(view.fit_zoom())
    assert view.relative_zoom() == pytest.approx(1.0)
    assert view.offset == QPointF(0, 0)
    assert view.fit_zoom() == pytest.approx(0.5)      # 1000px wide image in 500px view


def test_wheel_up_zooms_in_wheel_down_zooms_out_but_not_below_fit(view):
    wheel(view, 250, 200, 120)
    assert view.relative_zoom() > 1.0
    zoomed = view.zoom
    wheel(view, 250, 200, -120)
    assert view.zoom < zoomed
    for _ in range(30):
        wheel(view, 250, 200, -120)
    assert view.zoom == pytest.approx(view.fit_zoom())      # floor = fit
    assert view.offset == QPointF(0, 0)


def test_zoom_has_upper_limit(view):
    for _ in range(100):
        wheel(view, 250, 200, 120)
    assert view.zoom == pytest.approx(MAX_ZOOM)


def test_small_image_stays_centred_on_the_short_axis(view):
    wheel(view, 400, 60, 120)            # 1.15x: 575x287 px still shorter than the 400px view
    assert view._image_rect().center().y() == pytest.approx(view.height() / 2.0)


def test_zoom_keeps_point_under_cursor_fixed(view):
    for _ in range(6):                      # image now larger than the view in both axes
        wheel(view, 250, 200, 120)
    mx, my = 400.0, 120.0

    def image_point():
        rect = view._image_rect()
        return ((mx - rect.x()) / view.zoom, (my - rect.y()) / view.zoom)

    before = image_point()
    wheel(view, mx, my, 120)
    wheel(view, mx, my, 120)
    after = image_point()
    assert after[0] == pytest.approx(before[0], abs=0.5)
    assert after[1] == pytest.approx(before[1], abs=0.5)


def test_drag_pans_when_zoomed(view):
    for _ in range(6):
        wheel(view, 250, 200, 120)
    start = view.offset
    mouse(view, QEvent.Type.MouseButtonPress, 250, 200)
    mouse(view, QEvent.Type.MouseMove, 220, 185, buttons=Qt.MouseButton.LeftButton)
    mouse(view, QEvent.Type.MouseButtonRelease, 220, 185)
    moved = view.offset
    assert moved.x() == pytest.approx(start.x() - 30)
    assert moved.y() == pytest.approx(start.y() - 15)


def test_drag_does_nothing_at_fit_and_is_clamped_when_zoomed(view):
    mouse(view, QEvent.Type.MouseButtonPress, 250, 200)
    mouse(view, QEvent.Type.MouseMove, 100, 100, buttons=Qt.MouseButton.LeftButton)
    mouse(view, QEvent.Type.MouseButtonRelease, 100, 100)
    assert view.offset == QPointF(0, 0)            # fitted image cannot be dragged away
    for _ in range(6):
        wheel(view, 250, 200, 120)
    mouse(view, QEvent.Type.MouseButtonPress, 250, 200)
    mouse(view, QEvent.Type.MouseMove, 250 - 5000, 200 - 5000, buttons=Qt.MouseButton.LeftButton)
    mouse(view, QEvent.Type.MouseButtonRelease, 0, 0)
    rect = view._image_rect()
    assert rect.right() == pytest.approx(view.width())      # right edge stops at the border
    assert rect.bottom() == pytest.approx(view.height())


def test_middle_click_resets_zoom_and_position(view):
    for _ in range(6):
        wheel(view, 400, 100, 120)
    mouse(view, QEvent.Type.MouseButtonPress, 250, 200)
    mouse(view, QEvent.Type.MouseMove, 200, 150, buttons=Qt.MouseButton.LeftButton)
    mouse(view, QEvent.Type.MouseButtonRelease, 200, 150)
    assert view.relative_zoom() > 1.0 and view.offset != QPointF(0, 0)
    mouse(view, QEvent.Type.MouseButtonPress, 10, 10, button=Qt.MouseButton.MiddleButton)
    mouse(view, QEvent.Type.MouseButtonRelease, 10, 10, button=Qt.MouseButton.MiddleButton)
    assert view.relative_zoom() == pytest.approx(1.0)
    assert view.offset == QPointF(0, 0)


def test_same_key_keeps_view_new_key_resets(view):
    for _ in range(4):
        wheel(view, 300, 150, 120)
    zoom, offset = view.zoom, view.offset
    view.set_image("a", pixmap())                   # e.g. refresh after toggling adoption
    assert view.zoom == pytest.approx(zoom) and view.offset == offset
    view.set_image("b", pixmap(800, 600))           # another photo
    assert view.relative_zoom() == pytest.approx(1.0)
    assert view.offset == QPointF(0, 0)


def test_detail_requested_once_on_first_zoom_in(view, qtbot):
    keys = []
    view.detail_requested.connect(keys.append)
    wheel(view, 250, 200, -120)                     # zoom out at fit: nothing
    assert keys == []
    wheel(view, 250, 200, 120)
    wheel(view, 250, 200, 120)
    wheel(view, 250, 200, 120)
    assert keys == ["a"]
    view.set_detail("a", pixmap(4000, 2000))         # sharper pixmap, same logical size
    assert view.zoom == pytest.approx(view._zoom) and view._logical_w == 1000.0
    wheel(view, 250, 200, 120)
    assert keys == ["a"]                             # not asked again


def test_detail_for_another_image_is_ignored(view):
    view.set_detail("other", pixmap(4000, 2000))
    assert not view._has_detail


def test_detail_does_not_move_the_view(view):
    for _ in range(5):
        wheel(view, 300, 150, 120)
    zoom, offset = view.zoom, view.offset
    view.set_detail("a", pixmap(4000, 2000))
    assert view.zoom == zoom and view.offset == offset


def test_resize_refits_until_user_zooms(qtbot):
    v = ZoomPanView()
    qtbot.addWidget(v)
    v.resize(500, 400)
    v.show()
    v.set_image("a", pixmap())
    v.resize(800, 600)
    assert v.relative_zoom() == pytest.approx(1.0)
    assert v.zoom == pytest.approx(v.fit_zoom())
    for _ in range(5):
        wheel(v, 400, 300, 120)
    z = v.relative_zoom()
    v.resize(700, 500)
    assert v.relative_zoom() >= 1.0 and z > 1.0      # stays zoomed in after resize


def test_null_pixmap_shows_message_and_ignores_input(qtbot):
    v = ZoomPanView()
    qtbot.addWidget(v)
    v.resize(400, 300)
    v.show()
    v.set_image("x", None, "불러올 수 없음")
    wheel(v, 100, 100, 120)
    mouse(v, QEvent.Type.MouseButtonPress, 10, 10)
    assert v.zoom == 1.0
    v.grab()                                         # paint path with a message must not raise
    v.clear()
    v.grab()
