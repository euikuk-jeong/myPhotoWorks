import math
import os
import re
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

from myphotoworks.core.grouping import (  # noqa: E402
    EXIF_MISMATCH_PENALTY,
    REPRESENTATIVE_SLACK,
    TIME_RELAX,
    threshold_from_slider,
)
from myphotoworks.core.ranking import (  # noqa: E402
    COLOR_DEADBAND,
    COLOR_IGNORE_BELOW,
    EXPOSURE_DEADBAND,
    SENSITIVITY_CHOICES,
    SHARPNESS_DEADBAND,
    TIEBREAK_WEIGHTS,
    reason_label,
    recommend,
)
from myphotoworks.core.scoring import (  # noqa: E402
    BLUR_ABS,
    BLUR_REL,
    SHARP_GRAD_CEIL,
    SHARP_TOP_PERCENT,
    is_blurry,
)
from myphotoworks.models.settings import AppSettings  # noqa: E402
from myphotoworks.ui import group_tab as group_tab_module  # noqa: E402
from myphotoworks.ui import guide  # noqa: E402
from tests.synthetic import scores  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
GUIDE_DIR = ROOT / "guide"


@pytest.fixture(scope="module")
def html():
    return (GUIDE_DIR / guide.GUIDE_FILE).read_text(encoding="utf-8")


# ---- the published document (guide/ folder) -----------------------------------


def test_guide_lives_in_guide_folder_not_docs(html):
    assert (GUIDE_DIR / guide.GUIDE_FILE).is_file()
    assert not (ROOT / "docs").exists()
    assert html.startswith("<!doctype html>") and 'lang="ko"' in html


def test_guide_is_self_contained_and_static(html):
    assert not re.search(r'(?:src|href)\s*=\s*"(?:https?:)?//', html)   # nothing loaded online
    assert "<script" not in html


def test_guide_markup_is_balanced(html):
    for tag in ("div", "svg", "table", "details", "ul", "section"):
        assert html.count(f"<{tag}") == html.count(f"</{tag}>"), tag


def test_guide_index_redirects_to_the_guide():
    index = (GUIDE_DIR / "index.html").read_text(encoding="utf-8")
    assert f"url={guide.GUIDE_FILE}" in index and f'href="{guide.GUIDE_FILE}"' in index


def test_pages_workflow_publishes_only_the_guide_folder():
    wf = (ROOT / ".github" / "workflows" / "guide-pages.yml").read_text(encoding="utf-8")
    assert "path: guide" in wf and "actions/deploy-pages" in wf
    assert "pages: write" in wf and "id-token: write" in wf
    assert 'branches: [main]' in wf and '"guide/**"' in wf


def test_guide_covers_grouping_and_recommendation_topics(html):
    for topic in ("모양 지문", "색 분포", "기준선", "촬영 시각", "EXIF", "선명도", "노출", "색감",
                  "주제 영역", "불감대", "차이 미미", "민감도", "추천", "채택", "한계",
                  "예제 1", "예제 5"):
        assert topic in html, topic
    for gone in ("종합점수", "가중치"):          # the weighted-sum recommendation no longer exists
        assert gone not in html, gone
    assert html.count("<svg") >= 8                                      # infographics


def test_guide_numbers_match_the_real_algorithm(html):
    assert f"{threshold_from_slider(0):.2f}" in html and f"{threshold_from_slider(100):.2f}" in html
    assert f"{threshold_from_slider(50):.2f}" in html                    # default threshold
    assert f"{TIME_RELAX:.2f}" in html and f"{EXIF_MISMATCH_PENALTY:.2f}" in html
    assert f"{threshold_from_slider(50) - REPRESENTATIVE_SLACK:.2f}" in html


def test_guide_recommendation_constants_match_the_algorithm(html):
    assert f"{round(SHARPNESS_DEADBAND * 100)}%" in html
    assert f"<b>{round(EXPOSURE_DEADBAND)}점</b> 이내" in html
    assert f"{round(COLOR_DEADBAND)}점" in html and f"{round(COLOR_IGNORE_BELOW)}점 미만" in html
    ws, we, wc = (round(w * 100) for w in TIEBREAK_WEIGHTS)
    assert f"선명도 {ws} · 노출 {we} · 색감 {wc}" in html
    assert f"{round(BLUR_ABS)}점 미만" in html and f"{round(BLUR_REL * 100)}% 미만" in html
    for scale, name in SENSITIVITY_CHOICES:
        assert f"{name} (×{scale:.1f})" in html, name
    assert f"{round(SHARP_TOP_PERCENT)}%" in html and f"{round(SHARP_GRAD_CEIL)} 이상" in html


def test_guide_sharpness_table_matches_the_score_curve(html):
    for edge in (1, 10, 50, 150):
        score = round(100 * min(1.0, math.sqrt(edge / SHARP_GRAD_CEIL)))
        assert f"<td>{score}</td>" in html, edge


def test_guide_example_4_picks_the_scored_winner_by_exposure():
    group = [scores(84, 88, 76), scores(80, 62, 79), scores(48, 70, 74)]
    rec = recommend(group)
    assert (rec.index, rec.deciding_criterion, rec.tie) == (0, "subject_exposure", False)
    assert [is_blurry(s, group) for s in group] == [False, False, True]
    assert reason_label(rec, 3) == "주제 노출 우세"


def test_guide_example_5_matches_each_sensitivity_step():
    group = [scores(92, 55, 60), scores(84, 90, 60)]
    winners = {name: recommend(group, scale).index for scale, name in SENSITIVITY_CHOICES}
    assert winners == {"낮음": 1, "보통": 1, "높음": 0}


def test_guide_states_the_subject_estimation_limitation(html):
    assert "가장 선명한 영역”으로 추정" in html and "전체”를 기준" not in html


# ---- opening the link ---------------------------------------------------------


def test_guide_url_points_to_the_published_file():
    assert guide.GUIDE_URL.startswith("https://")
    assert guide.GUIDE_URL.endswith("/" + guide.GUIDE_FILE)
    assert "github.io/myPhotoWorks/" in guide.GUIDE_URL


def test_open_guide_opens_the_url_in_the_default_browser(monkeypatch):
    opened = []
    monkeypatch.setattr(guide.QDesktopServices, "openUrl", lambda url: opened.append(url) or True)
    assert guide.open_guide() is True
    assert opened[0].toString() == guide.GUIDE_URL


def test_open_guide_shows_the_address_when_browser_cannot_open(monkeypatch):
    shown = []
    monkeypatch.setattr(guide.QDesktopServices, "openUrl", lambda url: False)
    monkeypatch.setattr(guide.QMessageBox, "information", lambda *a, **k: shown.append(a[2]))
    assert guide.open_guide() is False
    assert guide.GUIDE_URL in shown[0]                                   # user can copy it


# ---- group tab button -----------------------------------------------------------


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
