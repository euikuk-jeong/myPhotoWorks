"""Explainability, item 2 — ``ranking.chain_trace``: the steps behind a recommendation.

``recommend()`` only returns the winner and the deciding criterion. ``chain_trace(group, scale)``
replays the same chain and keeps what happened at every step (who was still in the race, their
values, the deadband), so a sentence can say *why*. It must never disagree with ``recommend()``.
"""
import random

import pytest

from tests.synthetic import person, scores


def _trace(group, scale=1.0):
    from myphotoworks.core.ranking import chain_trace

    return chain_trace(group, scale)


def _names(trace):
    return [s.name for s in trace.steps]


# ---- the trace never disagrees with recommend() ---------------------------------------------

def _random_photo(rng: random.Random, with_faces: bool):
    tilt = rng.choice([None, 0.4, 2.0, 4.0, 9.0])
    if with_faces and rng.random() < 0.85:
        return person(closed=rng.choice([0, 0, 1, 2]), smile=rng.choice([0.0, 0.2, 0.5, 0.9]),
                      face_sharp=rng.uniform(0, 100), face_exposure=rng.uniform(0, 100),
                      cut=rng.choice([0, 0, 1]), tilt=tilt,
                      subject_sharp=rng.uniform(0, 100), subject_exposure=rng.uniform(0, 100),
                      color=rng.uniform(0, 60))
    return scores(rng.uniform(0, 100), rng.uniform(0, 100), rng.choice([0.0, rng.uniform(0, 60)]),
                  tilt=tilt)


@pytest.mark.parametrize("seed", range(250))
def test_trace_agrees_with_recommend(seed):
    from myphotoworks.core.ranking import recommend

    rng = random.Random(seed)
    with_faces = rng.random() < 0.5
    group = [_random_photo(rng, with_faces) for _ in range(rng.randint(1, 6))]
    scale = rng.choice([0.6, 1.0, 1.5])
    rec = recommend(group, scale)
    trace = _trace(group, scale)
    assert trace.winner == rec.index
    assert trace.tie == rec.tie
    assert trace.deciding == rec.deciding_criterion


# ---- steps -------------------------------------------------------------------------------

def test_steps_follow_the_chain_and_stop_at_one_photo():
    group = [scores(70, 90), scores(68, 40), scores(30, 99)]
    trace = _trace(group)
    assert _names(trace) == ["subject_sharpness", "subject_exposure"]
    first, second = trace.steps
    assert first.alive_before == (0, 1, 2) and first.alive_after == (0, 1)
    assert first.values == {0: 70.0, 1: 68.0, 2: 30.0}
    assert second.alive_before == (0, 1) and second.alive_after == (0,)
    assert second.values == {0: 90.0, 1: 40.0}
    assert trace.winner == 0 and trace.deciding == "subject_exposure" and not trace.tie


def test_step_margin_is_the_deadband_in_the_criterions_own_unit():
    first, second = _trace([scores(70, 90), scores(68, 40)]).steps
    assert first.margin == pytest.approx(7.0)         # 10 % of the best sharpness (70)
    assert second.margin == pytest.approx(10.0)       # 10 exposure points


def test_sensitivity_scales_the_margin():
    first, second = _trace([scores(70, 90), scores(68, 40)], scale=1.5).steps
    assert first.margin == pytest.approx(10.5)
    assert second.margin == pytest.approx(15.0)


def test_step_labels_are_the_panel_labels():
    first, second = _trace([scores(70, 90), scores(68, 40)]).steps
    assert (first.label, second.label) == ("주제 선명도", "주제 노출")


def test_tie_runs_every_criterion_and_nobody_drops_out():
    trace = _trace([scores(), scores()])
    assert _names(trace) == ["subject_sharpness", "subject_exposure", "composition", "color"]
    assert all(step.alive_after == (0, 1) for step in trace.steps)
    assert trace.tie and trace.deciding is None


def test_monochrome_group_has_no_colour_step():
    trace = _trace([scores(color=0.0), scores(color=2.0)])
    assert "color" not in _names(trace)


def test_single_photo_has_no_steps():
    trace = _trace([scores()])
    assert trace.steps == () and trace.winner == 0
    assert trace.deciding is None and not trace.tie


# ---- failure gate ---------------------------------------------------------------------------

def test_gate_removes_a_failed_photo_before_the_chain():
    trace = _trace([scores(70, 70), scores(70, 2)])
    assert trace.pool == (0,) and trace.gated and not trace.person
    assert trace.steps == ()
    assert trace.winner == 0 and trace.deciding == "gate"


def test_no_gate_when_everybody_passes():
    trace = _trace([scores(70, 70), scores(40, 70)])
    assert trace.pool == (0, 1) and not trace.gated


# ---- person group ---------------------------------------------------------------------------

def test_person_group_runs_the_person_chain():
    trace = _trace([person(closed=0), person(closed=2)])
    assert trace.person
    assert _names(trace) == ["face_detected", "closed_eyes"]
    assert trace.deciding == "closed_eyes" and trace.winner == 0


def test_person_chain_adds_smile_only_when_somebody_smiles():
    quiet = _trace([person(smile=0.1), person(smile=0.2)])
    assert "smile" not in _names(quiet)
    smiling = _trace([person(smile=0.8), person(smile=0.1)])
    assert "smile" in _names(smiling)


def test_person_gate_names_the_person_pool():
    trace = _trace([person(face_exposure=70, face_sharp=70), person(face_exposure=2)])
    assert trace.person and trace.gated and trace.pool == (0,)
    assert trace.deciding == "gate"


def test_faceless_photo_is_eliminated_by_face_detection():
    trace = _trace([person(), scores()])
    first = trace.steps[0]
    assert first.name == "face_detected"
    assert first.alive_before == (0, 1) and first.alive_after == (0,)
    assert trace.deciding == "face_detected"
