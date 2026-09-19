import os
import re

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

from myphotoworks.core.grouping import (  # noqa: E402
    EXIF_MISMATCH_PENALTY,
    REPRESENTATIVE_SLACK,
    TIME_RELAX,
    threshold_from_slider,
)
from myphotoworks.core.scoring import QualityScores, composite  # noqa: E402
from myphotoworks.models.settings import AppSettings  # noqa: E402
from myphotoworks.ui import group_tab as group_tab_module  # noqa: E402
from myphotoworks.ui import guide  # noqa: E402


@pytest.fixture(scope="module")
def html():
    return guide.guide_source_path().read_text(encoding="utf-8")


# ---- the bundled document ---------------------------------------------------


def test_guide_is_bundled_and_self_contained(html):
    assert guide.guide_source_path().is_file()
    assert html.startswith("<!doctype html>") and 'lang="ko"' in html
    assert not re.search(r'(?:src|href)\s*=\s*"(?:https?:)?//', html)   # nothing loaded online
    assert "<script" not in html                                        # static, no scripts


def test_guide_markup_is_balanced(html):
    for tag in ("div", "svg", "table", "details", "ul", "section"):
        assert html.count(f"<{tag}") == html.count(f"</{tag}>"), tag


def test_guide_covers_grouping_and_recommendation_topics(html):
    for topic in ("모양 지문", "색 분포", "기준선", "촬영 시각", "EXIF", "선명도", "노출", "색감",
                  "종합점수", "가중치", "추천", "채택", "한계", "예제 1", "예제 5"):
        assert topic in html, topic
    assert html.count("<svg") >= 8                                      # infographics


def test_guide_numbers_match_the_real_algorithm(html):
    assert f"{threshold_from_slider(0):.2f}" in html and f"{threshold_from_slider(100):.2f}" in html
    assert f"{threshold_from_slider(50):.2f}" in html                    # default threshold
    assert f"{TIME_RELAX:.2f}" in html and f"{EXIF_MISMATCH_PENALTY:.2f}" in html
    assert f"{threshold_from_slider(50) - REPRESENTATIVE_SLACK:.2f}" in html
    # example 4 / 5 arithmetic is computed with the real scoring code
    default = (0.5, 0.3, 0.2)
    assert f"{composite(QualityScores(84, 88, 76), default):.1f}" in html
    p1, p2 = QualityScores(90, 45, 60), QualityScores(70, 92, 65)
    assert f"{composite(p1, default):.1f}" in html and f"{composite(p2, default):.1f}" in html
    assert f"{composite(p1, (0.8, 0.1, 0.1)):.1f}" in html


def test_guide_states_the_whole_image_limitation(html):
    assert "전체”를 기준" in html or "전체”를 기준" in html


# ---- preparing / opening ----------------------------------------------------


def test_prepare_guide_copies_and_refreshes(tmp_path):
    src = tmp_path / "src.html"
    src.write_text("v1", encoding="utf-8")
    out = guide.prepare_guide(tmp_path / "dest", source=src)
    assert out.name == guide.GUIDE_NAME and out.read_text(encoding="utf-8") == "v1"
    src.write_text("v2", encoding="utf-8")                              # bundled guide updated
    assert guide.prepare_guide(tmp_path / "dest", source=src).read_text(encoding="utf-8") == "v2"


def test_prepare_guide_missing_source_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        guide.prepare_guide(tmp_path / "d", source=tmp_path / "nope.html")


def test_open_guide_opens_local_file_url(monkeypatch, tmp_path):
    opened = []
    monkeypatch.setattr(guide, "default_guide_dir", lambda: tmp_path / "g")
    monkeypatch.setattr(guide.QDesktopServices, "openUrl", lambda url: opened.append(url) or True)
    assert guide.open_guide() is True
    assert opened[0].isLocalFile()
    assert opened[0].toLocalFile().replace("\\", "/").endswith("g/algorithm_guide.html")
    assert (tmp_path / "g" / guide.GUIDE_NAME).is_file()


def test_open_guide_reports_when_browser_cannot_open(monkeypatch, tmp_path):
    shown = []
    monkeypatch.setattr(guide, "default_guide_dir", lambda: tmp_path / "g")
    monkeypatch.setattr(guide.QDesktopServices, "openUrl", lambda url: False)
    monkeypatch.setattr(guide.QMessageBox, "information", lambda *a, **k: shown.append(a[2]))
    assert guide.open_guide() is False
    assert "algorithm_guide.html" in shown[0]                            # tells where the file is


def test_open_guide_reports_missing_file(monkeypatch, tmp_path):
    shown = []
    monkeypatch.setattr(guide, "guide_source_path", lambda: tmp_path / "missing.html")
    monkeypatch.setattr(guide.QMessageBox, "warning", lambda *a, **k: shown.append(a[2]))
    assert guide.open_guide() is False and shown


# ---- group tab button -------------------------------------------------------


def test_group_tab_button_opens_the_guide(qtbot, monkeypatch):
    calls = []
    monkeypatch.setattr(group_tab_module, "open_guide", lambda parent=None: calls.append(parent))
    tab = group_tab_module.GroupTab(AppSettings())
    qtbot.addWidget(tab)
    assert "설명서" in tab._guide_btn.text()
    tab._guide_btn.click()
    assert calls == [tab]


def test_guide_button_stays_usable_while_grouping_runs(qtbot):
    tab = group_tab_module.GroupTab(AppSettings())
    qtbot.addWidget(tab)
    tab.set_running(True)
    assert tab._guide_btn.isEnabled()
