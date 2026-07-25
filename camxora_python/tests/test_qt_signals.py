"""Tests for quiet Qt signal disconnect helper."""

from __future__ import annotations

import warnings

import pytest
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication

from shared.lib.qt_signals import disconnect_quietly, disconnect_worker_signals


@pytest.fixture
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class _Probe(QObject):
    succeeded = Signal(int)
    failed = Signal(str)
    finished = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.hits = 0

    def on_finished(self) -> None:
        self.hits += 1


def test_disconnect_quietly_no_warning_when_unconnected(qapp: QApplication) -> None:
    probe = _Probe()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        disconnect_quietly(probe.succeeded)
        disconnect_quietly(probe.failed)
        disconnect_quietly(probe.finished, probe.on_finished)
    assert not any("Failed to disconnect" in str(item.message) for item in caught)


def test_disconnect_quietly_removes_connected_slot(qapp: QApplication) -> None:
    probe = _Probe()
    probe.finished.connect(probe.on_finished)
    disconnect_quietly(probe.finished, probe.on_finished)
    probe.finished.emit()
    assert probe.hits == 0


def test_disconnect_worker_signals(qapp: QApplication) -> None:
    probe = _Probe()
    probe.finished.connect(probe.on_finished)
    disconnect_worker_signals(probe, "finished", "missing")
    probe.finished.emit()
    assert probe.hits == 0
