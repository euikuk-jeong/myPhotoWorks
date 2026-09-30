from myphotoworks.dev.eval_metrics import evaluate, summarize
from myphotoworks.dev.phototriage import pairs_to_labels


def test_most_preferred_becomes_picked():  # D1
    label = pairs_to_labels([("s1", "a", "b"), ("s1", "a", "c"), ("s1", "b", "c")])
    g = label["groups"][0]
    assert g["files"] == ["a", "b", "c"] and g["picked"] == ["a"]
    assert label["schema"] == 1 and label["source"] == "phototriage" and g["reviewed"] is True


def test_ties_keep_all_top_photos_and_are_uninformative_when_all_tie():  # D2
    label = pairs_to_labels([("s1", "a", "b"), ("s1", "c", "d")])
    assert label["groups"][0]["picked"] == ["a", "c"]
    cyc = pairs_to_labels([("s2", "a", "b"), ("s2", "b", "c"), ("s2", "c", "a")])
    assert cyc["groups"][0]["picked"] == ["a", "b", "c"]
    assert evaluate([cyc], score_fn=lambda p: None).skipped_uninformative == 1


def test_single_photo_series_dropped():  # D3
    label = pairs_to_labels([("s1", "a", "a"), ("s2", "x", "y")])
    assert [g["series"] for g in label["groups"]] == ["s2"]


def test_pairs_preserved_and_feed_pair_accuracy():  # D4
    from myphotoworks.core.scoring import QualityScores

    label = pairs_to_labels([("s1", "a", "b"), ("s1", "a", "c"), ("s1", "c", "b")])
    assert label["groups"][0]["pairs"] == [["a", "b"], ["a", "c"], ["c", "b"]]
    table = {"a": 90, "b": 10, "c": 50}
    s = summarize(evaluate([label], score_fn=lambda p: QualityScores(table[p.name], 70, 60)))
    assert s["pair_accuracy"] == 1.0 and s["overall"]["top1"] == 1.0
