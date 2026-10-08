"""Explainability, item 5 — ``DiffBar``: a bar drawn from the centre.

Right of the centre line (sage) = better than the recommended photo, left (rust) = worse; a
difference inside the deadband ("same") is a short grey bar, "none" draws nothing but the track.
``value()`` is the signed bar length in percent of the half width (-100..100).
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PyQt6.QtGui import QColor  # noqa: E402

from myphotoworks.ui.styles import tokens  # noqa: E402


@pytest.fixture
def bar(qtbot):
    from myphotoworks.ui.diff_bar import DiffBar

    widget = DiffBar()
    qtbot.addWidget(widget)
    widget.resize(200, 12)
    widget.show()
    return widget


def _pixel(widget, fx, fy=0.5):
    image = widget.grab().toImage()
    return QColor(image.pixel(int(widget.width() * fx), int(widget.height() * fy))).name()


def test_starts_empty(bar):
    assert bar.value() == 0 and bar.verdict() == "none"


def test_value_is_the_signed_percent_of_the_half_width(bar):
    bar.set_delta(0.5, "better")
    assert bar.value() == 50 and bar.verdict() == "better"
    bar.set_delta(-0.25, "worse")
    assert bar.value() == -25 and bar.verdict() == "worse"


def test_delta_is_clamped(bar):
    bar.set_delta(3.0, "better")
    assert bar.value() == 100
    bar.set_delta(-3.0, "worse")
    assert bar.value() == -100


def test_better_fills_the_right_half_in_sage(bar):
    bar.set_delta(1.0, "better")
    assert _pixel(bar, 0.75) == QColor(tokens.PICK).name()
    assert _pixel(bar, 0.25) != QColor(tokens.PICK).name()


def test_worse_fills_the_left_half_in_rust(bar):
    bar.set_delta(-1.0, "worse")
    assert _pixel(bar, 0.25) == QColor(tokens.WARN).name()
    assert _pixel(bar, 0.75) != QColor(tokens.WARN).name()


def test_same_is_grey_not_sage_or_rust(bar):
    bar.set_delta(0.9, "same")
    colour = _pixel(bar, 0.7)
    assert colour not in (QColor(tokens.PICK).name(), QColor(tokens.WARN).name())
    assert colour != _pixel(bar, 0.3)                   # the filled side differs from the empty


def test_none_draws_only_the_track(bar):
    bar.set_delta(0.9, "none")
    assert bar.value() == 0
    assert _pixel(bar, 0.75) == _pixel(bar, 0.25)


def test_the_recommended_photo_leaves_both_halves_empty(bar):
    bar.set_delta(0.0, "same")
    assert _pixel(bar, 0.75) == _pixel(bar, 0.25)
