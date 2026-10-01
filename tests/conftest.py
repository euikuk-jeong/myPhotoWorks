"""Shared test setup.

* No real face model in tests (slow, and a false detection on a synthetic scene would change
  recommendations). Face tests inject ``tests.synthetic.FakeFaceEngine``.
"""
import pytest

from myphotoworks.core.faces import DISABLE_ENV


@pytest.fixture(autouse=True)
def _no_default_face_engine(monkeypatch):
    monkeypatch.setenv(DISABLE_ENV, "1")

