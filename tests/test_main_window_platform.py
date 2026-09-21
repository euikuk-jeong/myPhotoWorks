"""MainWindow 플랫폼 분기 테스트."""
import sys

from myphotoworks.ui.main_window import MainWindow


def test_patch_system_menu_is_noop_on_non_windows(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")

    class Dummy:
        def winId(self):  # noqa: N802
            raise AssertionError("winId must not be called on non-Windows")

    MainWindow._patch_system_menu(Dummy())
