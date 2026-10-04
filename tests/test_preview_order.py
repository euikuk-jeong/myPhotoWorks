"""Preview walks the photos in file-name order, not in the grouped / filtered display order."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path  # noqa: E402

import pytest  # noqa: E402

from myphotoworks.models.photo_item import PhotoItem  # noqa: E402


def photos(*names: str) -> list[PhotoItem]:
    return [PhotoItem(source_path=Path(n)) for n in names]


def names(items: list[PhotoItem]) -> list[str]:
    return [p.source_path.name for p in items]


def test_preview_order_sorts_by_file_name():
    from myphotoworks.ui.main_window import preview_order

    shown = photos("C.jpg", "A.jpg", "B.jpg")
    assert names(preview_order(shown)) == ["A.jpg", "B.jpg", "C.jpg"]


def test_preview_order_uses_natural_number_order():
    from myphotoworks.ui.main_window import preview_order

    shown = photos("IMG_10.jpg", "IMG_2.jpg", "IMG_1.jpg")
    assert names(preview_order(shown)) == ["IMG_1.jpg", "IMG_2.jpg", "IMG_10.jpg"]


def test_preview_order_ignores_case():
    from myphotoworks.ui.main_window import preview_order

    shown = photos("b.JPG", "A.jpg", "c.jpg")
    assert names(preview_order(shown)) == ["A.jpg", "b.JPG", "c.jpg"]


def test_preview_order_same_name_in_two_folders_is_stable_by_folder():
    from myphotoworks.ui.main_window import preview_order

    shown = [PhotoItem(Path("b/IMG_1.jpg")), PhotoItem(Path("a/IMG_1.jpg"))]
    assert [str(p.source_path) for p in preview_order(shown)] == [
        str(Path("a/IMG_1.jpg")), str(Path("b/IMG_1.jpg"))
    ]


def test_preview_order_returns_same_items_and_leaves_input_alone():
    from myphotoworks.ui.main_window import preview_order

    shown = photos("B.jpg", "A.jpg")
    before = list(shown)
    result = preview_order(shown)
    assert shown == before                      # input order untouched
    assert {id(p) for p in result} == {id(p) for p in shown}


@pytest.fixture
def window(qtbot, monkeypatch):
    import myphotoworks.ui.main_window as mw

    monkeypatch.setattr(mw, "load_config", lambda: {})
    monkeypatch.setattr(mw, "save_config", lambda cfg: None)
    win = mw.MainWindow()
    qtbot.addWidget(win)
    return win


def scrambled_display(window, monkeypatch, shown: list[PhotoItem]) -> list:
    """Make the thumbnail panel report ``shown`` and record what preview is opened with."""
    opened: list = []
    monkeypatch.setattr(window._thumb_panel, "photos", lambda: list(shown))
    monkeypatch.setattr(window, "_open_preview", lambda items, start: opened.append((items, start)))
    return opened


def test_preview_button_opens_in_file_name_order(window, monkeypatch):
    # grouped display: group 1 = C, A (A was moved in later), then a single B
    shown = photos("C.jpg", "A.jpg", "B.jpg")
    opened = scrambled_display(window, monkeypatch, shown)

    window._on_preview()

    items, start = opened[0]
    assert names(items) == ["A.jpg", "B.jpg", "C.jpg"]
    assert start == 0


def test_double_click_starts_at_the_clicked_photo_in_sorted_order(window, monkeypatch):
    shown = photos("C.jpg", "A.jpg", "B.jpg")
    opened = scrambled_display(window, monkeypatch, shown)

    window._on_photo_double_clicked(shown[0])          # C.jpg

    items, start = opened[0]
    assert names(items) == ["A.jpg", "B.jpg", "C.jpg"]
    assert items[start].source_path.name == "C.jpg"
