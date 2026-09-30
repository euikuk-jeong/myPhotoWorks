from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

from myphotoworks.core.scoring import ALGORITHM_VERSION, QualityScores, recommend
from myphotoworks.dev.eval_metrics import (
    baseline_rank,
    evaluate,
    judge_group,
    score_file,
    size_bucket,
    summarize,
)


def fake_scores(table):
    """score_fn reading QualityScores from a {filename: sharpness} table."""
    def fn(path: Path) -> QualityScores:
        if path.name not in table:
            raise FileNotFoundError(path)
        return QualityScores(table[path.name], 70.0, 60.0)
    return fn


def label(groups, root="/r"):
    return {"schema": 1, "root": root, "groups": groups}


def grp(files, picked, **kw):
    return {"id": 0, "files": files, "picked": picked, "reviewed": True, **kw}


SCORES = {"a": 90, "b": 70, "c": 30, "d": 60, "e": 80, "f": 50, "g": 40, "h": 20}


def test_judge_group_top1_top2():  # C1
    assert judge_group([0, 1, 2], {0}) == (True, True, 0, 0)
    assert judge_group([0, 1, 2], {1}) == (False, True, 0, 0)
    assert judge_group([0, 1, 2], {2}) == (False, False, 0, 0)


def test_multiple_picked_hits_when_top_is_any_picked():  # C2
    assert judge_group([2, 0, 1], {0, 2})[0] is True


def test_breakdown_by_size_and_tag():  # C3
    labels = [label([
        grp(["a", "b"], ["a"], tags=["portrait"]),          # size 2 hit
        grp(["d", "e", "f"], ["d"], tags=["portrait", "group"]),  # size 3 miss (e best)
        grp(["a", "b", "c", "d"], ["a"], tags=["film_scan"]),     # size 4+ hit
    ])]
    s = summarize(evaluate(labels, score_fn=fake_scores(SCORES)))
    assert s["overall"] == {"n": 3, "top1": 2 / 3, "top2": 1.0}
    assert s["by_size"]["2"]["top1"] == 1.0 and s["by_size"]["3"]["top1"] == 0.0
    assert s["by_size"]["4+"]["n"] == 1
    assert s["by_tag"]["portrait"]["n"] == 2 and s["by_tag"]["portrait"]["top1"] == 0.5
    assert s["by_tag"]["film_scan"]["top1"] == 1.0
    assert size_bucket(2) == "2" and size_bucket(3) == "3" and size_bucket(9) == "4+"


def test_unreviewed_groups_excluded_and_counted():  # C4
    labels = [label([grp(["a", "b"], ["a"], reviewed=False), grp(["a", "b"], ["a"])])]
    r = evaluate(labels, score_fn=fake_scores(SCORES))
    assert len(r.results) == 1 and r.skipped_unreviewed == 1


def test_uninformative_groups_excluded():  # C5
    labels = [label([grp(["a", "b"], []), grp(["a", "b"], ["a", "b"]), grp(["a", "b"], ["b"])])]
    r = evaluate(labels, score_fn=fake_scores(SCORES))
    assert len(r.results) == 1 and r.skipped_uninformative == 2


def test_unreadable_files_skipped_without_crash():  # C6
    labels = [label([grp(["a", "missing"], ["a"]), grp(["a", "b"], ["a"])])]
    r = evaluate(labels, score_fn=fake_scores(SCORES))
    assert len(r.results) == 1 and r.skipped_unreadable == 1
    assert summarize(r)["skipped"]["unreadable"] == 1


def test_pair_accuracy():  # C7
    g = grp(["a", "b", "c"], ["a"], pairs=[["a", "b"], ["b", "c"], ["c", "a"]])
    s = summarize(evaluate([label([g])], score_fn=fake_scores(SCORES)))
    assert s["pair_accuracy"] == 2 / 3
    assert judge_group([0, 1, 2], {0}, [(0, 2), (2, 1)]) == (True, True, 2, 1)
    assert summarize(evaluate([label([grp(["a", "b"], ["a"])])],
                              score_fn=fake_scores(SCORES)))["pair_accuracy"] is None


def test_deterministic():  # C8
    labels = [label([grp(["a", "b", "c"], ["b"]), grp(["d", "e"], ["e"])])]
    a = summarize(evaluate(labels, score_fn=fake_scores(SCORES)))
    b = summarize(evaluate(labels, score_fn=fake_scores(SCORES)))
    assert a == b


