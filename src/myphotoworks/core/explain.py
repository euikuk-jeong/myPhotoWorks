"""Explaining a recommendation to the user (pure, no Qt).

* ``subject_overlay``: where the algorithm measured a photo, as boxes in shares of the frame.
  ``subject_bbox`` and the face boxes live in the pixel grid of the analysis copy
  (``QualityScores.analysis_size``). The review preview shows a photo at any size, so the boxes are
  handed over as ``(x0, y0, x1, y1)`` shares of the width and height (0..1). ``source`` says where
  the area came from ("face", "af", "sharpest", "center"): the view picks colour and line style
  from it, and only the first box of a photo carries text, so several faces stay quiet.
* ``explain_photo``: one sentence on why a photo is (not) recommended, the step-by-step trace
  for a tooltip, and facts about the photo. Built on ``ranking.chain_trace``.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from myphotoworks.core.ranking import (
    CLOSED_EYES,
    COLOR,
    COLOR_IGNORE_BELOW,
    COMPOSITION,
    CRITERION_LABELS,
    EXPOSURE_FAIL,
    FACE_DETECTED,
    FACE_EXPOSURE,
    FACE_SHARPNESS,
    SHARPNESS_FAIL,
    SMILE,
    SMILE_PRESENT_TH,
    SUBJECT_EXPOSURE,
    SUBJECT_SHARPNESS,
    ChainTrace,
    Criterion,
    TraceStep,
    chain_trace,
    face_badges,
    is_person_group,
    sensitivity_label,
    tilt_badges,
)
from myphotoworks.core.scoring import QualityScores, is_blurry

Rect = tuple[float, float, float, float]

_SOURCE_LABELS = {
    "face": "얼굴",
    "af": "AF 포인트",
    "sharpest": "가장 선명한 영역",
    "center": "중앙 (주제를 찾지 못해 중앙 사용)",
}
_UNKNOWN_LABEL = "측정 영역"


@dataclass(frozen=True)
class OverlayBox:
    label: str      # text for the view; empty on all but the first box of a photo
    rect: Rect      # (x0, y0, x1, y1) in shares of the frame, 0..1
    source: str     # SubjectRegion source the area came from


def _share(box: tuple[float, float, float, float], size: tuple[int, int]) -> Rect | None:
    """``box`` (pixels of the analysis copy) as shares of ``size``, clamped to the frame;
    ``None`` when nothing of it is left."""
    w, h = size
    if w <= 0 or h <= 0:
        return None
    x0, y0, x1, y1 = box
    rect = (min(1.0, max(0.0, x0 / w)), min(1.0, max(0.0, y0 / h)),
            min(1.0, max(0.0, x1 / w)), min(1.0, max(0.0, y1 / h)))
    return rect if rect[2] > rect[0] and rect[3] > rect[1] else None


def subject_overlay(scores: QualityScores | None) -> list[OverlayBox]:
    """The boxes to draw for one photo: each main face when the subject is the faces, else the
    one measured area. Empty when nothing was measured or the analysis size is unknown."""
    if scores is None or scores.analysis_size is None or scores.subject_bbox is None:
        return []
    size = scores.analysis_size
    source = scores.subject_source
    label = _SOURCE_LABELS.get(source, _UNKNOWN_LABEL)
    if source == "face" and scores.faces is not None and scores.faces.boxes:
        rects = [r for r in (_share(b, size) for b in scores.faces.boxes) if r is not None]
        if len(rects) > 1:
            label = f"{label} {len(rects)}명"
        return [OverlayBox(label if i == 0 else "", r, source) for i, r in enumerate(rects)]
    rect = _share(scores.subject_bbox, size)
    return [OverlayBox(label, rect, source)] if rect is not None else []


# ---- one sentence on why ----------------------------------------------------------------------


@dataclass(frozen=True)
class Explanation:
    headline: str                   # the sentence
    trace_lines: tuple[str, ...]    # one line per visible step of the chain (tooltip)
    facts: tuple[str, ...]          # facts about this photo (second line)


def _points(v: float) -> str:
    return f"{v:.0f}점"


def _people(v: float) -> str:
    return f"{v:.0f}명"


def _percent(v: float) -> str:
    return f"{v * 100:.0f}%"


# deciding criterion -> (sentence for the recommended photo, formatter of the values)
_WINS = {
    "subject_sharpness": ("주제 선명도가 가장 높아요", _points),
    "subject_exposure": ("주제 노출이 가장 적정해요", _points),
    "composition": ("구도 점수가 가장 높아요", _points),
    "color": ("색감이 가장 풍부해요", _points),
    "closed_eyes": ("눈 감은 사람이 가장 적어요", _people),
    "smile": ("웃음이 가장 뚜렷해요", _percent),
    "face_sharpness": ("얼굴 선명도가 가장 높아요", _points),
    "face_exposure": ("얼굴 노출이 가장 적정해요", _points),
}
# criterion a photo dropped out on -> (what is lower than the recommended photo's, formatter)
_LOSSES = {
    "subject_sharpness": ("주제 선명도가 낮아요", _points),
    "subject_exposure": ("주제 노출 점수가 낮아요", _points),
    "composition": ("구도 점수가 낮아요", _points),
    "color": ("색감이 덜 풍부해요", _points),
    "smile": ("웃음이 약해요", _percent),
    "face_sharpness": ("얼굴 선명도가 낮아요", _points),
    "face_exposure": ("얼굴 노출 점수가 낮아요", _points),
}
_LOWER_IS_BETTER = {"closed_eyes"}


def _hidden(step: TraceStep) -> bool:
    """A step with nothing to tell: nobody loses composition points, everybody has a face."""
    if step.name == "composition":
        return all(v >= 100.0 - 1e-9 for v in step.values.values())
    if step.name == "face_detected":
        return all(v >= 1.0 for v in step.values.values())
    return False


def _runner_up(step: TraceStep, winner: int) -> int:
    """The best photo besides the winner among those that were in the race at this step."""
    sign = 1.0 if step.name in _LOWER_IS_BETTER else -1.0
    return min((i for i in step.alive_before if i != winner),
               key=lambda i: (sign * step.values[i], i))


def _winner_sentence(trace: ChainTrace, names: Sequence[str]) -> str:
    if trace.deciding == "gate":
        what = "얼굴이" if trace.person else "주제가"
        return f"나머지 사진은 {what} 너무 어둡거나 흐려서 이 사진을 추천해요"
    if trace.tie:
        return "모든 기준에서 차이가 작아요(차이 미미). 종합 점수가 가장 높은 사진이에요"
    step = trace.steps[-1]
    if step.name == "face_detected":
        return "얼굴이 인식된 사진은 이것뿐이에요"
    text, fmt = _WINS[step.name]
    other = _runner_up(step, trace.winner)
    earlier = [s.label for s in trace.steps[:-1] if not _hidden(s)]
    prefix = f"앞선 기준({', '.join(earlier)})이 비슷해 " if earlier else ""
    return (f"{prefix}{text} — {fmt(step.values[trace.winner])}, "
            f"다음 사진({names[other]})은 {fmt(step.values[other])}")


def _loser_sentence(trace: ChainTrace, index: int, names: Sequence[str]) -> str:
    if index not in trace.pool:
        what = "얼굴이" if trace.person else "주제가"
        return f"{what} 너무 어둡거나 디테일이 없어 후보에서 제외됐어요"
    winner = names[trace.winner]
    step = next((s for s in trace.steps
                 if index in s.alive_before and index not in s.alive_after), None)
    if step is None:
        return f"차이는 작지만 종합 점수가 추천 사진({winner})보다 낮아요"
    mine, best = step.values[index], step.values[trace.winner]
    if step.name == "face_detected":
        return "얼굴이 인식되지 않아 얼굴이 인식된 사진보다 밀려요"
    if step.name == "closed_eyes":
        return f"눈 감은 사람이 {mine:.0f}명이라 추천 사진({winner}, {best:.0f}명)보다 밀려요"
    text, fmt = _LOSSES[step.name]
    return f"추천 사진({winner})보다 {text} — {fmt(mine)} vs {fmt(best)}"


def _allowance_text(name: str, allowance: float, relative: bool) -> str:
    """The deadband of a criterion as the user reads it: a share, points, or exact match."""
    if allowance == 0:
        return "같은 값만"
    if relative or name == "smile":
        return f"허용폭 {allowance * 100:g}%"
    return f"허용폭 {allowance:g}점"


def _allowance(step: TraceStep) -> str:
    return _allowance_text(step.name, step.allowance, step.relative)


def _trace_lines(trace: ChainTrace, group_size: int) -> tuple[str, ...]:
    lines: list[str] = []
    if trace.gated:
        what = "얼굴이" if trace.person else "주제가"
        lines.append(
            f"실패 사진 제외: {what} 너무 어둡거나 흐린 사진 {group_size - len(trace.pool)}장")
    shown = [s for s in trace.steps if not _hidden(s)]
    for k, step in enumerate(shown, start=1):
        lines.append(f"{k}. {step.label}: {len(step.alive_before)}장 중 "
                     f"{len(step.alive_after)}장 남음 ({_allowance(step)})")
    if trace.tie:
        lines.append("모든 기준이 동점이라 종합 점수로 정했어요")
    return tuple(lines)


def photo_facts(group: Sequence[QualityScores], index: int) -> tuple[str, ...]:
    """What is notable about ``group[index]`` itself: closed eyes, faces cut by the frame, no face
    (person group), tilted lines, blur. One source for the review window's second line and the
    badges on the cards."""
    s = group[index]
    facts: list[str] = []
    if len(group) > 1 and is_person_group(group):
        facts += face_badges(s)
    if len(group) > 1:
        facts += tilt_badges(s)
    if is_blurry(s, list(group)):
        facts.append("흐림")
    return tuple(facts)


def explain_photo(
    group: Sequence[QualityScores],
    index: int,
    names: Sequence[str],
    deadband_scale: float = 1.0,
) -> Explanation:
    """Why ``group[index]`` is (not) the recommended photo. ``names`` are the display names of
    the photos of ``group``, in the same order; ``deadband_scale`` is the session's sensitivity."""
    trace = chain_trace(group, deadband_scale)
    if len(group) == 1:
        headline = "그룹에 이 사진 하나뿐이에요"
    elif index == trace.winner:
        headline = _winner_sentence(trace, names)
    else:
        headline = _loser_sentence(trace, index, names)
    return Explanation(headline, _trace_lines(trace, len(group)), photo_facts(group, index))


