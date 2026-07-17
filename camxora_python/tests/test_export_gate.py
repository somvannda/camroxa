"""Tests for export gate concurrency control."""

from __future__ import annotations

import threading

from features.video.export_gate import ExportGate


def test_export_gate_limits_concurrency() -> None:
    gate = ExportGate(limit=1)
    gate.acquire()
    released = threading.Event()

    def worker() -> None:
        gate.acquire()
        released.set()
        gate.release()

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join(timeout=0.05)
    assert not released.is_set()
    gate.release()
    thread.join(timeout=1.0)
    assert released.is_set()
