"""Shared test setup.

* No real face model in tests (slow, and a false detection on a synthetic scene would change
  recommendations). Face tests inject ``tests.synthetic.FakeFaceEngine``.
* A throw-away home folder per test, so nothing a test triggers (selection logs, ...) is written
  to the real ``~/.myphotoworks``.
"""
import pytest

from myphotoworks.core.faces import DISABLE_ENV


@pytest.fixture(autouse=True)
def _no_default_face_engine(monkeypatch):
    monkeypatch.setenv(DISABLE_ENV, "1")


@pytest.fixture(autouse=True)
def _isolated_home(monkeypatch, tmp_path_factory):
    home = tmp_path_factory.mktemp("home")
    for var in ("HOME", "USERPROFILE"):
        monkeypatch.setenv(var, str(home))
