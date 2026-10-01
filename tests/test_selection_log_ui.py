"""Recommendation v2, stage 3 — selection log in the UI (plan §6-3).

* ``GroupReviewWindow(session, settings, parent=None, log_dir=None)``: closing the window saves
  the review (``utils/selection_log.save_selection_log``) into ``log_dir`` (default: the real log
  folder) when ``settings.selection_log`` is on. Once per window, never on a session nobody
  reviewed, and a folder that cannot be written never breaks closing.
* ``GroupTab``: a check box ``_log_cb`` ("선택 기록 저장") bound to ``AppSettings.selection_log``.
"""
import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from myphotoworks.models.settings import AppSettings  # noqa: E402
from tests.synthetic import scores  # noqa: E402
from tests.test_grouping import scene  # noqa: E402


def _review(qtbot, tmp_path, log_dir, settings=None, sharp=(40, 70)):
    from myphotoworks.models.group_session import GroupSession
    from myphotoworks.models.photo_item import PhotoItem
    from myphotoworks.ui.group_review_window import GroupReviewWindow

    photos = []
    for i, sh in enumerate(sharp):
        p = tmp_path / f"s_{i}.jpg"
        scene(i).save(p, "JPEG")
        item = PhotoItem(p)
        item.scores = scores(sh)
        photos.append(item)
    session = GroupSession(photos, [list(range(len(photos)))], 1.0)
    win = GroupReviewWindow(session, settings or AppSettings(), log_dir=log_dir)
    qtbot.addWidget(win)
    win.show()
    qtbot.wait(30)
    return win, session, photos


def _logs(directory):
    return sorted(directory.glob("*.json")) if directory.is_dir() else []


def test_closing_the_review_window_saves_the_review(qtbot, tmp_path):
    log_dir = tmp_path / "logs"
    win, _, _ = _review(qtbot, tmp_path, log_dir)
    win.close()
    (path,) = _logs(log_dir)
    label = json.loads(path.read_text(encoding="utf-8"))
    assert label["schema"] == 1 and label["groups"][0]["reviewed"] is True
    assert label["groups"][0]["picked"] == ["s_1.jpg"]


def test_the_log_holds_the_users_adoption_at_the_time_of_closing(qtbot, tmp_path):
    log_dir = tmp_path / "logs"
    win, session, photos = _review(qtbot, tmp_path, log_dir)
    session.set_adopted(photos[0], True)
    session.set_adopted(photos[1], False)
    win.close()
    group = json.loads(_logs(log_dir)[0].read_text(encoding="utf-8"))["groups"][0]
    assert group["picked"] == ["s_0.jpg"] and group["recommended"] == "s_1.jpg"
    assert group["edited"] is True


def test_nothing_is_saved_when_the_setting_is_off(qtbot, tmp_path):
    log_dir = tmp_path / "logs"
    win, _, _ = _review(qtbot, tmp_path, log_dir, AppSettings(selection_log=False))
    win.close()
    assert _logs(log_dir) == []


def test_closing_again_updates_the_same_log_instead_of_stacking_copies(qtbot, tmp_path):
    """Stage-3 refinement: every close saves (a failed write is retried at the next close), and
    the one file per session holds the latest state."""
    log_dir = tmp_path / "logs"
    win, session, photos = _review(qtbot, tmp_path, log_dir)
    win.close()
    (first,) = _logs(log_dir)
    session.set_adopted(photos[0], True)
    win.show()
    win.close()
    (second,) = _logs(log_dir)
    assert first == second
    assert json.loads(second.read_text(encoding="utf-8"))["groups"][0]["picked"] == [
        "s_0.jpg", "s_1.jpg"]


def test_a_second_review_window_of_the_same_session_updates_the_same_log(qtbot, tmp_path):
    from myphotoworks.ui.group_review_window import GroupReviewWindow

    log_dir = tmp_path / "logs"
    win, session, photos = _review(qtbot, tmp_path, log_dir)
    win.close()
    session.set_adopted(photos[1], False)
    again = GroupReviewWindow(session, AppSettings(), log_dir=log_dir)
    qtbot.addWidget(again)
    again.close()
    (only,) = _logs(log_dir)
    assert json.loads(only.read_text(encoding="utf-8"))["groups"][0]["picked"] == []


def test_an_unwritable_log_folder_does_not_break_closing(qtbot, tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    win, _, _ = _review(qtbot, tmp_path, blocker / "logs")
    win.close()
    assert not win.isVisible()


# ---- group tab ------------------------------------------------------------------------------


def test_group_tab_has_a_selection_log_check_box(qtbot):
    from myphotoworks.ui.group_tab import GroupTab

    tab = GroupTab(AppSettings(selection_log=False))
    qtbot.addWidget(tab)
    assert "선택 기록" in tab._log_cb.text() and not tab._log_cb.isChecked()
    tab.set_settings(AppSettings(selection_log=True))
    assert tab._log_cb.isChecked()


def test_toggling_the_check_box_updates_the_settings_and_signals_a_change(qtbot):
    from myphotoworks.ui.group_tab import GroupTab

    settings = AppSettings()
    tab = GroupTab(settings)
    qtbot.addWidget(tab)
    with qtbot.waitSignal(tab.changed, timeout=500):
        tab._log_cb.click()
    assert settings.selection_log is False
    tab._log_cb.click()
    assert settings.selection_log is True
