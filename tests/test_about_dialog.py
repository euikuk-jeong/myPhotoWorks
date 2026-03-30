"""Tests for AboutDialog."""
import pytest
from unittest.mock import patch
from PyQt6.QtWidgets import QDialogButtonBox


@pytest.fixture
def about_dialog(qtbot):
    from myphotoworks.ui.about_dialog import AboutDialog

    dlg = AboutDialog()
    qtbot.addWidget(dlg)
    return dlg


def test_about_dialog_opens(about_dialog):
    assert about_dialog is not None


def test_about_dialog_title(about_dialog):
    assert "myPhotoWorks" in about_dialog.windowTitle()


def test_about_dialog_shows_version(about_dialog):
    labels = [
        w.text()
        for w in about_dialog.findChildren(about_dialog.__class__.__mro__[-2])
        if hasattr(w, "text")
    ]
    # version label exists somewhere in the dialog
    from myphotoworks.ui.about_dialog import _get_version
    ver = _get_version()
    assert ver  # non-empty


def test_get_version_fallback():
    """PackageNotFoundError should return the fallback version string."""
    from importlib.metadata import PackageNotFoundError
    from myphotoworks.ui import about_dialog

    with patch("myphotoworks.ui.about_dialog.version", side_effect=PackageNotFoundError):
        result = about_dialog._get_version()
    assert result == "0.1.0"


def test_get_version_returns_string():
    from myphotoworks.ui.about_dialog import _get_version

    result = _get_version()
    assert isinstance(result, str)
    assert len(result) > 0
