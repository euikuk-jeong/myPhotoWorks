"""Unit tests for PreviewWindow — keyboard shortcuts, saved_count, completion dialog,
event filter routing, and prefetch cache.

GUI 테스트는 pytest-qt의 qapp fixture를 통해 QApplication 인스턴스를 공급받는다.
PreviewWindow는 show() 없이 생성하므로 _load_current()는 호출되지 않는다.
이미지 처리가 필요한 경로는 processor를 mock 처리한다.
"""
from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image, ImageOps
from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import QComboBox, QSlider, QSpinBox

from myphotoworks.models.photo_item import PhotoItem
from myphotoworks.models.settings import AppSettings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_jpeg(tmp_path: Path, name: str = "photo.jpg") -> Path:
    path = tmp_path / name
    Image.new("RGB", (100, 50), (128, 128, 128)).save(path, format="JPEG")
    return path


def make_key_event(key: Qt.Key) -> QKeyEvent:
    return QKeyEvent(QEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def photos(tmp_path):
    return [PhotoItem(source_path=make_jpeg(tmp_path, f"img{i}.jpg")) for i in range(3)]


@pytest.fixture
def window(qapp, photos):
    """PreviewWindow를 show 없이 생성. _load_current()는 실행되지 않는다."""
    settings = AppSettings()
    fake_img = Image.new("RGB", (100, 50))
    with (
        patch("myphotoworks.ui.preview_window.processor.process", return_value=fake_img),
        patch("myphotoworks.ui.preview_window.processor.save"),
    ):
        from myphotoworks.ui.preview_window import PreviewWindow
        win = PreviewWindow(photos, settings)
        yield win
        win.close()


# ---------------------------------------------------------------------------
# Tests — _saved_count
# ---------------------------------------------------------------------------

class TestSavedCount:
    def test_initial_saved_count_is_zero(self, window):
        assert window._saved_count == 0

    def test_saved_count_increments_on_save(self, window):
        fake_img = Image.new("RGB", (100, 50))
        with (
            patch("myphotoworks.ui.preview_window.processor.process", return_value=fake_img),
            patch("myphotoworks.ui.preview_window.processor.save"),
            patch("myphotoworks.ui.preview_window.QMessageBox.information"),
        ):
            window._save_and_advance(window._base_settings, apply_effects=False)
            assert window._saved_count == 1

    def test_saved_count_does_not_increment_on_error(self, window):
        with (
            patch(
                "myphotoworks.ui.preview_window.processor.process",
                side_effect=RuntimeError("처리 오류"),
            ),
            patch("myphotoworks.ui.preview_window.QMessageBox.information"),
        ):
            window._save_and_advance(window._base_settings, apply_effects=False)
            assert window._saved_count == 0


# ---------------------------------------------------------------------------
# Tests — completion dialog (_advance at last photo)
# ---------------------------------------------------------------------------

class TestCompletionDialog:
    def test_dialog_shown_at_last_photo(self, window):
        window._index = len(window._photos) - 1  # 마지막 사진으로 이동
        with patch("myphotoworks.ui.preview_window.QMessageBox.information") as mock_dlg:
            window._advance()
            mock_dlg.assert_called_once()

    def test_dialog_message_contains_total_and_saved(self, window):
        window._index = len(window._photos) - 1
        window._saved_count = 2
        total = len(window._photos)
        with patch("myphotoworks.ui.preview_window.QMessageBox.information") as mock_dlg:
            window._advance()
            _parent, _title, msg = mock_dlg.call_args.args
            assert str(total) in msg
            assert "2" in msg

    def test_no_dialog_when_not_at_last_photo(self, window):
        window._index = 0
        fake_img = Image.new("RGB", (100, 50))
        with (
            patch("myphotoworks.ui.preview_window.processor.process", return_value=fake_img),
            patch("myphotoworks.ui.preview_window.processor.save"),
            patch("myphotoworks.ui.preview_window.QMessageBox.information") as mock_dlg,
        ):
            window._advance()
            mock_dlg.assert_not_called()


# ---------------------------------------------------------------------------
# Tests — keyboard shortcuts (keyPressEvent)
# ---------------------------------------------------------------------------

class TestKeyboardShortcuts:
    def test_backtick_calls_go_prev(self, window):
        window._index = 1
        window.keyPressEvent(make_key_event(Qt.Key.Key_QuoteLeft))
        assert window._index == 0

    def test_key4_calls_go_next(self, window):
        window._index = 0
        fake_img = Image.new("RGB", (100, 50))
        with (
            patch("myphotoworks.ui.preview_window.processor.process", return_value=fake_img),
            patch("myphotoworks.ui.preview_window.processor.save"),
        ):
            window.keyPressEvent(make_key_event(Qt.Key.Key_4))
        assert window._index == 1

    def test_left_arrow_calls_go_prev(self, window):
        window._index = 2
        fake_img = Image.new("RGB", (100, 50))
        with (
            patch("myphotoworks.ui.preview_window.processor.process", return_value=fake_img),
            patch("myphotoworks.ui.preview_window.processor.save"),
        ):
            window.keyPressEvent(make_key_event(Qt.Key.Key_Left))
        assert window._index == 1

    def test_right_arrow_calls_go_next(self, window):
        window._index = 0
        fake_img = Image.new("RGB", (100, 50))
        with (
            patch("myphotoworks.ui.preview_window.processor.process", return_value=fake_img),
            patch("myphotoworks.ui.preview_window.processor.save"),
        ):
            window.keyPressEvent(make_key_event(Qt.Key.Key_Right))
        assert window._index == 1

    def test_space_calls_skip(self, window):
        """Space는 스킵(다음으로 이동)이어야 함."""
        window._index = 0
        fake_img = Image.new("RGB", (100, 50))
        with (
            patch("myphotoworks.ui.preview_window.processor.process", return_value=fake_img),
            patch("myphotoworks.ui.preview_window.processor.save"),
        ):
            window.keyPressEvent(make_key_event(Qt.Key.Key_Space))
        assert window._index == 1

    def test_backtick_does_not_go_below_zero(self, window):
        window._index = 0
        window.keyPressEvent(make_key_event(Qt.Key.Key_QuoteLeft))
        assert window._index == 0

    def test_key4_does_not_exceed_last(self, window):
        window._index = len(window._photos) - 1
        with patch("myphotoworks.ui.preview_window.QMessageBox.information"):
            window.keyPressEvent(make_key_event(Qt.Key.Key_4))
        assert window._index == len(window._photos) - 1

    def test_key1_triggers_save_before(self, window):
        """1키는 apply_effects=False로 저장 후 processor.save를 호출해야 함."""
        fake_img = Image.new("RGB", (100, 50))
        with (
            patch("myphotoworks.ui.preview_window.processor.process", return_value=fake_img),
            patch("myphotoworks.ui.preview_window.processor.save") as mock_save,
        ):
            window.keyPressEvent(make_key_event(Qt.Key.Key_1))
            mock_save.assert_called_once()

    def test_key2_triggers_save_after_a(self, window):
        """2키는 저장 후 processor.save를 호출해야 함."""
        fake_img = Image.new("RGB", (100, 50))
        with (
            patch("myphotoworks.ui.preview_window.processor.process", return_value=fake_img),
            patch("myphotoworks.ui.preview_window.processor.save") as mock_save,
        ):
            window.keyPressEvent(make_key_event(Qt.Key.Key_2))
            mock_save.assert_called_once()

    def test_key3_triggers_save_after_b(self, window):
        """3키는 저장 후 processor.save를 호출해야 함."""
        fake_img = Image.new("RGB", (100, 50))
        with (
            patch("myphotoworks.ui.preview_window.processor.process", return_value=fake_img),
            patch("myphotoworks.ui.preview_window.processor.save") as mock_save,
        ):
            window.keyPressEvent(make_key_event(Qt.Key.Key_3))
            mock_save.assert_called_once()


# ---------------------------------------------------------------------------
# Tests — event filter routing
# ---------------------------------------------------------------------------

class TestEventFilter:
    def _make_key_event(self, key: Qt.Key) -> QKeyEvent:
        return QKeyEvent(QEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier)

    def test_e_key_always_intercepted(self, window):
        """E 키는 어떤 자식 위젯에 포커스가 있어도 PreviewWindow로 전달되어야 함."""
        child = QSlider(window)  # 임의의 자식 위젯
        event = self._make_key_event(Qt.Key.Key_E)
        with patch.object(window, "keyPressEvent") as mock_kpe:
            result = window.eventFilter(child, event)
        assert result is True
        mock_kpe.assert_called_once_with(event)

    def test_home_key_always_intercepted(self, window):
        child = QSpinBox(window)
        event = self._make_key_event(Qt.Key.Key_Home)
        with patch.object(window, "keyPressEvent") as mock_kpe:
            result = window.eventFilter(child, event)
        assert result is True
        mock_kpe.assert_called_once_with(event)

    def test_left_key_intercepted_on_non_slider(self, window):
        """Left 키는 QSlider 이외의 자식에서 PreviewWindow로 전달되어야 함."""
        child = QComboBox(window)
        event = self._make_key_event(Qt.Key.Key_Left)
        with patch.object(window, "keyPressEvent") as mock_kpe:
            result = window.eventFilter(child, event)
        assert result is True
        mock_kpe.assert_called_once_with(event)

    def test_left_key_passes_through_on_slider(self, window):
        """Left 키는 QSlider에서는 통과되어야 함 (슬라이더 조절 허용)."""
        child = QSlider(window)
        event = self._make_key_event(Qt.Key.Key_Left)
        with patch.object(window, "keyPressEvent") as mock_kpe:
            result = window.eventFilter(child, event)
        assert result is False
        mock_kpe.assert_not_called()

    def test_backtick_intercepted_on_non_slider(self, window):
        """` 키는 QSlider 이외의 자식에서 PreviewWindow로 전달되어야 함."""
        child = QComboBox(window)
        event = self._make_key_event(Qt.Key.Key_QuoteLeft)
        with patch.object(window, "keyPressEvent") as mock_kpe:
            result = window.eventFilter(child, event)
        assert result is True
        mock_kpe.assert_called_once_with(event)

    def test_key4_passes_through_on_spinbox(self, window):
        """4 키는 QSpinBox에서는 통과되어야 함 (숫자 입력 허용)."""
        child = QSpinBox(window)
        event = self._make_key_event(Qt.Key.Key_4)
        with patch.object(window, "keyPressEvent") as mock_kpe:
            result = window.eventFilter(child, event)
        assert result is False
        mock_kpe.assert_not_called()

    def test_key4_intercepted_on_non_input_widget(self, window):
        """4 키는 QSpinBox/QComboBox 이외의 자식에서 PreviewWindow로 전달되어야 함."""
        child = QSlider(window)
        event = self._make_key_event(Qt.Key.Key_4)
        with patch.object(window, "keyPressEvent") as mock_kpe:
            result = window.eventFilter(child, event)
        assert result is True
        mock_kpe.assert_called_once_with(event)

    def test_space_passes_through_on_combobox(self, window):
        """Space 키는 QComboBox에서는 통과되어야 함 (드롭다운 허용)."""
        child = QComboBox(window)
        event = self._make_key_event(Qt.Key.Key_Space)
        with patch.object(window, "keyPressEvent") as mock_kpe:
            result = window.eventFilter(child, event)
        assert result is False
        mock_kpe.assert_not_called()

    def test_non_child_widget_not_intercepted(self, window, qapp):
        """PreviewWindow의 자식이 아닌 위젯의 키 이벤트는 가로채지 않아야 함."""
        external = QSlider()  # 부모 없음 → window의 자식이 아님
        event = self._make_key_event(Qt.Key.Key_E)
        with patch.object(window, "keyPressEvent") as mock_kpe:
            result = window.eventFilter(external, event)
        assert result is False
        mock_kpe.assert_not_called()
        external.deleteLater()


# ---------------------------------------------------------------------------
# Tests — preview downsampling
# ---------------------------------------------------------------------------

class TestMakePreviewImage:
    def test_large_image_downsampled(self, qapp):
        """큰 이미지는 long side가 _PREVIEW_MAX_PX 이하로 축소."""
        from myphotoworks.ui.preview_window import PreviewWindow
        img = Image.new("RGB", (7728, 5152))
        result = PreviewWindow._make_preview_image(img)
        assert max(result.size) <= PreviewWindow._PREVIEW_MAX_PX
        # aspect ratio preserved
        assert abs(result.width / result.height - 7728 / 5152) < 0.01

    def test_small_image_unchanged(self, qapp):
        """_PREVIEW_MAX_PX 이하 이미지는 그대로 반환."""
        from myphotoworks.ui.preview_window import PreviewWindow
        img = Image.new("RGB", (800, 600))
        result = PreviewWindow._make_preview_image(img)
        assert result is img  # same object, no copy

    def test_portrait_image_downsampled(self, qapp):
        """세로 이미지도 long side 기준으로 축소."""
        from myphotoworks.ui.preview_window import PreviewWindow
        img = Image.new("RGB", (3000, 5000))
        result = PreviewWindow._make_preview_image(img)
        assert max(result.size) <= PreviewWindow._PREVIEW_MAX_PX
        assert result.height == PreviewWindow._PREVIEW_MAX_PX


# ---------------------------------------------------------------------------
# Tests — _PrefetchCache
# ---------------------------------------------------------------------------

class TestPrefetchCache:
    def test_cache_miss_returns_none(self):
        from myphotoworks.ui.preview_window import _PrefetchCache
        cache = _PrefetchCache(preview_max_px=1600)
        assert cache.get(Path("nonexistent.jpg")) is None

    def test_prefetch_loads_image(self, tmp_path):
        from myphotoworks.ui.preview_window import _PrefetchCache
        path = tmp_path / "test.jpg"
        Image.new("RGB", (200, 100), (255, 0, 0)).save(path, format="JPEG")

        cache = _PrefetchCache(preview_max_px=1600)
        cache.prefetch([path])

        # Wait for background thread to finish
        for _ in range(50):
            if cache.get(path) is not None:
                break
            time.sleep(0.05)

        result = cache.get(path)
        assert result is not None
        original, preview = result
        assert original.size == (200, 100)
        assert preview is original  # small image, no downsample needed

    def test_prefetch_downsamples_large_image(self, tmp_path):
        from myphotoworks.ui.preview_window import _PrefetchCache
        path = tmp_path / "big.jpg"
        Image.new("RGB", (4000, 3000)).save(path, format="JPEG")

        cache = _PrefetchCache(preview_max_px=1600)
        cache.prefetch([path])

        for _ in range(50):
            if cache.get(path) is not None:
                break
            time.sleep(0.05)

        result = cache.get(path)
        assert result is not None
        original, preview = result
        assert original.size == (4000, 3000)
        assert max(preview.size) <= 1600

    def test_eviction_removes_stale_entries(self, tmp_path):
        from myphotoworks.ui.preview_window import _PrefetchCache
        path_a = tmp_path / "a.jpg"
        path_b = tmp_path / "b.jpg"
        Image.new("RGB", (100, 100)).save(path_a, format="JPEG")
        Image.new("RGB", (100, 100)).save(path_b, format="JPEG")

        cache = _PrefetchCache(preview_max_px=1600)
        cache.prefetch([path_a])

        for _ in range(50):
            if cache.get(path_a) is not None:
                break
            time.sleep(0.05)
        assert cache.get(path_a) is not None

        # Prefetching only path_b should evict path_a
        cache.prefetch([path_b])

        for _ in range(50):
            if cache.get(path_b) is not None:
                break
            time.sleep(0.05)

        assert cache.get(path_a) is None
        assert cache.get(path_b) is not None

    def test_clear_empties_cache(self, tmp_path):
        from myphotoworks.ui.preview_window import _PrefetchCache
        path = tmp_path / "test.jpg"
        Image.new("RGB", (100, 100)).save(path, format="JPEG")

        cache = _PrefetchCache(preview_max_px=1600)
        cache.prefetch([path])

        for _ in range(50):
            if cache.get(path) is not None:
                break
            time.sleep(0.05)

        cache.clear()
        assert cache.get(path) is None


# ---------------------------------------------------------------------------
# Tests — EXIF transpose on load
# ---------------------------------------------------------------------------

class TestExifTransposeOnLoad:
    def test_portrait_jpeg_with_exif_rotation_displayed_correctly(self, tmp_path):
        """EXIF Orientation=6(90° CW)인 JPEG는 로드 후 세로 방향으로 보정되어야 함."""
        import piexif
        # 원본 픽셀은 가로(200x100)이지만 EXIF에 90° CW 회전 정보 기록
        path = tmp_path / "rotated.jpg"
        img = Image.new("RGB", (200, 100), (255, 0, 0))
        exif_dict = {"0th": {piexif.ImageIFD.Orientation: 6}}  # 90° CW → 세로로 보여야 함
        img.save(path, format="JPEG", exif=piexif.dump(exif_dict))

        # exif_transpose 적용 후 크기 검증
        loaded = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
        assert loaded.width == 100  # 회전 후 세로 이미지
        assert loaded.height == 200

    def test_normal_jpeg_without_rotation_unchanged(self, tmp_path):
        """EXIF Orientation=1(Normal)인 JPEG는 크기 그대로 유지되어야 함."""
        import piexif
        path = tmp_path / "normal.jpg"
        img = Image.new("RGB", (200, 100), (0, 255, 0))
        exif_dict = {"0th": {piexif.ImageIFD.Orientation: 1}}
        img.save(path, format="JPEG", exif=piexif.dump(exif_dict))

        loaded = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
        assert loaded.width == 200
        assert loaded.height == 100

    def test_splitter_stays_horizontal_for_portrait_image(self, window):
        """세로 이미지여도 레이아웃 스플리터는 항상 Horizontal이어야 함."""
        assert window._splitter.orientation() == Qt.Orientation.Horizontal

    def test_layout_has_no_update_layout_method(self, window):
        """_update_layout_for_image 메서드는 제거되어 존재하지 않아야 함."""
        assert not hasattr(window, "_update_layout_for_image")
