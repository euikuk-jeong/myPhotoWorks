"""Recommendation v2, stage 1 — evaluation side (plan §3-2 "v2 결과를 나란히", tie rate).

``dev/eval_metrics`` gains a ``"v2"`` ranker next to ``"baseline"`` (the baseline path and
its tests stay as they are), a full best-first ordering ``v2_rank`` and a "차이 미미" rate.
"""
from pathlib import Path

import numpy as np

from tests.synthetic import scores


def table_scores(table):
    """score_fn returning v2 ``QualityScores`` from a {filename: (sharp, exposure, color)}."""
    def fn(path: Path):
        if path.name not in table:
            raise FileNotFoundError(path)
        return scores(*table[path.name])
    return fn


def label(groups, root="/r", **kw):
    return {"schema": 1, "root": root, "groups": groups, **kw}


def grp(files, picked, **kw):
    return {"id": 0, "files": files, "picked": picked, "reviewed": True, **kw}


def test_v2_is_registered_next_to_baseline():
    from myphotoworks.dev.eval_metrics import RANKERS

    assert {"baseline", "v2"} <= set(RANKERS)


def test_v2_rank_is_a_best_first_permutation_whose_head_is_the_recommendation():
    from myphotoworks.core.ranking import recommend

    from myphotoworks.dev.eval_metrics import v2_rank

    rng = np.random.default_rng(0)
    for _ in range(30):
        group = [scores(*rng.uniform(5, 100, 3)) for _ in range(rng.integers(2, 6))]
        order = v2_rank(group)
        assert sorted(order) == list(range(len(group)))
        assert order[0] == recommend(group).index


def test_v2_rank_orders_clearly_different_photos_by_subject_sharpness():
    from myphotoworks.dev.eval_metrics import v2_rank

    group = [scores(30), scores(90), scores(60)]
    assert v2_rank(group) == [1, 2, 0]


def test_evaluate_with_v2_counts_hits():
    from myphotoworks.dev.eval_metrics import evaluate, summarize

    table = {"a": (90, 70, 60), "b": (60, 70, 60), "c": (30, 70, 60)}
    labels = [label([grp(["a", "b", "c"], ["a"]), grp(["a", "b", "c"], ["b"])])]
    s = summarize(evaluate(labels, algo="v2", score_fn=table_scores(table)))
    assert s["overall"] == {"n": 2, "top1": 0.5, "top2": 1.0}


def test_tie_rate_counts_negligible_difference_groups():
    from myphotoworks.dev.eval_metrics import evaluate, summarize

    table = {"a": (80.0, 70.0, 60.0), "b": (80.4, 70.3, 60.2),      # noise-level pair
             "c": (90, 70, 60), "d": (40, 70, 60)}                   # clear pair
    labels = [label([grp(["a", "b"], ["a"]), grp(["c", "d"], ["c"])])]
    s = summarize(evaluate(labels, algo="v2", score_fn=table_scores(table)))
    assert s["tie_rate"] == 0.5


def test_labels_made_with_v2_do_not_trigger_the_algorithm_mismatch_warning():
    from myphotoworks.core.scoring import ALGORITHM_VERSION
    from myphotoworks.dev.eval_metrics import evaluate

    table = {"a": (90, 70, 60), "b": (60, 70, 60)}
    r = evaluate([label([grp(["a", "b"], ["a"])], algorithm=ALGORITHM_VERSION)],
                 algo="v2", score_fn=table_scores(table))
    assert r.warnings == [] and ALGORITHM_VERSION != "baseline"
