"""Grouping by visual similarity with optional capture-time and EXIF assistance.

Two strategies:
  * sequential — compare each photo with its neighbour (and the group's first photo)
  * global     — compare each photo with every existing group (order independent)
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from myphotoworks.core.similarity import Signature, similarity

TIME_RELAX = 0.08            # threshold relief when timestamps are close and trusted
REPRESENTATIVE_SLACK = 0.10  # group-first comparison is this much looser (drift guard)
EXIF_MISMATCH_PENALTY = 0.10  # threshold increase when lens/focal/aperture disagree
FOCAL_TOLERANCE = 0.15       # relative focal-length difference treated as the same
APERTURE_TOLERANCE = 1.41    # f-number ratio (~1 stop) treated as the same
MIN_TIME_COVERAGE = 0.7
MAX_SAME_TIME_RATIO = 0.5
MIN_HINT_COVERAGE = 0.7
DEFAULT_THRESHOLD = 0.80


class GroupingMode(str, Enum):
    AUTO = "auto"
    TIME_FIRST = "time_first"
    SIMILARITY_ONLY = "similarity_only"


@dataclass(frozen=True)
class GroupingParams:
    mode: GroupingMode = GroupingMode.AUTO
    threshold: float = DEFAULT_THRESHOLD  # similarity >= threshold joins the same group
    time_gap: float = 2.0                 # seconds
    global_clustering: bool = False       # order-independent comparison against all groups
    use_exif_hints: bool = False          # focal length / lens / aperture consistency


@dataclass(frozen=True)
class ExifHints:
    focal: float | None = None     # mm, 0 / missing -> None
    lens: str | None = None
    aperture: float | None = None  # f-number


@dataclass(frozen=True)
class PhotoMeta:
    name: str
    signature: Signature
    taken: datetime | None = None
    hints: ExifHints | None = None


@dataclass(frozen=True)
class TimeTrust:
    trusted: bool
    reason: str = ""


@dataclass
class GroupingResult:
    groups: list[list[int]]  # indices into the input list
    time_trusted: bool
    message: str
    no_time_count: int = 0
    hints_used: bool = False


def threshold_from_slider(value: int) -> float:
    """Slider 0 (strict) .. 100 (loose) -> similarity threshold 0.95 .. 0.65."""
    value = max(0, min(100, value))
    return 0.95 - 0.30 * value / 100.0


def slider_from_threshold(threshold: float) -> int:
    return round(max(0.0, min(100.0, (0.95 - threshold) / 0.30 * 100.0)))


def natural_key(name: str) -> list:
    return [(0, int(t)) if t.isdigit() else (1, t.lower()) for t in re.split(r"(\d+)", name) if t]


def judge_time_trust(times: list[datetime | None]) -> TimeTrust:
    """Decide whether capture times are usable as a grouping aid.

    Untrusted when too few photos carry a time, or too many share one timestamp
    (e.g. film scans stamped with the scan time). Bursts legitimately share a second,
    so the criterion is the share of the single largest same-second bucket.
    """
    n = len(times)
    have = [t for t in times if t is not None]
    if n == 0 or len(have) < 2:
        return TimeTrust(False, "촬영 시각이 있는 사진이 부족합니다")
    if len(have) / n < MIN_TIME_COVERAGE:
        return TimeTrust(False, f"{n}장 중 {len(have)}장만 촬영 시각이 있습니다")
    biggest = Counter(have).most_common(1)[0][1]
    if len(set(have)) < 2 or biggest / len(have) > MAX_SAME_TIME_RATIO:
        return TimeTrust(False, f"{len(have)}장 중 {biggest}장이 같은 시각입니다")
    return TimeTrust(True)


def hints_consistent(metas: list[PhotoMeta]) -> bool:
    """EXIF hints are only used when most photos carry a focal length (manual lenses
    and scans usually do not, so their values would be noise)."""
    if not metas:
        return False
    have = sum(1 for m in metas if m.hints is not None and m.hints.focal)
    return have / len(metas) >= MIN_HINT_COVERAGE


def hints_mismatch(a: ExifHints | None, b: ExifHints | None) -> bool:
    """True when both photos report a value and the values clearly disagree."""
    if a is None or b is None:
        return False
    if a.focal and b.focal and abs(a.focal - b.focal) / max(a.focal, b.focal) > FOCAL_TOLERANCE:
        return True
    if a.lens and b.lens and a.lens != b.lens:
        return True
    if a.aperture and b.aperture:
        hi, lo = max(a.aperture, b.aperture), min(a.aperture, b.aperture)
        if hi / lo > APERTURE_TOLERANCE:
            return True
    return False


def _order(metas: list[PhotoMeta], use_time: bool) -> list[int]:
    idx = list(range(len(metas)))
    if use_time:
        far = datetime.max
        idx.sort(key=lambda i: (metas[i].taken or far, natural_key(metas[i].name)))
    else:
        idx.sort(key=lambda i: natural_key(metas[i].name))
    return idx


def group_photos(metas: list[PhotoMeta], params: GroupingParams) -> GroupingResult:
    """Split ``metas`` into groups (sequential neighbours, or globally if requested)."""
    no_time = sum(1 for m in metas if m.taken is None)
    trust = judge_time_trust([m.taken for m in metas])

    if params.mode == GroupingMode.SIMILARITY_ONLY:
        use_time, message = False, "시각 유사도만 사용해 그룹핑했습니다."
    elif params.mode == GroupingMode.TIME_FIRST:
        use_time, message = True, "촬영 시각을 우선해 그룹핑했습니다."
    elif trust.trusted:
        use_time, message = True, "촬영 시각을 보조 신호로 사용했습니다."
    else:
        use_time = False
        message = f"촬영 시각이 신뢰되지 않아 시각 유사도로 그룹핑했습니다. ({trust.reason})"

    use_hints = False
    if params.use_exif_hints:
        use_hints = hints_consistent(metas)
        message += (
            " EXIF(초점거리·렌즈·조리개)를 보조로 사용했습니다."
            if use_hints else " EXIF 값이 일관되지 않아 사용하지 않았습니다."
        )

    # time-first decides by time gaps only; a global search would not make sense
    use_global = params.global_clustering and params.mode != GroupingMode.TIME_FIRST
    if use_global:
        message += " (순서와 무관하게 전체에서 비교)"

    order = _order(metas, use_time)
    groups = (
        _group_global(metas, order, params, use_time, use_hints)
        if use_global
        else _group_sequential(metas, order, params, use_time, use_hints)
    )
    return GroupingResult(groups, use_time, message, no_time, use_hints)


def _group_sequential(metas, order, params, use_time, use_hints) -> list[list[int]]:
    groups: list[list[int]] = []
    for i in order:
        if groups:
            prev, first = metas[groups[-1][-1]], metas[groups[-1][0]]
            if _join_score(prev, first, metas[i], params, use_time, use_hints) is not None:
                groups[-1].append(i)
                continue
        groups.append([i])
    return groups


def _group_global(metas, order, params, use_time, use_hints) -> list[list[int]]:
    """Leader clustering: join the best-matching existing group, else start a new one."""
    groups: list[list[int]] = []
    for i in order:
        best, best_score = None, -1.0
        for g in groups:
            score = _join_score(metas[g[-1]], metas[g[0]], metas[i], params, use_time, use_hints)
            if score is not None and score > best_score:
                best, best_score = g, score
        if best is None:
            groups.append([i])
        else:
            best.append(i)
    return groups


def _join_score(
    prev: PhotoMeta, first: PhotoMeta, cur: PhotoMeta,
    params: GroupingParams, use_time: bool, use_hints: bool,
) -> float | None:
    """Similarity to the group's latest photo if ``cur`` may join, else None."""
    dt = None
    if use_time and prev.taken is not None and cur.taken is not None:
        dt = abs((cur.taken - prev.taken).total_seconds())

    if params.mode == GroupingMode.TIME_FIRST and dt is not None:
        return 1.0 if dt <= params.time_gap else None

    threshold = params.threshold
    if dt is not None and dt <= params.time_gap:
        threshold -= TIME_RELAX
    if use_hints and hints_mismatch(prev.hints, cur.hints):
        threshold += EXIF_MISMATCH_PENALTY

    s = similarity(prev.signature, cur.signature)
    if s < threshold:
        return None
    if similarity(first.signature, cur.signature) < threshold - REPRESENTATIVE_SLACK:
        return None
    return s
