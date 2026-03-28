"""Unit tests for BatchWorker output path resolution and filename building."""
from pathlib import Path

import pytest
from PIL import Image

from myphotoworks.models.photo_item import PhotoItem
from myphotoworks.models.settings import AppSettings, OutputPathMode
from myphotoworks.workers.batch_worker import BatchWorker


def make_jpeg_file(tmp_path: Path, name: str = "photo.jpg") -> Path:
    path = tmp_path / name
    Image.new("RGB", (100, 50), (128, 128, 128)).save(path, format="JPEG")
    return path


def make_worker(photos, settings, first_file_dir=None):
    return BatchWorker(photos, settings, first_file_dir=first_file_dir)


class TestResolveOutputPath:
    def test_first_file_mode(self, tmp_path):
        photo_path = make_jpeg_file(tmp_path, "img.jpg")
        photo = PhotoItem(source_path=photo_path)
        settings = AppSettings(output_path_mode=OutputPathMode.FIRST_FILE)
        first_dir = tmp_path / "base"
        worker = make_worker([photo], settings, first_file_dir=first_dir)

        result = worker._resolve_output_path(photo)
        assert result == first_dir / "output" / "img.jpg"

    def test_per_file_mode(self, tmp_path):
        photo_path = make_jpeg_file(tmp_path, "img.jpg")
        photo = PhotoItem(source_path=photo_path)
        settings = AppSettings(output_path_mode=OutputPathMode.PER_FILE)
        worker = make_worker([photo], settings)

        result = worker._resolve_output_path(photo)
        assert result == tmp_path / "output" / "img.jpg"

    def test_custom_mode(self, tmp_path):
        photo_path = make_jpeg_file(tmp_path, "img.jpg")
        photo = PhotoItem(source_path=photo_path)
        custom_dir = tmp_path / "custom_out"
        settings = AppSettings(
            output_path_mode=OutputPathMode.CUSTOM,
            output_custom_dir=custom_dir,
        )
        worker = make_worker([photo], settings)

        result = worker._resolve_output_path(photo)
        assert result == custom_dir / "img.jpg"

    def test_prefix_applied(self, tmp_path):
        photo_path = make_jpeg_file(tmp_path, "shot.jpg")
        photo = PhotoItem(source_path=photo_path)
        settings = AppSettings(
            output_path_mode=OutputPathMode.PER_FILE,
            output_prefix="web_",
        )
        worker = make_worker([photo], settings)

        result = worker._resolve_output_path(photo)
        assert result.name == "web_shot.jpg"

    def test_suffix_applied(self, tmp_path):
        photo_path = make_jpeg_file(tmp_path, "shot.jpg")
        photo = PhotoItem(source_path=photo_path)
        settings = AppSettings(
            output_path_mode=OutputPathMode.PER_FILE,
            output_suffix="_resized",
        )
        worker = make_worker([photo], settings)

        result = worker._resolve_output_path(photo)
        assert result.name == "shot_resized.jpg"

    def test_prefix_and_suffix_combined(self, tmp_path):
        photo_path = make_jpeg_file(tmp_path, "shot.jpg")
        photo = PhotoItem(source_path=photo_path)
        settings = AppSettings(
            output_path_mode=OutputPathMode.PER_FILE,
            output_prefix="web_",
            output_suffix="_sm",
        )
        worker = make_worker([photo], settings)

        result = worker._resolve_output_path(photo)
        assert result.name == "web_shot_sm.jpg"


class TestBatchWorkerRun:
    def test_processes_all_photos(self, tmp_path):
        """전체 파일이 처리되고 output 폴더에 저장되어야 함."""
        paths = [make_jpeg_file(tmp_path, f"img{i}.jpg") for i in range(3)]
        photos = [PhotoItem(source_path=p) for p in paths]
        settings = AppSettings(output_path_mode=OutputPathMode.PER_FILE)

        worker = BatchWorker(photos, settings)
        worker.run()  # 동기 실행

        for p in paths:
            out = tmp_path / "output" / p.name
            assert out.exists(), f"{out} 가 존재해야 함"

    def test_progress_signal_count(self, tmp_path):
        """progress 시그널이 파일 수만큼 발생해야 함 (동기 run() 호출)."""
        paths = [make_jpeg_file(tmp_path, f"img{i}.jpg") for i in range(3)]
        photos = [PhotoItem(source_path=p) for p in paths]
        settings = AppSettings(output_path_mode=OutputPathMode.PER_FILE)

        worker = BatchWorker(photos, settings)
        progress_calls = []
        worker.progress.connect(lambda c, t: progress_calls.append((c, t)))

        worker.run()  # 동기 실행

        assert len(progress_calls) == 3
        assert progress_calls[-1] == (3, 3)
