"""Recommendation by priority chain with deadbands (pure logic, no Qt).

Criteria are checked in order. Photos whose value is within the criterion's *deadband* of the
best one stay in the race; the first criterion that leaves a single photo is the *deciding*
criterion. If every criterion leaves several, the group is a tie ("차이 미미") and a weighted
sum picks the photo. A group never gets a hard "winner" on a difference too small to matter.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from myphotoworks.core.scoring import QualityScores

# ---- tunables (plan §7; tuned with the evaluation script) ----------------------------------
SHARPNESS_DEADBAND = 0.10      # relative: within 10 % of the best subject sharpness is a tie
EXPOSURE_DEADBAND = 10.0       # absolute points of subject exposure
COLOR_DEADBAND = 10.0          # absolute points of colourfulness
COLOR_IGNORE_BELOW = 8.0       # a group whose most colourful photo is below this is monochrome
EXPOSURE_FAIL = 10.0           # subject exposure below this: subject (almost) black / blown out
SHARPNESS_FAIL = 15.0          # subject sharpness below this: no usable detail at all
TIEBREAK_WEIGHTS = (0.6, 0.3, 0.1)   # sharpness / exposure / colour, only used for ties

# deadband multipliers behind the three sensitivity steps (low, normal, high)
SENSITIVITY_CHOICES: tuple[tuple[float, str], ...] = ((1.5, "낮음"), (1.0, "보통"), (0.6, "높음"))

_EPS = 1e-9


@dataclass(frozen=True)
class Criterion:
    """One step of the chain. ``key`` maps an item to its value; ``deadband`` is absolute, or a
    share of the best value when ``relative``."""

    name: str
    key: Callable[[Any], float]
    deadband: float
    relative: bool = False
    higher_is_better: bool = True


@dataclass(frozen=True)
class Recommendation:
    index: int
    deciding_criterion: str | None   # None for ties and single photos
    tie: bool


@dataclass(frozen=True)
class CriterionRow:
    """One bar of the detail panel for one photo."""

    name: str
    label: str
    value: float          # the photo's own value
    relative: float       # value / group best, 0..1
    deciding: bool        # this criterion decided the group
    tied: bool            # the whole group is inside this criterion's deadband ("≈")


def _margin(criterion: Criterion, best: float, scale: float) -> float:
    base = criterion.deadband * scale
    return base * abs(best) if criterion.relative else base


def _survivors(items: Sequence[Any], alive: list[int], c: Criterion, scale: float) -> list[int]:
    values = {i: c.key(items[i]) for i in alive}
    best = max(values.values()) if c.higher_is_better else min(values.values())
    margin = _margin(c, best, scale) + _EPS
    if c.higher_is_better:
        return [i for i in alive if best - values[i] <= margin]
    return [i for i in alive if values[i] - best <= margin]


def select_best(
    items: Sequence[Any],
    criteria: Sequence[Criterion],
    tiebreak: Callable[[Any], float],
    deadband_scale: float = 1.0,
) -> Recommendation:
    """Run the chain over ``items``; ``deadband_scale`` multiplies every deadband."""
    if not items:
        raise ValueError("cannot recommend from an empty group")
    alive = list(range(len(items)))
    if len(alive) == 1:
        return Recommendation(0, None, False)
    for c in criteria:
        alive = _survivors(items, alive, c, deadband_scale)
        if len(alive) == 1:
            return Recommendation(alive[0], c.name, False)
    best = max(alive, key=lambda i: (tiebreak(items[i]), -i))
    return Recommendation(best, None, True)


# ---- stage-1 chain on QualityScores ------------------------------------------------------------

SUBJECT_SHARPNESS = Criterion(
    "subject_sharpness", lambda s: s.subject_sharpness, SHARPNESS_DEADBAND, relative=True)
SUBJECT_EXPOSURE = Criterion("subject_exposure", lambda s: s.subject_exposure, EXPOSURE_DEADBAND)
COLOR = Criterion("color", lambda s: s.color, COLOR_DEADBAND)

_LABELS = {"subject_sharpness": "주제 선명도", "subject_exposure": "주제 노출", "color": "색감"}


def _tiebreak(s: QualityScores) -> float:
    ws, we, wc = TIEBREAK_WEIGHTS
    return ws * s.subject_sharpness + we * s.subject_exposure + wc * s.color


def _is_monochrome(group: Sequence[QualityScores]) -> bool:
    return max(s.color for s in group) < COLOR_IGNORE_BELOW


def _chain(group: Sequence[QualityScores]) -> list[Criterion]:
    chain = [SUBJECT_SHARPNESS, SUBJECT_EXPOSURE]
    if not _is_monochrome(group):
        chain.append(COLOR)
    return chain


def _failed(s: QualityScores) -> bool:
    return s.subject_exposure < EXPOSURE_FAIL or s.subject_sharpness < SHARPNESS_FAIL


def _pool(group: Sequence[QualityScores]) -> list[int]:
    """Indices that compete: photos that obviously failed (subject black / blown out, no detail
    at all) only compete when nothing in the group passed."""
    passed = [i for i, s in enumerate(group) if not _failed(s)]
    return passed if passed else list(range(len(group)))


def recommend(group: Sequence[QualityScores], deadband_scale: float = 1.0) -> Recommendation:
    """Pick the photo to recommend from ``group`` (index into ``group``)."""
    if not group:
        raise ValueError("cannot recommend from an empty group")
    pool = _pool(group)
    members = [group[i] for i in pool]
    rec = select_best(members, _chain(members), _tiebreak, deadband_scale)
    if len(pool) < len(group) and len(pool) == 1:
        return Recommendation(pool[0], "gate", False)
    return Recommendation(pool[rec.index], rec.deciding_criterion, rec.tie)


def reason_label(rec: Recommendation, group_size: int) -> str:
    """Badge text for the recommended photo: which criterion decided."""
    if group_size == 1:
        return "단독 사진"
    if rec.tie:
        return "차이 미미"
    if rec.deciding_criterion == "gate":
        return "다른 사진은 사용 어려움"
    if rec.deciding_criterion in _LABELS:
        return f"{_LABELS[rec.deciding_criterion]} 우세"
    return ""


def criterion_rows(
    group: Sequence[QualityScores],
    index: int,
    rec: Recommendation,
    deadband_scale: float = 1.0,
) -> list[CriterionRow]:
    """Detail-panel data for ``group[index]``: each chain criterion relative to the group best,
    which one decided, and which ones could not tell the photos apart. "Could not tell apart"
    is judged among the photos that actually competed in ``recommend`` (failed ones left out)."""
    pool = [group[i] for i in _pool(group)]
    rows = []
    for c in (SUBJECT_SHARPNESS, SUBJECT_EXPOSURE, COLOR):
        values = [c.key(s) for s in group]
        best = max(values)
        pooled = [c.key(s) for s in pool]
        pool_best = max(pooled)
        monochrome_skip = c is COLOR and _is_monochrome(pool)
        tied = (monochrome_skip
                or pool_best - min(pooled) <= _margin(c, pool_best, deadband_scale) + _EPS)
        value = c.key(group[index])
        relative = min(1.0, max(0.0, value / best)) if best > 0 else 1.0
        rows.append(CriterionRow(c.name, _LABELS[c.name], value, relative,
                                 rec.deciding_criterion == c.name, tied))
    return rows


def sensitivity_label(scale: float) -> str:
    """Name of the sensitivity step closest to ``scale``."""
    return min(SENSITIVITY_CHOICES, key=lambda choice: abs(choice[0] - scale))[1]