def test_baseline_rank_top_matches_recommend():  # C9
    rng = np.random.default_rng(0)
    for _ in range(50):
        group = [QualityScores(*rng.uniform(0, 100, 3)) for _ in range(rng.integers(2, 6))]
        assert baseline_rank(group)[0] == recommend(group, (0.5, 0.3, 0.2))
    tie = [QualityScores(50, 50, 50)] * 3
    assert baseline_rank(tie) == [0, 1, 2]


def test_end_to_end_sharp_vs_blur(tmp_path):  # C10
    rng = np.random.default_rng(1)
    base = Image.fromarray(rng.integers(0, 256, (240, 320, 3), dtype=np.uint8))
    base.save(tmp_path / "sharp.jpg", quality=95)
    base.filter(ImageFilter.GaussianBlur(4)).save(tmp_path / "blur.jpg", quality=95)
    labels = [label([grp(["blur.jpg", "sharp.jpg"], ["sharp.jpg"])], root=str(tmp_path))]
    s = summarize(evaluate(labels))
    assert s["overall"] == {"n": 1, "top1": 1.0, "top2": 1.0}
    sharp, blur = score_file(tmp_path / "sharp.jpg"), score_file(tmp_path / "blur.jpg")
    assert sharp.sharpness > blur.sharpness


def test_root_override(tmp_path):
    base = Image.fromarray(np.zeros((64, 64, 3), dtype=np.uint8))
    base.save(tmp_path / "x.jpg")
    base.save(tmp_path / "y.jpg")
    labels = [label([grp(["x.jpg", "y.jpg"], ["x.jpg"])], root="D:/nowhere")]
    assert evaluate(labels, root_override=tmp_path).skipped_unreadable == 0
    assert evaluate(labels).skipped_unreadable == 1


def test_label_weights_drive_the_ranking():  # C11
    table = {"hi_sharp": QualityScores(90, 10, 10), "hi_exp": QualityScores(10, 90, 10)}

    def fn(path):
        return table[path.name]

    def picked_hit(weights):
        g = grp(["hi_sharp", "hi_exp"], ["hi_sharp"])
        return evaluate([{**label([g]), "weights": weights}], score_fn=fn).results[0].top1

    assert picked_hit([1, 0, 0]) is True
    assert picked_hit([0, 1, 0]) is False


def test_algorithm_mismatch_warns_but_matching_or_missing_does_not():  # C12
    g = grp(["a", "b"], ["a"])
    old = {**label([g]), "algorithm": "old"}
    ok = {**label([g]), "algorithm": ALGORITHM_VERSION}
    assert evaluate([old], score_fn=fake_scores(SCORES)).warnings
    assert not evaluate([ok, label([g])], score_fn=fake_scores(SCORES)).warnings
    assert "old" in summarize(evaluate([old], score_fn=fake_scores(SCORES)))["warnings"][0]


def test_failures_keep_cause_and_are_capped():  # C13
    groups = [grp(["a", f"missing{i}"], ["a"]) for i in range(9)]
    r = evaluate([label(groups)], score_fn=fake_scores(SCORES))
    assert r.skipped_unreadable == 9 and len(r.errors) == 5
    assert "FileNotFoundError" in r.errors[0] and "missing0" in r.errors[0]
    assert summarize(r)["errors"] == r.errors


def test_unresolvable_picked_is_bad_label_not_a_miss():  # C14
    labels = [label([grp(["a", "b"], ["zzz"]), grp(["a", "b"], ["a"])])]
    r = evaluate(labels, score_fn=fake_scores(SCORES))
    assert len(r.results) == 1 and r.skipped_bad_label == 1
    assert summarize(r)["skipped"]["bad_label"] == 1


def test_top2_reported_without_trivial_two_photo_groups():  # C15
    labels = [label([
        grp(["a", "b"], ["b"]),            # size 2: top2 always true
        grp(["a", "b", "c"], ["c"]),       # size 3: c is last -> top2 miss
    ])]
    s = summarize(evaluate(labels, score_fn=fake_scores(SCORES)))
    assert s["overall"]["top2"] == 0.5
    assert s["top2_size3plus"] == {"n": 1, "top1": 0.0, "top2": 0.0}


def test_edited_only_summary():  # C16
    labels = [label([
        grp(["a", "b"], ["a"], edited=False),
        grp(["a", "b"], ["b"], edited=True),
    ])]
    s = summarize(evaluate(labels, score_fn=fake_scores(SCORES)))
    assert s["overall"]["top1"] == 0.5
    assert s["edited_only"] == {"n": 1, "top1": 0.0, "top2": 1.0}
    assert summarize(evaluate([label([grp(["a", "b"], ["a"])])],
                              score_fn=fake_scores(SCORES)))["edited_only"]["n"] == 0
