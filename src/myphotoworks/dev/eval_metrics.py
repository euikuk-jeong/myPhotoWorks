"""Hit-rate metrics for recommendation algorithms against user labels (GUI-free, pure logic).

A label file follows schema 1 (see ``GroupSession.to_label_dict``). Only groups whose choice
carries information are counted: ``reviewed`` groups with at least one picked and at least one
non-picked photo.
"""
from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path

from myphotoworks.core.scoring import DEFAULT_WEIGHTS, QualityScores, composite

Ranker = Callable[[list[QualityScores]], list[int]]
ScoreFn = Callable[[Path], QualityScores]


def baseline_rank(scores: list[QualityScores]) -> list[int]:
    """Current (v1.4) ranking: weighted sum, first wins ties. Best first."""
    totals = [composite(s, DEFAULT_WEIGHTS) for s in scores]
    return sorted(range(len(scores)), key=lambda i: (-totals[i], i))


RANKERS: dict[str, Ranker] = {"baseline": baseline_rank}


@dataclass
class GroupResult:
    size: int
    tags: list[str]
    top1: bool
    top2: bool
    pair_total: int = 0
    pair_correct: int = 0


def judge_group(
    ranking: list[int],
    picked: set[int],
    pairs: list[tuple[int, int]] | None = None,
) -> tuple[bool, bool, int, int]:
    """(top1, top2, pair_total, pair_correct) for one group.

    ``ranking`` lists member indices best-first; ``pairs`` are (winner, loser) indices.
    """
    top1 = ranking[0] in picked
    top2 = any(i in picked for i in ranking[:2])
    place = {idx: rank for rank, idx in enumerate(ranking)}
    pairs = pairs or []
    correct = sum(1 for w, lo in pairs if place[w] < place[lo])
    return top1, top2, len(pairs), correct


def size_bucket(size: int) -> str:
    return str(size) if size <= 3 else "4+"


def is_informative(group: dict) -> bool:
    picked, files = set(group.get("picked", [])), group.get("files", [])
    return bool(picked) and len(picked) < len(files) and group.get("reviewed", True)


@dataclass
class Report:
    results: list[GroupResult] = field(default_factory=list)
    skipped_unreviewed: int = 0
    skipped_uninformative: int = 0
    skipped_unreadable: int = 0


def evaluate(
    labels: Iterable[dict],
    algo: str = "baseline",
    score_fn: ScoreFn | None = None,
    root_override: Path | None = None,
) -> Report:
    ranker = RANKERS[algo]
    score_fn = score_fn or score_file
    report = Report()
    for label in labels:
        root = Path(root_override if root_override is not None else label["root"])
        for g in label["groups"]:
            if not g.get("reviewed", True):
                report.skipped_unreviewed += 1
                continue
            if not is_informative(g):
                report.skipped_uninformative += 1
                continue
            files = g["files"]
            try:
                scores = [score_fn(root / f) for f in files]
            except Exception:
                report.skipped_unreadable += 1
                continue
            index = {f: i for i, f in enumerate(files)}
            pairs = [(index[w], index[lo]) for w, lo in g.get("pairs", [])
                     if w in index and lo in index]
            t1, t2, pt, pc = judge_group(
                ranker(scores), {index[f] for f in g["picked"] if f in index}, pairs
            )
            report.results.append(
                GroupResult(len(files), list(g.get("tags", [])), t1, t2, pt, pc)
            )
    return report


def _rate(results: list[GroupResult]) -> dict:
    n = len(results)
    if n == 0:
        return {"n": 0, "top1": None, "top2": None}
    return {
        "n": n,
        "top1": sum(r.top1 for r in results) / n,
        "top2": sum(r.top2 for r in results) / n,
    }


def summarize(report: Report) -> dict:
    by_size: dict[str, list[GroupResult]] = defaultdict(list)
    by_tag: dict[str, list[GroupResult]] = defaultdict(list)
    for r in report.results:
        by_size[size_bucket(r.size)].append(r)
        for t in r.tags:
            by_tag[t].append(r)
    pair_total = sum(r.pair_total for r in report.results)
    pair_correct = sum(r.pair_correct for r in report.results)
    return {
        "overall": _rate(report.results),
        "by_size": {k: _rate(v) for k, v in sorted(by_size.items())},
        "by_tag": {k: _rate(v) for k, v in sorted(by_tag.items())},
        "pair_accuracy": pair_correct / pair_total if pair_total else None,
        "skipped": {
            "unreviewed": report.skipped_unreviewed,
            "uninformative": report.skipped_uninformative,
            "unreadable": report.skipped_unreadable,
        },
    }


def load_label(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def score_file(path: Path) -> QualityScores:
    """Scores exactly as the grouping run computes them, without correction settings."""
    from myphotoworks.core.analysis_image import load_analysis_image
    from myphotoworks.core.scoring import score_images

    raw = load_analysis_image(path)
    return score_images(raw, raw)
