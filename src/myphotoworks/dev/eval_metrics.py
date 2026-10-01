"""Hit-rate metrics for recommendation algorithms against user labels (GUI-free, pure logic).

A label file follows schema 1 (see ``GroupSession.to_label_dict``). Only groups whose choice
carries information are counted: ``reviewed`` groups with at least one picked and at least one
non-picked photo.
"""
from __future__ import annotations

import json
import logging
from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path

from myphotoworks.core.ranking import recommend as v2_recommend
from myphotoworks.core.scoring import (
    ALGORITHM_VERSION,
    DEFAULT_WEIGHTS,
    QualityScores,
    Weights,
    composite,
)

logger = logging.getLogger(__name__)

MAX_ERRORS = 5

# (scores, label weights, label sensitivity) -> member indices, best first
Ranker = Callable[[list[QualityScores], Weights, float], list[int]]
ScoreFn = Callable[[Path], QualityScores]


def baseline_rank(scores: list[QualityScores], weights: Weights = DEFAULT_WEIGHTS) -> list[int]:
    """Current (v1.4) ranking: weighted sum, first wins ties. Best first.

    ``weights`` are the ones the label was made with, so the evaluated ranking matches what
    the user saw.
    """
    totals = [composite(s, weights) for s in scores]
    return sorted(range(len(scores)), key=lambda i: (-totals[i], i))


def v2_rank(scores: list[QualityScores], deadband_scale: float = 1.0) -> list[int]:
    """Recommendation v2 order, best first: the chain's pick, then the pick of the rest, ..."""
    left = list(range(len(scores)))
    order: list[int] = []
    while left:
        pick = v2_recommend([scores[i] for i in left], deadband_scale).index
        order.append(left.pop(pick))
    return order


def v2_tie(scores: list[QualityScores], deadband_scale: float = 1.0) -> bool:
    """True when v2 calls the group a tie ("차이 미미")."""
    return v2_recommend(scores, deadband_scale).tie


RANKERS: dict[str, Ranker] = {
    "baseline": lambda scores, weights, sensitivity: baseline_rank(scores, weights),
    "v2": lambda scores, weights, sensitivity: v2_rank(scores, sensitivity),
}


@dataclass
class GroupResult:
    size: int
    tags: list[str]
    top1: bool
    top2: bool
    pair_total: int = 0
    pair_correct: int = 0
    edited: bool = False
    tie: bool | None = None   # v2 only: the group was a "차이 미미" tie


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
    return bool(picked) and len(picked) < len(files)


@dataclass
class Report:
    results: list[GroupResult] = field(default_factory=list)
    skipped_unreviewed: int = 0
    skipped_uninformative: int = 0
    skipped_unreadable: int = 0
    skipped_bad_label: int = 0
    errors: list[str] = field(default_factory=list)  # first few failures, with path and cause
    warnings: list[str] = field(default_factory=list)


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
        weights = tuple(label.get("weights", DEFAULT_WEIGHTS))
        sensitivity = float(label.get("sensitivity", 1.0))
        made_with = label.get("algorithm")
        if made_with is not None and made_with != ALGORITHM_VERSION:
            report.warnings.append(
                f"label made with algorithm '{made_with}', current is '{ALGORITHM_VERSION}'"
            )
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
            except Exception as exc:  # unreadable file or scoring failure; keep the cause
                report.skipped_unreadable += 1
                logger.warning("scoring failed for group %s: %s", g.get("id"), exc)
                if len(report.errors) < MAX_ERRORS:
                    report.errors.append(f"{root / files[0]} ...: {type(exc).__name__}: {exc}")
                continue
            index = {f: i for i, f in enumerate(files)}
            picked = {index[f] for f in g["picked"] if f in index}
            if not picked:  # picked names that are not in files: a broken label, not a miss
                report.skipped_bad_label += 1
                continue
            pairs = [(index[w], index[lo]) for w, lo in g.get("pairs", [])
                     if w in index and lo in index]
            t1, t2, pt, pc = judge_group(ranker(scores, weights, sensitivity), picked, pairs)
            report.results.append(
                GroupResult(len(files), list(g.get("tags", [])), t1, t2, pt, pc,
                            bool(g.get("edited", False)),
                            v2_tie(scores, sensitivity) if algo == "v2" else None)
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
    ties = [r.tie for r in report.results if r.tie is not None]
    summary = {
        "overall": _rate(report.results),
        # a 2-photo group is always a top-2 hit, so top2 is also given without them
        "top2_size3plus": _rate([r for r in report.results if r.size >= 3]),
        # groups where the user overrode the recommendation: the strictest (lower-bound) labels
        "edited_only": _rate([r for r in report.results if r.edited]),
        "by_size": {k: _rate(v) for k, v in sorted(by_size.items())},
        "by_tag": {k: _rate(v) for k, v in sorted(by_tag.items())},
        "pair_accuracy": pair_correct / pair_total if pair_total else None,
        "skipped": {
            "unreviewed": report.skipped_unreviewed,
            "uninformative": report.skipped_uninformative,
            "unreadable": report.skipped_unreadable,
            "bad_label": report.skipped_bad_label,
        },
        "errors": report.errors,
        "warnings": sorted(set(report.warnings)),
    }
    if ties:   # share of groups v2 could not separate ("차이 미미")
        summary["tie_rate"] = sum(ties) / len(ties)
    return summary


def load_label(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def score_file(path: Path) -> QualityScores:
    """Scores exactly as the grouping run computes them, without correction settings, plus the
    legacy whole-frame values the ``baseline`` ranker needs."""
    from dataclasses import replace

    from myphotoworks.core.analysis_image import load_analysis_image
    from myphotoworks.core.scoring import exposure_score, score_images, sharpness_score

    raw = load_analysis_image(path)
    return replace(score_images(raw, raw),
                   sharpness=sharpness_score(raw), exposure=exposure_score(raw))
