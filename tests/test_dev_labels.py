import json

import pytest

from myphotoworks.dev.labels import DEV_ENV, is_dev_mode, write_labels
from myphotoworks.models.group_session import GroupSession
from myphotoworks.models.photo_item import PhotoItem
from myphotoworks.models.settings import AppSettings
from tests.synthetic import scores


@pytest.mark.parametrize("value,expected", [
    (None, False), ("", False), ("0", False), ("1", True), ("true", True), ("TRUE", True),
])
def test_is_dev_mode(monkeypatch, value, expected):  # B1
    if value is None:
        monkeypatch.delenv(DEV_ENV, raising=False)
    else:
        monkeypatch.setenv(DEV_ENV, value)
    assert is_dev_mode() is expected


def test_write_labels_roundtrip_with_korean_names(tmp_path):  # B2
    ps = []
    for name, sharp in (("가족_1.jpg", 90), ("가족_2.jpg", 40)):
        p = PhotoItem(tmp_path / name)
        p.scores = scores(sharp, 70, 60)
        ps.append(p)
    session = GroupSession(ps, [[0, 1]], 1.0)
    out = tmp_path / "labels.json"
    label = write_labels(session, out, root=tmp_path)
    assert json.loads(out.read_text(encoding="utf-8")) == label
    assert label["groups"][0]["files"] == ["가족_1.jpg", "가족_2.jpg"]


def test_group_tab_export_button_only_in_dev_mode(qtbot, monkeypatch):  # B3
    from myphotoworks.ui.group_tab import GroupTab

    monkeypatch.delenv(DEV_ENV, raising=False)
    tab = GroupTab(AppSettings())
    qtbot.addWidget(tab)
    assert tab._export_btn is None

    monkeypatch.setenv(DEV_ENV, "1")
    tab = GroupTab(AppSettings())
    qtbot.addWidget(tab)
    assert tab._export_btn is not None
    tab.set_has_photos(True)
    assert not tab._export_btn.isEnabled()
    tab.set_done(True)
    assert tab._export_btn.isEnabled()
    with qtbot.waitSignal(tab.export_labels_requested):
        tab._export_btn.click()
