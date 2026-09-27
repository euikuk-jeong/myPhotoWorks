"""Tests for ThumbnailPanel cards: loop geometry, checkbox hit area, image size cache."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image  # noqa: E402
from PyQt6.QtCore import QRect, QRectF  # noqa: E402

from myphotoworks.ui.thumbnail_panel import (  # noqa: E402
    CARD_PAD,
    THUMB_BOX,
    ThumbnailPanel,
    checkbox_rect,
    pick_loop_path,
)


def test_pick_loop_stays_within_card_padding():
    photo = QRectF(CARD_PAD + 1, CARD_PAD + 1, THUMB_BOX.width(), THUMB_BOX.height())
    bounds = pick_loop_path(photo).boundingRect()
    card = QRectF(0, 0, THUMB_BOX.width() + 2 * (CARD_PAD + 1), THUMB_BOX.height() + 2 * CARD_PAD)
    assert card.contains(bounds)
    assert bounds.contains(photo)          # the loop surrounds the photo


def test_checkbox_sits_in_photo_top_right_corner():
    photo = QRect(10, 20, 168, 112)
    box = checkbox_rect(photo)
    assert photo.contains(box)
    assert box.right() > photo.center().x() and box.top() < photo.center().y()


def _loaded_panel(qtbot, tmp_path, size=(600, 400)):
    p = tmp_path / "a.jpg"
    Image.new("RGB", size, (120, 140, 160)).save(p)
    panel = ThumbnailPanel()
    qtbot.addWidget(panel)
    panel.resize(600, 400)
    panel.show()
    panel.add_photos([p])
    qtbot.waitUntil(lambda: panel.image_size(panel.all_photos()[0]) is not None, timeout=5000)
    return panel


def test_load_box_scales_with_device_pixel_ratio(qtbot, monkeypatch):
    from PyQt6.QtCore import QSize

    panel = ThumbnailPanel()
    qtbot.addWidget(panel)
    monkeypatch.setattr(panel, "devicePixelRatioF", lambda: 1.5)
    assert panel._load_box() == QSize(252, 168)


def test_current_size_loaded_fires_for_selected_photo(qtbot, tmp_path):
    p = tmp_path / "a.jpg"
    Image.new("RGB", (900, 600)).save(p)
    panel = ThumbnailPanel()
    qtbot.addWidget(panel)
    panel.show()
    with qtbot.waitSignal(panel.current_size_loaded, timeout=5000) as sig:
        panel.add_photos([p])
        panel.setCurrentRow(0)
    assert sig.args[0] is panel.all_photos()[0]
    assert panel.image_size(sig.args[0]) == (900, 600)


def test_image_size_cached_from_loader(qtbot, tmp_path):
    panel = _loaded_panel(qtbot, tmp_path, size=(1200, 800))
    assert panel.image_size(panel.all_photos()[0]) == (1200, 800)


def test_portrait_photo_rect_is_narrower_and_centred(qtbot, tmp_path):
    panel = _loaded_panel(qtbot, tmp_path, size=(400, 600))
    index = panel.model().index(0, 0)
    item_rect = panel.visualRect(index)
    rect = panel.itemDelegate().photo_rect(item_rect, index)
    assert rect.height() == THUMB_BOX.height() and rect.width() < THUMB_BOX.width()
    assert abs(rect.center().x() - item_rect.center().x()) <= 1


def test_landscape_photo_in_square_box_is_pinned_to_top(qtbot, tmp_path):
    """Review strip uses a square icon box: the pixmap sits at the box top, not centred."""
    from PyQt6.QtCore import QSize

    panel = _loaded_panel(qtbot, tmp_path, size=(600, 400))
    panel.setIconSize(QSize(130, 130))
    index = panel.model().index(0, 0)
    item_rect = panel.visualRect(index)
    rect = panel.itemDelegate().photo_rect(item_rect, index)
    assert rect.top() == item_rect.top() + 1 + CARD_PAD
    assert rect.height() < 130


def test_clicking_checkbox_requests_adoption_toggle(qtbot, tmp_path):
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest

    from myphotoworks.models.group_session import GroupSession

    panel = _loaded_panel(qtbot, tmp_path)
    photo = panel.all_photos()[0]
    panel.set_session(GroupSession([photo], [[0]], (0.5, 0.3, 0.2)))
    index = panel.model().index(0, 0)
    box = checkbox_rect(panel.itemDelegate().photo_rect(panel.visualRect(index), index))
    with qtbot.waitSignal(panel.adoption_toggle_requested, timeout=1000) as sig:
        QTest.mouseClick(panel.viewport(), Qt.MouseButton.LeftButton, pos=box.center())
    assert sig.args == [photo, not photo.is_adopted]


def test_status_badge_maps_batch_states():
    from myphotoworks.models.photo_item import ProcessStatus
    from myphotoworks.ui.thumbnail_panel import status_badge

    assert status_badge(ProcessStatus.PENDING) is None
    assert status_badge(ProcessStatus.PROCESSING)[0] == "처리중"
    assert status_badge(ProcessStatus.DONE)[0] == "완료"
    assert status_badge(ProcessStatus.ERROR)[0] == "오류"


def test_update_status_keeps_file_name_on_card(qtbot, tmp_path):
    from myphotoworks.models.photo_item import ProcessStatus

    panel = _loaded_panel(qtbot, tmp_path)
    photo = panel.all_photos()[0]
    for status in (ProcessStatus.PROCESSING, ProcessStatus.DONE, ProcessStatus.ERROR):
        photo.status = status
        panel.update_status(photo)
        panel.grab()                      # paint the badge path once per state
        assert panel.item(0).text() == "a.jpg"
