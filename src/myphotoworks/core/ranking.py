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
    # against the recommended photo: -1..1 (positive = better) and better / worse / same (inside
    # the deadband) / none (nothing to compare); the recommended photo itself is the centre line
    delta: float = 0.0
    verdict: str = "same"


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
CRITERION_LABELS = _LABELS      # public name: the explanations in core/explain write these


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


def _face_failed(s: QualityScores) -> bool:
    """A photo with a face whose face is (nearly) black / blown out, or has no detail at all."""
    if not s.faces:
        return False
    return s.faces.exposure < EXPOSURE_FAIL or s.faces.sharpness < SHARPNESS_FAIL


def _person_pool(group: Sequence[QualityScores]) -> tuple[list[int], bool]:
    """Indices that compete in a person group, and whether the failure gate removed anyone.

    Photos with a failed face only compete when no photo with a face passed. Photos without a
    face are never failed: the face chain already ranks them behind every photo with a face."""
    with_face = [i for i, s in enumerate(group) if s.faces]
    passed = {i for i in with_face if not _face_failed(group[i])}
    if not passed or len(passed) == len(with_face):
        return list(range(len(group))), False
    return [i for i, s in enumerate(group) if not s.faces or i in passed], True


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
    """Per-photo face facts for the badge line of a person group: "얼굴 인식 안 됨" (the detector
    found no main face - that is not the same as "there is no face"), or "눈 감음 N명" and
    "얼굴 잘림 N명"."""
    if not s.faces:
        return ["얼굴 인식 안 됨"]
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
        pool, gated = _person_pool(group)
        members = [group[i] for i in pool]
        rec = select_best(members, _person_chain(members), _person_tiebreak, deadband_scale)
        winner = pool[rec.index]
        if gated and sum(1 for i in pool if group[i].faces) == 1:
            return Recommendation(winner, "gate", False)
        return Recommendation(winner, rec.deciding_criterion, rec.tie)
    pool = _pool(group)
    members = [group[i] for i in pool]
    rec = select_best(members, _chain(members), _tiebreak, deadband_scale)
    if len(pool) < len(group) and len(pool) == 1:
        return Recommendation(pool[0], "gate", False)
    return Recommendation(pool[rec.index], rec.deciding_criterion, rec.tie)


@dataclass(frozen=True)
class TraceStep:
    """One criterion of the chain, as ``chain_trace`` saw it. Photo numbers are indices into the
    group."""

    name: str
    label: str
    values: dict[int, float]            # the photos still in the race and their values
    alive_before: tuple[int, ...]
    alive_after: tuple[int, ...]        # within the deadband of the best
    margin: float                       # the deadband in the criterion's own unit
    allowance: float                    # the (scaled) deadband setting: a share when ``relative``
    relative: bool


@dataclass(frozen=True)
class ChainTrace:
    """What ``recommend`` did, step by step. ``winner``, ``deciding`` and ``tie`` always equal
    its result (``deciding`` is ``"gate"`` when the failure gate left one photo)."""

    person: bool
    pool: tuple[int, ...]               # photos that competed (the failure gate removed the rest)
    gated: bool                         # the failure gate removed somebody
    steps: tuple[TraceStep, ...]        # up to the step that left one photo, or all of them
    winner: int
    deciding: str | None
    tie: bool


def chain_trace(group: Sequence[QualityScores], deadband_scale: float = 1.0) -> ChainTrace:
    """Replay ``recommend`` and keep every step, so that a sentence can say why. Kept next to
    ``recommend``: the tests compare both on random groups."""
    if not group:
        raise ValueError("cannot recommend from an empty group")
    person = is_person_group(group)
    if person:
        pool, gated = _person_pool(group)
        members = [group[i] for i in pool]
        criteria, tiebreak = _person_chain(members), _person_tiebreak
    else:
        pool = _pool(group)
        gated = len(pool) < len(group)
        members = [group[i] for i in pool]
        criteria, tiebreak = _chain(members), _tiebreak
    alive = list(range(len(members)))
    steps: list[TraceStep] = []
    deciding: str | None = None
    tie = False
    winner = 0
    if len(alive) > 1:
        for c in criteria:
            values = {i: c.key(members[i]) for i in alive}
            best = max(values.values()) if c.higher_is_better else min(values.values())
            before = alive
            alive = _survivors(members, alive, c, deadband_scale)
            steps.append(TraceStep(
                c.name, _LABELS[c.name], {pool[i]: v for i, v in values.items()},
                tuple(pool[i] for i in before), tuple(pool[i] for i in alive),
                _margin(c, best, deadband_scale), c.deadband * deadband_scale, c.relative))
            if len(alive) == 1:
                winner, deciding = alive[0], c.name
                break
        else:
            winner = max(alive, key=lambda i: (tiebreak(members[i]), -i))
            tie = True
    winner = pool[winner]
    one_left = (sum(1 for i in pool if group[i].faces) == 1) if person else len(pool) == 1
    if gated and one_left:                  # the same case ``recommend`` calls "gate"
        deciding, tie = "gate", False
    return ChainTrace(person, tuple(pool), gated, tuple(steps), winner, deciding, tie)


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


