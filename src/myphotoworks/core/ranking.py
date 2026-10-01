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

from myphotoworks.core.composition import TILT_BADGE_DEG, composition_score
from myphotoworks.core.scoring import QualityScores

# ---- tunables (plan §7; tuned with the evaluation script) ----------------------------------
SHARPNESS_DEADBAND = 0.10      # relative: within 10 % of the best subject sharpness is a tie
EXPOSURE_DEADBAND = 10.0       # absolute points of subject exposure
COLOR_DEADBAND = 10.0          # absolute points of colourfulness
COLOR_IGNORE_BELOW = 8.0       # a group whose most colourful photo is below this is monochrome
EXPOSURE_FAIL = 10.0           # subject exposure below this: subject (almost) black / blown out
SHARPNESS_FAIL = 15.0          # subject sharpness below this: no usable detail at all
TIEBREAK_WEIGHTS = (0.6, 0.3, 0.1)   # sharpness / exposure / colour, only used for ties
COMPOSITION_DEADBAND = 10.0    # absolute points of composition_score
SMILE_DEADBAND = 0.15          # absolute smile (0..1): a smaller gap does not decide
SMILE_PRESENT_TH = 0.30        # smile only counts as a criterion if someone in the group reaches it
PERSON_TIEBREAK_WEIGHTS = (0.6, 0.3, 0.1)   # face sharpness / face exposure / smile (x100), ties

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


def _composition(s: QualityScores) -> float:
    """0..100 composition score of a photo: tilted lines and faces cut by the frame cost points."""
    return composition_score(s.tilt, s.faces.cut if s.faces else 0)


COMPOSITION = Criterion("composition", _composition, COMPOSITION_DEADBAND)

_LABELS = {"subject_sharpness": "주제 선명도", "subject_exposure": "주제 노출", "color": "색감",
           "face_detected": "얼굴 인식", "closed_eyes": "눈 감음", "smile": "웃음",
           "face_sharpness": "얼굴 선명도", "face_exposure": "얼굴 노출", "composition": "구도"}


# ---- person chain (stage 2): a group where at least one photo has a main face ------------------

FACE_DETECTED = Criterion("face_detected", lambda s: 1.0 if s.faces else 0.0, 0.0)
CLOSED_EYES = Criterion("closed_eyes", lambda s: float(s.faces.closed_eyes) if s.faces else 0.0,
                        0.0, higher_is_better=False)
SMILE = Criterion("smile", lambda s: s.faces.smile if s.faces else 0.0, SMILE_DEADBAND)
FACE_SHARPNESS = Criterion("face_sharpness", lambda s: s.faces.sharpness if s.faces else 0.0,
                           SHARPNESS_DEADBAND, relative=True)
FACE_EXPOSURE = Criterion("face_exposure", lambda s: s.faces.exposure if s.faces else 0.0,
                          EXPOSURE_DEADBAND)


def is_person_group(group: Sequence[QualityScores]) -> bool:
    """True when any photo of the group has a main face (plan Q13): the group is then judged by
    its people, and photos without a face rank behind those with one."""
    return any(s.faces for s in group)


def _smile_present(group: Sequence[QualityScores]) -> bool:
    return max((s.faces.smile for s in group if s.faces), default=0.0) >= SMILE_PRESENT_TH


def _person_chain(group: Sequence[QualityScores]) -> list[Criterion]:
    chain = [FACE_DETECTED, CLOSED_EYES]
    if _smile_present(group):
        chain.append(SMILE)
    return chain + [FACE_SHARPNESS, FACE_EXPOSURE, COMPOSITION]


def _person_tiebreak(s: QualityScores) -> float:
    if not s.faces:
        return 0.0
    ws, we, wm = PERSON_TIEBREAK_WEIGHTS
    return ws * s.faces.sharpness + we * s.faces.exposure + wm * 100.0 * s.faces.smile


