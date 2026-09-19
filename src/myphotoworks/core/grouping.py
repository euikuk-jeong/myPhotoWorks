"""Sequential-neighbour grouping with optional capture-time assistance."""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from myphotoworks.core.similarity import Signature, similarity

TIME_RELAX = 0.08            # threshold relief when timestamps are close and trusted
REPRESENTATIVE_SLACK = 0.10  # group-first comparison is this much looser (drift guard)
MIN_TIME_COVERAGE = 0.7
MAX_SAME_TIME_RATIO = 0.5
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


@dataclass(frozen=True)
class PhotoMeta:
    name: str
    signature: Signature
    taken: datetime | None = None


@dataclass(frozen=True)
class TimeTrust:
    trusted: bool
    reason: str = ""


@dataclass
class GroupingResult:
    groups: list[list[int]]  # indices into the input list, in processing order
    time_trusted: bool
    message: str
    no_time_count: int = 0


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


def _order(metas: list[PhotoMeta], use_time: bool) -> list[int]:
    idx = list(range(len(metas)))
    if use_time:
        far = datetime.max
        idx.sort(key=lambda i: (metas[i].taken or far, natural_key(metas[i].name)))
    else:
        idx.sort(key=lambda i: natural_key(metas[i].name))
    return idx


def group_photos(metas: list[PhotoMeta], params: GroupingParams) -> GroupingResult:
    """Split ``metas`` into groups by comparing sequential neighbours."""
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

    groups: list[list[int]] = []
    for i in _order(metas, use_time):
        if groups:
            prev = metas[groups[-1][-1]]
            first = metas[groups[-1][0]]
            if _same_group(prev, first, metas[i], params, use_time):
                groups[-1].append(i)
                continue
        groups.append([i])

    return GroupingResult(groups, use_time, message, no_time)


def _same_group(
    prev: PhotoMeta, first: PhotoMeta, cur: PhotoMeta, params: GroupingParams, use_time: bool
) -> bool:
    dt = None
    if use_time and prev.taken is not None and cur.taken is not None:
        dt = abs((cur.taken - prev.taken).total_seconds())

    if params.mode == GroupingMode.TIME_FIRST and dt is not None:
        return dt <= params.time_gap

    threshold = params.threshold
    if dt is not None and dt <= params.time_gap:
        threshold -= TIME_RELAX
    if similarity(prev.signature, cur.signature) < threshold:
        return False
    return similarity(first.signature, cur.signature) >= threshold - REPRESENTATIVE_SLACK