def _name_list(names: Sequence[str]) -> str:
    """At most four names, then how many more."""
    shown = ", ".join(names[:4])
    return f"{shown} 외 {len(names) - 4}장" if len(names) > 4 else shown


def group_walkthrough(
    group: Sequence[QualityScores], names: Sequence[str], deadband_scale: float = 1.0
) -> tuple[str, ...]:
    """How the chain went through this group, for the "추천 방식" dialog: the photos the failure
    gate removed, one line per visible step with the photos still in the race, then the result.
    Same ``chain_trace`` as the sentence and the tooltip; empty for a single photo."""
    if len(group) < 2:
        return ()
    trace = chain_trace(group, deadband_scale)
    lines: list[str] = []
    if trace.gated:
        removed = [names[i] for i in range(len(group)) if i not in trace.pool]
        what = "얼굴이" if trace.person else "주제가"
        lines.append(f"실패 사진 제외: {what} 너무 어둡거나 흐린 사진 {len(removed)}장 — "
                     f"{_name_list(removed)}")
    shown = [s for s in trace.steps if not _hidden(s)]
    for k, step in enumerate(shown, start=1):
        lines.append(f"{k}. {step.label}: {len(step.alive_before)}장 중 "
                     f"{len(step.alive_after)}장 남음 ({_allowance(step)}) — "
                     f"{_name_list([names[i] for i in step.alive_after])}")
    winner = names[trace.winner]
    if trace.tie:
        lines.append(f"→ 추천: {winner} (종합 점수)")
    elif trace.deciding == "gate":
        lines.append(f"→ 추천: {winner} (나머지는 후보에서 제외)")
    else:
        lines.append(f"→ 추천: {winner}")
    return tuple(lines)