def face_badges(s: QualityScores) -> list[str]:
    """Per-photo face facts for the badge line of a person group: "얼굴 없음", or "눈 감음 N명"
    and "얼굴 잘림 N명"."""
    if not s.faces:
        return ["얼굴 없음"]
    badges = []
    if s.faces.closed_eyes:
        badges.append(f"눈 감음 {s.faces.closed_eyes}명")
    if s.faces.cut:
        badges.append(f"얼굴 잘림 {s.faces.cut}명")
    return badges


def tilt_badges(s: QualityScores) -> list[str]:
    """"기울어짐" for a photo whose lines are tilted by ``TILT_BADGE_DEG`` or more."""
    return ["기울어짐"] if s.tilt is not None and abs(s.tilt) >= TILT_BADGE_DEG else []


def _tiebreak(s: QualityScores) -> float:
    ws, we, wc = TIEBREAK_WEIGHTS
    return ws * s.subject_sharpness + we * s.subject_exposure + wc * s.color


def _is_monochrome(group: Sequence[QualityScores]) -> bool:
    return max(s.color for s in group) < COLOR_IGNORE_BELOW


def _chain(group: Sequence[QualityScores]) -> list[Criterion]:
    chain = [SUBJECT_SHARPNESS, SUBJECT_EXPOSURE, COMPOSITION]
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
    """Pick the photo to recommend from ``group`` (index into ``group``).

    A group with a main face anywhere runs the person chain, any other group the subject chain."""
    if not group:
        raise ValueError("cannot recommend from an empty group")
    if is_person_group(group):
        return select_best(group, _person_chain(group), _person_tiebreak, deadband_scale)
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
    if rec.deciding_criterion == "closed_eyes":
        return "눈 감음 적음"
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
    is judged among the photos that actually competed in ``recommend`` (failed ones left out).
    A person group shows the four person criteria instead; a photo without a face gets empty
    bars. The composition row only appears when a competing photo has something to criticise."""
    if is_person_group(group):
        return _person_rows(group, index, rec, deadband_scale)
    pool = [group[i] for i in _pool(group)]
    criteria = [SUBJECT_SHARPNESS, SUBJECT_EXPOSURE]
    if any(_composition(s) < 100.0 for s in pool):
        criteria.append(COMPOSITION)
    rows = []
    for c in (*criteria, COLOR):
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


def _person_rows(
    group: Sequence[QualityScores], index: int, rec: Recommendation, deadband_scale: float
) -> list[CriterionRow]:
    """Detail rows of a person group. Everything is judged among the photos with a face (the
    ones that competed). The bar of "눈 감음" is the share ``(fewest + 1) / (this photo's + 1)``:
    full for the photo with the fewest closed eyes, shorter for more."""
    competing = [s for s in group if s.faces]
    photo = group[index]
    criteria = [CLOSED_EYES, SMILE, FACE_SHARPNESS, FACE_EXPOSURE]
    if any(_composition(s) < 100.0 for s in competing):
        criteria.append(COMPOSITION)
    rows = []
    for c in criteria:
        values = [c.key(s) for s in competing]
        best = max(values) if c.higher_is_better else min(values)
        skipped = c is SMILE and not _smile_present(group)
        tied = skipped or max(values) - min(values) <= _margin(c, best, deadband_scale) + _EPS
        value = c.key(photo)
        if not photo.faces:
            relative = 0.0
        elif c is CLOSED_EYES:
            relative = (best + 1) / (value + 1)
        else:
            relative = min(1.0, max(0.0, value / best)) if best > 0 else 1.0
        rows.append(CriterionRow(c.name, _LABELS[c.name], value, relative,
                                 rec.deciding_criterion == c.name, tied))
    return rows


def sensitivity_label(scale: float) -> str:
    """Name of the sensitivity step closest to ``scale``."""
    return min(SENSITIVITY_CHOICES, key=lambda choice: abs(choice[0] - scale))[1]
