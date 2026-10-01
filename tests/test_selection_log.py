"""Recommendation v2, stage 3 — selection log (plan §6-3): recommended vs adopted, kept locally.

New ``utils/selection_log.py`` API under test (no Qt):

    selection_log_dir() -> Path                      ~/.myphotoworks/selection_logs
    save_selection_log(session, directory=None, now=None) -> Path | None
        writes one schema-1 label file (``GroupSession.to_label_dict()`` plus ``logged_at``) per
        call; ``None`` and no file when nothing was reviewed or there is no group of two or more;
        never raises (an unwritable folder just means no log)
    load_selection_logs(directory=None) -> list[dict]   saved labels, oldest first; files that are
        not labels are skipped

Privacy (plan §6-3): only the label fields - relative file names and the user's choices - no pixel
data and no other keys. The label files are what ``dev/eval_metrics`` already reads, so a log
folder is evaluated like any exported label. ``AppSettings.selection_log`` (default on) switches
the logging off; it survives the config round trip.
"""
import json
from datetime import datetime
from pathlib import Path

import pytest

from myphotoworks.models.photo_item import PhotoItem
from tests.synthetic import scores

NOW = datetime(2026, 10, 2, 9, 30, 15)


def make(groups=((0, 1), (2, 3), (4,)), sensitivity=1.0):
    """a b | c d | e: scores make the second photo of each pair the recommendation."""
    from myphotoworks.models.group_session import GroupSession

    ps = []
    for i, name in enumerate("abcde"):
        p = PhotoItem(Path("/photos/day1") / f"{name}.jpg")
        p.scores = scores(40 + 30 * (i % 2))
        ps.append(p)
    return GroupSession(ps, [list(g) for g in groups], sensitivity), ps


def _save(session, directory, now=NOW):
    from myphotoworks.utils.selection_log import save_selection_log

    return save_selection_log(session, directory, now=now)


def _json_files(directory):
    return sorted(Path(directory).glob("*.json")) if Path(directory).is_dir() else []


# ---- location and content -------------------------------------------------------------------


def test_the_default_folder_is_inside_the_settings_directory():
    from myphotoworks.utils.selection_log import selection_log_dir

    assert selection_log_dir() == Path.home() / ".myphotoworks" / "selection_logs"


def test_a_reviewed_session_is_saved_as_a_schema_one_label(tmp_path):
    session, _ = make()
    session.mark_reviewed(0)
    path = _save(session, tmp_path)
    assert path is not None and path.parent == tmp_path and path.suffix == ".json"
    saved = json.loads(path.read_text(encoding="utf-8"))
    expected = session.to_label_dict()
    for key in ("schema", "source", "algorithm", "sensitivity", "root", "groups"):
        assert saved[key] == expected[key]
    assert saved["schema"] == 1 and saved["logged_at"].startswith("2026-10-02T09:30:15")


def test_only_label_fields_are_logged(tmp_path):
    session, _ = make()
    session.mark_reviewed(0)
    saved = json.loads(_save(session, tmp_path).read_text(encoding="utf-8"))
    assert set(saved) == {"schema", "source", "algorithm", "sensitivity", "root", "groups",
                          "logged_at", "session"}
    for group in saved["groups"]:
        assert set(group) == {"id", "files", "picked", "recommended", "reviewed", "edited"}
        assert all("/" not in name for name in group["files"])      # relative to the root only


def test_the_log_records_what_the_user_changed(tmp_path):
    session, ps = make()
    session.mark_reviewed(0)
    session.set_adopted(ps[0], True)                  # also adopt the photo that was not picked
    session.set_adopted(ps[1], False)                 # ... and drop the recommended one
    saved = json.loads(_save(session, tmp_path).read_text(encoding="utf-8"))
    first = saved["groups"][0]
    assert first["recommended"] == "b.jpg" and first["picked"] == ["a.jpg"]
    assert first["reviewed"] is True and first["edited"] is True


def test_the_saved_file_is_read_by_the_evaluation(tmp_path):
    from myphotoworks.dev.eval_metrics import evaluate, load_label

    session, ps = make()
    session.mark_reviewed(0)
    session.set_adopted(ps[0], True)
    session.set_adopted(ps[1], False)
    report = evaluate([load_label(_save(session, tmp_path))], "v2", score_fn=lambda p: scores())
    assert len(report.results) == 1


# ---- when nothing is written ----------------------------------------------------------------


def test_a_session_nobody_looked_at_writes_nothing(tmp_path):
    session, _ = make()
    assert _save(session, tmp_path) is None
    assert _json_files(tmp_path) == []


def test_a_session_without_groups_of_two_or_more_writes_nothing(tmp_path):
    session, _ = make(groups=((0,), (1,), (2,), (3,), (4,)))
    for gid in range(5):
        session.mark_reviewed(gid)
    assert _save(session, tmp_path) is None


def test_an_unwritable_folder_means_no_log_and_no_exception(tmp_path):
    blocker = tmp_path / "not_a_folder"
    blocker.write_text("x")
    session, _ = make()
    session.mark_reviewed(0)
    assert _save(session, blocker / "logs") is None


# ---- accumulating ---------------------------------------------------------------------------


def test_the_folder_is_created_on_demand(tmp_path):
    session, _ = make()
    session.mark_reviewed(0)
    target = tmp_path / "a" / "b" / "logs"
    assert _save(session, target).parent == target


