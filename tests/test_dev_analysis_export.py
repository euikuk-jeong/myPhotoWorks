"""Developer export — the label JSON also carries what the algorithm measured per photo.

``[채택 결과 내보내기 (개발)]`` writes ``groups[*].photos`` next to ``files``: one entry per photo
(same order) with the sentence, trace, facts, subject area, faces, tilt and the AF debug
(``exif_reader.read_af_debug``: raw Fujifilm values and the first check that failed), so a
review can be analysed from the JSON alone. Such a group also has its display ``number`` (the
"그룹 N" of the review window). Selection logs stay as they were (no analysis, no number).
"""
import json
from pathlib import Path

import pytest

from myphotoworks.models.group_session import GroupSession
from myphotoworks.models.photo_item import PhotoItem
from tests.synthetic import fuji_jpeg, person, scores


def _session(groups):
    photos, indexes, n = [], [], 0
    for group in groups:
        idx = []
        for s in group:
            item = PhotoItem(Path(f"p{n}.jpg"))
            item.scores = s
            photos.append(item)
            idx.append(n)
            n += 1
        indexes.append(idx)
    return GroupSession(photos, indexes, 1.0), photos


# ---- AF debug ---------------------------------------------------------------------------------

def _af(path):
    from myphotoworks.utils.exif_reader import read_af_debug

    return read_af_debug(path)


def test_af_debug_reads_the_raw_fuji_values(tmp_path):
    from myphotoworks.utils.exif_reader import read_af_point

    path = fuji_jpeg(tmp_path / "a.jpg", focus_pixel=(1200, 900))
    info = _af(path)
    assert info["make"] == "FUJIFILM" and info["focus_mode"] == 0
    assert info["focus_pixel"] == [1200, 900]
    assert info["exif_size"] == [4000, 3000] and info["actual_size"] == [512, 384]
    assert info["af_point"] == pytest.approx([0.3, 0.3])
    assert info["reason"] == "사용 가능"
    assert tuple(info["af_point"]) == read_af_point(path)      # the debug never disagrees


def test_af_debug_says_manual_focus(tmp_path):
    info = _af(fuji_jpeg(tmp_path / "m.jpg", focus_mode=1))
    assert info["focus_mode"] == 1 and info["af_point"] is None
    assert info["reason"] == "수동 초점(또는 동영상)"


def test_af_debug_says_no_focus_pixel(tmp_path):
    info = _af(fuji_jpeg(tmp_path / "n.jpg", focus_pixel=None))
    assert info["af_point"] is None and info["reason"] == "초점 좌표 없음"


def test_af_debug_says_cropped(tmp_path):
    info = _af(fuji_jpeg(tmp_path / "c.jpg", exif_size=(4000, 2000)))
    assert info["af_point"] is None and info["reason"] == "잘린(크롭) 사진"


def test_af_debug_says_point_outside_the_frame(tmp_path):
    info = _af(fuji_jpeg(tmp_path / "o.jpg", focus_pixel=(5000, 900)))
    assert info["af_point"] is None and info["reason"] == "초점 좌표가 프레임 밖"


def test_af_debug_says_not_fujifilm(tmp_path):
    info = _af(fuji_jpeg(tmp_path / "x.jpg", make=b"Canon"))
    assert info["make"] == "Canon" and info["reason"] == "Fujifilm이 아님"


def test_af_debug_never_raises(tmp_path):
    info = _af(tmp_path / "missing.jpg")
    assert info["af_point"] is None and info["reason"] == "EXIF를 읽지 못함"


# ---- group numbers and per-photo info ----------------------------------------------------------

def test_developer_labels_carry_the_display_number():
    session, _ = _session([[scores(70), scores(60)], [scores(70)], [scores(70), scores(60)]])
    groups = session.to_label_dict(photo_info=lambda p: {})["groups"]
    assert [g["number"] for g in groups] == [1, 3]      # the single photo is group 2


def test_labels_without_photo_info_are_unchanged():
    session, _ = _session([[scores(70), scores(60)]])
    group = session.to_label_dict()["groups"][0]
    assert set(group) == {"id", "files", "picked", "recommended", "reviewed", "edited"}


def test_photo_info_adds_one_entry_per_member_in_order():
    session, _ = _session([[scores(70), scores(60)]])
    seen = []

    def info(photo):
        seen.append(photo)
        return {"mark": photo.source_path.name}

    (group,) = session.to_label_dict(photo_info=info)["groups"]
    assert [p["file"] for p in group["photos"]] == group["files"]
    assert [p["mark"] for p in group["photos"]] == ["p0.jpg", "p1.jpg"]


# ---- the developer export ----------------------------------------------------------------------

def test_dev_export_adds_the_analysis_of_every_photo(tmp_path):
    from myphotoworks.dev.labels import write_labels

    shape = dict(subject_bbox=(10, 10, 140, 70), analysis_size=(400, 200), subject_source="face")
    session, _ = _session([[person(closed=1, tilt=4.0, **shape), person(closed=0, **shape)]])
    out = tmp_path / "labels.json"
    write_labels(session, out)
    (group,) = json.loads(out.read_text(encoding="utf-8"))["groups"]
    blinking, open_eyes = group["photos"]

    assert blinking["file"] == "p0.jpg" and blinking["scored"] is True
    assert blinking["recommended"] is False and blinking["adopted"] is False
    assert blinking["facts"] == ["눈 감음 1명", "기울어짐"]
    assert blinking["why"].startswith("눈 감은 사람이 1명이라 추천 사진(p1, 0명)")
    assert blinking["tilt"] == 4.0
    assert blinking["subject"]["source"] == "face"
    assert blinking["faces"]["closed_eyes"] == 1 and blinking["faces"]["count"] == 1
    assert blinking["boxes"][0]["source"] == "face"
    assert len(blinking["boxes"][0]["rect"]) == 4
    assert blinking["af"]["reason"] == "EXIF를 읽지 못함"            # p0.jpg does not exist
    assert blinking["trace"] and isinstance(blinking["trace"], list)

    assert open_eyes["recommended"] is True and open_eyes["adopted"] is True
    assert open_eyes["why"].startswith("눈 감은 사람이 가장 적어요")


def test_dev_export_notes_a_photo_that_was_not_analysed(tmp_path):
    from myphotoworks.dev.labels import write_labels

    session, photos = _session([[scores(70), scores(60)]])
    photos[1].scores = None
    out = tmp_path / "labels.json"
    write_labels(session, out)
    (group,) = json.loads(out.read_text(encoding="utf-8"))["groups"]
    assert group["photos"][1]["scored"] is False and "why" not in group["photos"][1]


def test_selection_log_has_no_per_photo_analysis(tmp_path):
    from myphotoworks.utils.selection_log import save_selection_log

    session, _ = _session([[scores(70), scores(60)]])
    session.mark_reviewed(session.groups()[0].id)           # a group that was opened
    path = save_selection_log(session, tmp_path)
    group = json.loads(path.read_text(encoding="utf-8"))["groups"][0]
    assert "photos" not in group and "number" not in group
