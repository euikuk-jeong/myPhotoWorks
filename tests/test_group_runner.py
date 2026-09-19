import piexif
import pytest
from PIL import ImageFilter

from myphotoworks.core.grouping import GroupingMode
from myphotoworks.models.photo_item import PhotoItem
from myphotoworks.models.settings import AppSettings, CorrectionMode
from myphotoworks.processing.group_runner import Cancelled, run_grouping
from tests.test_grouping import scene


def save(path, seed, taken=None, blur=0.0):
    img = scene(seed)
    if blur:
        img = img.filter(ImageFilter.GaussianBlur(blur))
    kwargs = {}
    if taken:
        kwargs["exif"] = piexif.dump(
            {"Exif": {piexif.ExifIFD.DateTimeOriginal: taken.encode()}}
        )
    img.save(path, "JPEG", quality=95, **kwargs)
    return PhotoItem(path)


@pytest.fixture
def photos(tmp_path):
    return [
        save(tmp_path / "a1.jpg", 1, "2026:01:01 12:00:00"),
        save(tmp_path / "a2.jpg", 1, "2026:01:01 12:00:01", blur=3.0),
        save(tmp_path / "b1.jpg", 2, "2026:01:01 12:05:00"),
        save(tmp_path / "b2.jpg", 2, "2026:01:01 12:05:01", blur=0.8),
        save(tmp_path / "c1.jpg", 3, "2026:01:01 12:10:00"),
        save(tmp_path / "d1.jpg", 4, "2026:01:01 12:20:00"),
    ]


def test_end_to_end_groups_scores_and_recommends_sharper(photos):
    session, result = run_grouping(photos, AppSettings())
    names = [[p.source_path.name for p in g.photos] for g in session.groups()]
    assert names == [["a1.jpg", "a2.jpg"], ["b1.jpg", "b2.jpg"], ["c1.jpg"], ["d1.jpg"]]
    assert result.time_trusted
    a1, a2 = photos[0], photos[1]
    assert a1.is_recommended and not a2.is_recommended     # a2 is blurred
    assert a1.is_adopted and not a2.is_adopted
    assert all(p.scores is not None and p.reason for p in photos)
    assert session.adopted_count() == 4


def test_progress_reports_every_photo(photos):
    calls = []
    run_grouping(photos, AppSettings(), progress=lambda s, c, t: calls.append((c, t)))
    assert [c for c, _ in calls][:6] == [1, 2, 3, 4, 5, 6]
    assert all(t == 6 for _, t in calls)


def test_cancel_raises(photos):
    with pytest.raises(Cancelled):
        run_grouping(photos, AppSettings(), is_cancelled=lambda: True)


def test_regroup_reuses_cached_analysis_when_correction_unchanged(photos, monkeypatch):
    run_grouping(photos, AppSettings())
    import myphotoworks.processing.group_runner as gr

    def boom(*a, **k):
        raise AssertionError("should not decode again")

    monkeypatch.setattr(gr, "analyze_photo", boom)
    session, _ = run_grouping(photos, AppSettings(similarity_slider=20))  # threshold only
    assert session.group_count() >= 1


def test_correction_change_invalidates_cache(photos, monkeypatch):
    run_grouping(photos, AppSettings())
    import myphotoworks.processing.group_runner as gr

    seen = []
    real = gr.analyze_photo
    monkeypatch.setattr(gr, "analyze_photo", lambda *a, **k: seen.append(1) or real(*a, **k))
    run_grouping(photos, AppSettings(correction_mode=CorrectionMode.AUTO_LEVEL))
    assert len(seen) == 6


def test_corrupt_file_becomes_single_adopted_group(photos, tmp_path):
    bad = tmp_path / "bad.jpg"
    bad.write_bytes(b"junk")
    photos.append(PhotoItem(bad))
    session, _ = run_grouping(photos, AppSettings())
    bad_item = photos[-1]
    assert bad_item.scores is None
    assert session.group(bad_item.group_id).is_single
    assert bad_item.is_adopted            # never silently dropped
    assert bad_item.error_message


def test_similarity_only_mode_ignores_exif(tmp_path):
    ps = [save(tmp_path / "x1.jpg", 5), save(tmp_path / "x2.jpg", 5, blur=1.0),
          save(tmp_path / "y1.jpg", 6)]
    session, result = run_grouping(ps, AppSettings(grouping_mode=GroupingMode.SIMILARITY_ONLY))
    assert result.no_time_count == 3
    assert [len(g.photos) for g in session.groups()] == [2, 1]


def test_worker_emits_done_signal(photos, qtbot):
    from myphotoworks.workers.group_worker import GroupWorker

    w = GroupWorker(photos, AppSettings())
    with qtbot.waitSignal(w.done, timeout=10000) as blocker:
        w.start()
    session, result = blocker.args
    assert session.group_count() == 4
    w.wait()
