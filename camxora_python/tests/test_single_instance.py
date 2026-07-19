"""Tests for single-instance guard."""

from __future__ import annotations

import sys

import pytest
from PySide6.QtWidgets import QApplication

from shared.lib.single_instance import SingleInstanceGuard


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv[:1])
    return app


def test_second_guard_cannot_become_primary(qapp: QApplication) -> None:
    first = SingleInstanceGuard(qapp)
    assert first.try_become_primary() is True

    activated = {"count": 0}

    def _on_activate() -> None:
        activated["count"] += 1

    first.set_activate_handler(_on_activate)

    second = SingleInstanceGuard(qapp)
    assert second.try_become_primary() is False

    # Local-socket signals are delivered via the Qt event loop.
    for _ in range(20):
        qapp.processEvents()
        if activated["count"] >= 1:
            break
    assert activated["count"] >= 1
