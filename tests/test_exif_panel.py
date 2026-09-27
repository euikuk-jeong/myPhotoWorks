"""Tests for the EXIF overlay: grouping, empty-value hiding, close signal."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image  # noqa: E402

from myphotoworks.ui.exif_panel import ExifPanel, exif_groups  # noqa: E402


def test_exif_groups_drop_empty_values_and_groups():
    exif = {"file_size": "1,024 bytes", "size": "600 x 400", "make": "", "model": "",
            "software": "", "iso": "400", "comment": ""}
    groups = dict(exif_groups(exif, index=2, total=10))
    assert list(groups) == ["파일", "촬영 설정"]          # 카메라·코멘트 are empty
    assert ("번호", "2 / 10") in groups["파일"]
    assert ("ISO", "400") in groups["촬영 설정"]


def test_exif_groups_without_index_omits_number():
    groups = dict(exif_groups({"file_size": "1 bytes"}))
    assert all(k != "번호" for k, _ in groups["파일"])


def test_panel_shows_file_name_and_emits_closed(qtbot, tmp_path):
    p = tmp_path / "shot.jpg"
    Image.new("RGB", (60, 40)).save(p)
    panel = ExifPanel()
    qtbot.addWidget(panel)
    panel.update_photo(p, index=1, total=3)
    panel.show()
    assert panel._file_label.text() == "shot.jpg"
    with qtbot.waitSignal(panel.closed, timeout=1000):
        panel.reject()
    assert not panel.isVisible()