# ---- how the recommendation works ("추천 방식") -------------------------------------------------


@dataclass(frozen=True)
class Overview:
    title: str
    steps: tuple[str, ...]      # the chain in order, with each deadband
    notes: tuple[str, ...]      # the rules around it: tie, failure gate, sensitivity ...


_GENERAL_CHAIN = (SUBJECT_SHARPNESS, SUBJECT_EXPOSURE, COMPOSITION, COLOR)
_PERSON_CHAIN = (FACE_DETECTED, CLOSED_EYES, SMILE, FACE_SHARPNESS, FACE_EXPOSURE, COMPOSITION)


def _describe(c: Criterion, scale: float) -> str:
    if c.name == "face_detected":
        return "얼굴이 인식된 사진 우선"
    if c.name == "closed_eyes":
        return "같은 값만 (적을수록 좋아요)"
    return _allowance_text(c.name, c.deadband * scale, c.relative)


def chain_overview(person: bool, deadband_scale: float = 1.0) -> Overview:
    """The criteria ``recommend`` compares, in order, with their deadbands at this sensitivity,
    and the rules around them. Written from the same criteria and constants the algorithm uses."""
    chain = _PERSON_CHAIN if person else _GENERAL_CHAIN
    steps = tuple(f"{k}. {CRITERION_LABELS[c.name]} — {_describe(c, deadband_scale)}"
                  for k, c in enumerate(chain, start=1))
    what = "얼굴이" if person else "주제가"
    mix = "얼굴 선명도·얼굴 노출·웃음" if person else "선명도·노출·색감"
    if person:
        special = (f"웃음은 그룹 안에 웃음 {SMILE_PRESENT_TH * 100:g}% 이상인 사람이 있을 때만 "
                   "비교해요.")
    else:
        special = (f"색감이 {COLOR_IGNORE_BELOW:g}점 미만인 흑백에 가까운 그룹에서는 색감 기준을 "
                   "건너뛰어요.")
    notes = (
        "앞 기준에서 1등과의 차이가 허용폭 안이면 동점으로 보고 다음 기준으로 넘어가요. "
        "한 사진만 남는 기준이 그 사진을 추천한 이유예요.",
        f"끝까지 동점이면 '차이 미미'로 보고, {mix}을 섞은 종합 점수가 가장 높은 사진을 추천해요.",
        f"{what} 너무 어둡거나 날아가거나(노출 {EXPOSURE_FAIL:g}점 미만) 디테일이 거의 없는"
        f"(선명도 {SHARPNESS_FAIL:g}점 미만) 사진은, 성한 사진이 있으면 후보에서 빼요.",
        special,
        f"허용폭은 '추천 민감도'로 조절해요. 지금은 {sensitivity_label(deadband_scale)}이에요 "
        "(낮음은 넓게, 높음은 좁게).",
        "점수를 잰 영역은 '측정 영역 보기'로 사진 위에서 확인할 수 있어요.",
    )
    return Overview("인물 그룹의 추천 순서" if person else "일반 그룹의 추천 순서", steps, notes)
