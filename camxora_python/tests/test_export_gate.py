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


def test_export_gate_timeout_while_busy() -> None:
    gate = ExportGate(limit=1)
    gate.acquire()
    try:
        try:
            gate.acquire(timeout_sec=0.2)
            raise AssertionError("expected timeout")
        except RuntimeError as exc:
            assert "Timed out" in str(exc)
    finally:
        gate.release()


def test_export_gate_cancel_while_waiting() -> None:
    gate = ExportGate(limit=1)
    gate.acquire()
    cancel = {"flag": False}

    def worker() -> None:
        try:
            gate.acquire(cancel_check=lambda: cancel["flag"], timeout_sec=2.0)
        except RuntimeError as exc:
            assert "cancelled" in str(exc).lower()
            cancel["done"] = True

    thread = threading.Thread(target=worker)
    thread.start()
    threading.Event().wait(0.05)
    cancel["flag"] = True
    thread.join(timeout=1.0)
    assert cancel.get("done") is True
    gate.release()