def test_a_session_has_a_stable_unique_id():
    """Stage-3 refinement: ``GroupSession.session_id``, one per grouping run."""
    first, _ = make()
    second, _ = make()
    assert isinstance(first.session_id, str) and len(first.session_id) >= 8
    assert first.session_id == first.session_id != second.session_id


def test_editing_a_session_keeps_its_id():
    session, ps = make()
    before = session.session_id
    session.move_photo(ps[0], session.groups()[1].id)
    session.merge(session.groups()[0].id, session.groups()[-1].id)
    assert session.session_id == before


def test_the_log_records_the_session_id(tmp_path):
    session, _ = make()
    session.mark_reviewed(0)
    saved = json.loads(_save(session, tmp_path).read_text(encoding="utf-8"))
    assert saved["session"] == session.session_id


def test_saving_the_same_session_again_updates_its_one_file(tmp_path):
    """Stage-3 refinement: reopening and closing a review must not stack copies of the same
    decisions (the evaluation would count them twice)."""
    session, ps = make()
    session.mark_reviewed(0)
    first = _save(session, tmp_path, now=datetime(2026, 10, 2, 9, 0, 0))
    session.mark_reviewed(1)
    session.set_adopted(ps[2], True)
    second = _save(session, tmp_path, now=datetime(2026, 10, 2, 9, 5, 0))
    assert first == second and _json_files(tmp_path) == [first]
    saved = json.loads(first.read_text(encoding="utf-8"))
    assert saved["logged_at"].startswith("2026-10-02T09:05:00")
    assert sum(g["reviewed"] for g in saved["groups"]) == 2             # the later state wins


def test_different_sessions_get_different_files_even_in_the_same_second(tmp_path):
    one, _ = make()
    other, _ = make()
    one.mark_reviewed(0)
    other.mark_reviewed(0)
    assert _save(one, tmp_path) != _save(other, tmp_path)
    assert len(_json_files(tmp_path)) == 2


def test_logs_load_oldest_first_and_foreign_files_are_skipped(tmp_path):
    from myphotoworks.utils.selection_log import load_selection_logs

    early, _ = make()
    early.mark_reviewed(0)
    late, _ = make()
    late.mark_reviewed(0)
    late.mark_reviewed(1)
    _save(late, tmp_path, now=datetime(2026, 10, 3, 9, 0, 0))
    _save(early, tmp_path, now=datetime(2026, 10, 2, 9, 0, 0))
    (tmp_path / "notes.json").write_text('{"hello": 1}', encoding="utf-8")
    (tmp_path / "broken.json").write_text("{not json", encoding="utf-8")
    (tmp_path / "readme.txt").write_text("hi", encoding="utf-8")
    logs = load_selection_logs(tmp_path)
    assert [entry["logged_at"][:10] for entry in logs] == ["2026-10-02", "2026-10-03"]
    assert [sum(g["reviewed"] for g in entry["groups"]) for entry in logs] == [1, 2]


def test_logs_written_before_the_session_id_still_load(tmp_path):
    from myphotoworks.utils.selection_log import load_selection_logs

    old = {"schema": 1, "source": "user", "algorithm": "v2-stage3", "sensitivity": 1.0,
           "root": "/photos/day1", "groups": [], "logged_at": "2026-10-01T10:00:00"}
    (tmp_path / "20261001-100000.json").write_text(json.dumps(old), encoding="utf-8")
    assert [entry["logged_at"] for entry in load_selection_logs(tmp_path)] == [
        "2026-10-01T10:00:00"]


def test_loading_a_missing_folder_gives_an_empty_list(tmp_path):
    from myphotoworks.utils.selection_log import load_selection_logs

    assert load_selection_logs(tmp_path / "nothing") == []


# ---- the setting ----------------------------------------------------------------------------


def test_the_selection_log_is_on_by_default():
    from myphotoworks.models.settings import AppSettings

    assert AppSettings().selection_log is True


def test_the_setting_survives_the_config_round_trip():
    from myphotoworks.models.settings import AppSettings
    from myphotoworks.utils.config import load_settings, save_settings

    cfg: dict = {}
    save_settings(cfg, AppSettings(selection_log=False))
    assert cfg["app_settings"]["selection_log"] is False
    assert load_settings(cfg).selection_log is False
    save_settings(cfg, AppSettings(selection_log=True))
    assert load_settings(cfg).selection_log is True


def test_an_older_config_without_the_key_means_on():
    from myphotoworks.utils.config import load_settings

    assert load_settings({"app_settings": {"brightness": 5}}).selection_log is True


@pytest.mark.parametrize("value", [False, 0])
def test_a_stored_off_value_stays_off(value):
    from myphotoworks.utils.config import load_settings

    assert load_settings({"app_settings": {"selection_log": value}}).selection_log is False


def test_a_failed_replace_leaves_no_temporary_file_behind(tmp_path, monkeypatch):
    import os

    session, _ = make()
    session.mark_reviewed(0)

    def boom(*a, **k):
        raise PermissionError("target is locked")

    monkeypatch.setattr(os, "replace", boom)
    assert _save(session, tmp_path) is None
    assert list(tmp_path.iterdir()) == []                       # no .tmp, no half log
