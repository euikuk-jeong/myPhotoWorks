"""Run analysis + grouping over a photo list (GUI-free so it can be tested directly)."""
from __future__ import annotations

import dataclasses
import logging
from collections.abc import Callable

from PIL import Image

from myphotoworks.core.grouping import (
    GroupingParams,
    GroupingResult,
    PhotoMeta,
    group_photos,
    threshold_from_slider,
)
from myphotoworks.core.pipeline import analyze_photo
from myphotoworks.models.group_session import GroupSession
from myphotoworks.models.photo_item import PhotoItem
from myphotoworks.models.settings import AppSettings
from myphotoworks.processing import processor
from myphotoworks.utils.exif_reader import read_taken_at

logger = logging.getLogger(__name__)

ProgressCb = Callable[[str, int, int], None]


class Cancelled(Exception):
    pass


def correction_key(settings: AppSettings) -> tuple:
    """Settings that change exposure / colour scores (resize does not)."""
    return (settings.correction_mode, settings.recipe_name, settings.brightness, settings.contrast)


def params_from_settings(settings: AppSettings) -> GroupingParams:
    return GroupingParams(
        mode=settings.grouping_mode,
        threshold=threshold_from_slider(settings.similarity_slider),
        time_gap=settings.time_gap,
    )


def run_grouping(
    photos: list[PhotoItem],
    settings: AppSettings,
    progress: ProgressCb | None = None,
    is_cancelled: Callable[[], bool] | None = None,
) -> tuple[GroupSession, GroupingResult]:
    """Analyse (cached per correction settings), group, and return a fresh GroupSession.

    Photos that cannot be decoded become single ungrouped entries without scores.
    Raises Cancelled when ``is_cancelled`` turns true between photos.
    """
    key = correction_key(settings)
    scoring_settings = dataclasses.replace(settings, resize_enabled=False)

    def correct(img: Image.Image) -> Image.Image:
        return processor.process(PhotoItem(photos[0].source_path), scoring_settings,
                                 source_image=img)

    total = len(photos)
    failed: list[int] = []
    for n, photo in enumerate(photos, start=1):
        if is_cancelled and is_cancelled():
            raise Cancelled
        if progress:
            progress("축소본·촬영 시각 읽는 중", n, total)
        if photo.analysis is not None and photo.analysis_key == key:
            continue
        try:
            photo.analysis = analyze_photo(
                photo.source_path, read_taken_at(photo.source_path), correct
            )
            photo.analysis_key = key
        except Exception as e:  # unreadable / corrupt file
            logger.warning("analysis failed for %s: %s", photo.source_path, e)
            photo.analysis = None
            photo.analysis_key = None
            photo.error_message = str(e)
            failed.append(n - 1)

    ok = [i for i, p in enumerate(photos) if p.analysis is not None]
    metas = [
        PhotoMeta(photos[i].source_path.name, a.signature, a.taken)
        for i, a in ((i, photos[i].analysis) for i in ok)
    ]
    if progress:
        progress("그룹 묶는 중", total, total)
    result = group_photos(metas, params_from_settings(settings))
    groups = [[ok[j] for j in g] for g in result.groups] + [[i] for i in failed]
    result.groups = groups

    for p in photos:
        p.scores = p.analysis.scores if p.analysis is not None else None
        p.is_adopted = p.is_recommended = False
    session = GroupSession(photos, groups, settings.weights())
    return session, result
