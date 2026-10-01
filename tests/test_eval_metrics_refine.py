"""Stage-3 refinement — evaluation of selection logs (code review of PR #44).

* ``ALGORITHM_VERSION`` becomes ``"v2-stage3.1"``: the tilt estimator and the person-chain gate
  changed the recommendations, so labels made before must be told apart.
* ``evaluate`` counts a session once: labels sharing a non-empty ``"session"`` (reopened reviews,
  logs copied around) keep only the newest (by ``logged_at``, ties: the later one in the list).
  Labels without a session (exports, older logs) are never merged.
* ``evaluate`` warns when labels were made with face analysis (``algorithm`` "v2-stage2" or
  later) but the default scoring is used without a face engine: the person chain would silently
  not be measured. No warning with a ``face_engine``, a custom ``score_fn`` or older labels.
"""
import pytest

from tests.synthetic import FakeFaceEngine, scores

SHARP = {"a.jpg": 90.0, "b.jpg": 40.0}          # v2 recommends a.jpg


def _label(session, logged_at, picked, algorithm=None):
    from myphotoworks.core.scoring import ALGORITHM_VERSION

    label = {"schema": 1, "source": "user", "algorithm": algorithm or ALGORITHM_VERSION,
             "sensitivity": 1.0, "root": "/r", "logged_at": logged_at,
             "groups": [{"id": 0, "files": ["a.jpg", "b.jpg"], "picked": [picked],
                         "recommended": "a.jpg", "reviewed": True, "edited": picked != "a.jpg"}]}
    if session is not None:
        label["session"] = session
    return label


def _score_fn(path):
    return scores(SHARP[path.name])


def _evaluate(labels, **kw):
    from myphotoworks.dev.eval_metrics import evaluate

    kw.setdefault("score_fn", _score_fn)
    return evaluate(labels, "v2", **kw)


def test_algorithm_version_marks_the_stage_three_refinement():
    from myphotoworks.core.scoring import ALGORITHM_VERSION

    assert ALGORITHM_VERSION == "v2-stage3.1"


# ---- sessions are counted once ---------------------------------------------------------------


def test_the_newest_log_of_a_session_is_the_one_that_counts():
    old = _label("s1", "2026-10-02T09:00:00", picked="a.jpg")
    new = _label("s1", "2026-10-02T09:30:00", picked="b.jpg")      # the user changed their mind
    for labels in ([old, new], [new, old]):
        report = _evaluate(labels)
        assert len(report.results) == 1
        assert report.results[0].top1 is False                          # newest: picked b, rec a


def test_different_sessions_all_count():
    report = _evaluate([_label("s1", "2026-10-02T09:00:00", "a.jpg"),
                        _label("s2", "2026-10-02T09:00:00", "a.jpg")])
    assert len(report.results) == 2


def test_labels_without_a_session_are_never_merged():
    report = _evaluate([_label(None, "2026-10-02T09:00:00", "a.jpg"),
                        _label(None, "2026-10-02T09:00:00", "a.jpg"),
                        _label("", "2026-10-02T09:00:00", "a.jpg")])
    assert len(report.results) == 3


def test_a_tie_in_time_keeps_the_later_label_of_the_list():
    first = _label("s1", "2026-10-02T09:00:00", picked="a.jpg")
    second = _label("s1", "2026-10-02T09:00:00", picked="b.jpg")
    assert _evaluate([first, second]).results[0].top1 is False


# ---- face analysis warning ----------------------------------------------------------------------


def _warns_about_faces(report):
    return any("face" in w.lower() for w in report.warnings)


def test_labels_made_with_faces_but_replayed_without_a_face_engine_are_warned_about():
    from myphotoworks.dev.eval_metrics import evaluate

    label = _label("s1", "2026-10-02T09:00:00", "a.jpg")
    label["root"] = "/nonexistent"                       # nothing to read: only the warning matters
    assert _warns_about_faces(evaluate([label], "v2"))


@pytest.mark.parametrize("how", ["face_engine", "score_fn"])
def test_no_warning_when_faces_are_handled(how):
    from myphotoworks.dev.eval_metrics import evaluate

    label = _label("s1", "2026-10-02T09:00:00", "a.jpg")
    label["root"] = "/nonexistent"
    kw = {"face_engine": FakeFaceEngine()} if how == "face_engine" else {"score_fn": _score_fn}
    assert not _warns_about_faces(evaluate([label], "v2", **kw))


@pytest.mark.parametrize("algorithm", ["baseline", "v2-stage1", "v2"])
def test_labels_older_than_face_analysis_need_no_face_warning(algorithm):
    from myphotoworks.dev.eval_metrics import evaluate

    label = _label("s1", "2026-10-02T09:00:00", "a.jpg", algorithm=algorithm)
    label["root"] = "/nonexistent"
    assert not _warns_about_faces(evaluate([label], "v2"))