# Full-scale span of a bar: the difference to the recommended photo that fills the half bar. A
# share of the recommended photo's value for the relative criteria (sharpness), otherwise the
# criterion's own unit (points, smile 0..1, people).
_BAR_SPAN = {"subject_sharpness": 0.5, "subject_exposure": 40.0, "composition": 40.0,
             "color": 40.0, "closed_eyes": 2.0, "smile": 0.5, "face_sharpness": 0.5,
             "face_exposure": 40.0}


def _versus(
    c: Criterion, value: float, reference: float, best: float, scale: float
) -> tuple[float, str]:
    """How ``value`` compares with the recommended photo's ``reference``: a signed length
    (positive = better, -1..1 of the half bar) and better / worse / same (inside the deadband)."""
    diff = (value - reference) if c.higher_is_better else (reference - value)
    if abs(diff) <= _margin(c, best, scale) + _EPS:
        verdict = "same"
    else:
        verdict = "better" if diff > 0 else "worse"
    size = diff / max(abs(reference), 1.0) if c.relative else diff
    return max(-1.0, min(1.0, size / _BAR_SPAN[c.name])), verdict


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
        delta, verdict = _versus(c, value, c.key(group[rec.index]), pool_best, deadband_scale)
        rows.append(CriterionRow(c.name, _LABELS[c.name], value, relative,
                                 rec.deciding_criterion == c.name, tied, delta, verdict))
    return rows


def _person_rows(
    group: Sequence[QualityScores], index: int, rec: Recommendation, deadband_scale: float
) -> list[CriterionRow]:
    """Detail rows of a person group, judged among the photos that competed (photos with a failed
    face are left out when the gate removed them: they cannot win, so they must not set the bars).
    The bar of "눈 감음" is the share ``(fewest + 1) / (this photo's + 1)``: full for the photo
    with the fewest closed eyes, shorter for more."""
    pool, _gated = _person_pool(group)
    competing = [group[i] for i in pool if group[i].faces]
    photo = group[index]
    criteria = [CLOSED_EYES, SMILE, FACE_SHARPNESS, FACE_EXPOSURE]
    if any(_composition(s) < 100.0 for s in competing):
        criteria.append(COMPOSITION)
    rows = []
    for c in criteria:
        pooled = [c.key(s) for s in competing]
        best = max(pooled) if c.higher_is_better else min(pooled)
        skipped = c is SMILE and not _smile_present([group[i] for i in pool])
        tied = skipped or max(pooled) - min(pooled) <= _margin(c, best, deadband_scale) + _EPS
        value = c.key(photo)
        delta, verdict = 0.0, "none"
        if not photo.faces:
            relative = 0.0
        else:
            if c is CLOSED_EYES:
                relative = min(1.0, (best + 1) / (value + 1))
            else:
                relative = min(1.0, max(0.0, value / best)) if best > 0 else 1.0
            delta, verdict = _versus(c, value, c.key(group[rec.index]), best, deadband_scale)
        rows.append(CriterionRow(c.name, _LABELS[c.name], value, relative,
                                 rec.deciding_criterion == c.name, tied, delta, verdict))
    return rows


def sensitivity_label(scale: float) -> str:
    """Name of the sensitivity step closest to ``scale``."""
    return min(SENSITIVITY_CHOICES, key=lambda choice: abs(choice[0] - scale))[1]
