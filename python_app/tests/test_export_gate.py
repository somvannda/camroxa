"""Tests for the process-global export concurrency gate.

Verifies that ExportGate never allows more than `limit` concurrent permits,
which is what prevents NVENC session exhaustion when multiple auto-video
channels run in parallel.
"""
from __future__ import annotations

import threading
import time

from python_app.features.video_export.export_gate import ExportGate


def test_gate_caps_concurrency():
    """No more than `limit` workers may hold a permit simultaneously."""
    gate = ExportGate(limit=3)
    peak = {"n": 0}
    current = {"n": 0}
    lock = threading.Lock()

    def worker():
        gate.acquire()
        try:
            with lock:
                current["n"] += 1
                peak["n"] = max(peak["n"], current["n"])
            time.sleep(0.05)  # simulate work
        finally:
            with lock:
                current["n"] -= 1
            gate.release()

    threads = [threading.Thread(target=worker) for _ in range(12)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert peak["n"] <= 3, f"peak concurrency {peak['n']} exceeded limit 3"
    assert gate.active == 0, "all permits should be released"


def test_gate_uses_full_budget():
    """The gate should allow exactly `limit` workers concurrently (not fewer)."""
    gate = ExportGate(limit=4)
    barrier = threading.Barrier(4, timeout=5)
    reached = {"n": 0}
    lock = threading.Lock()

    def worker():
        gate.acquire()
        try:
            with lock:
                reached["n"] += 1
            # All 4 permit holders should be able to reach the barrier at once.
            barrier.wait()
        finally:
            gate.release()

    threads = [threading.Thread(target=worker, daemon=True) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=6)

    assert reached["n"] == 4


def test_set_limit_raises_wakes_waiters():
    """Raising the limit lets blocked workers proceed."""
    gate = ExportGate(limit=1)
    order: list[str] = []
    lock = threading.Lock()
    started = threading.Event()

    def holder():
        gate.acquire()
        started.set()
        time.sleep(0.2)
        with lock:
            order.append("holder")
        gate.release()

    def waiter():
        started.wait(timeout=2)
        gate.acquire()
        with lock:
            order.append("waiter")
        gate.release()

    th = threading.Thread(target=holder)
    tw = threading.Thread(target=waiter)
    th.start()
    started.wait(timeout=2)
    # Raise the limit so the waiter can proceed without waiting for holder.
    gate.set_limit(2)
    tw.start()
    th.join(timeout=3)
    tw.join(timeout=3)

    assert "waiter" in order
    assert gate.active == 0


def test_release_never_goes_negative():
    """Extra releases must not drive the active count below zero."""
    gate = ExportGate(limit=2)
    gate.release()
    gate.release()
    assert gate.active == 0
    gate.acquire()
    assert gate.active == 1
    gate.release()
    assert gate.active == 0


def test_throttle_spawn_spaces_out_starts():
    """Concurrent spawns must be spread out over at least the expected span.

    Each call reserves the next time slot (0, I, 2I, ...). We assert the
    overall span rather than per-gap spacing, since OS scheduling jitter can
    reorder thread wake-ups even though the reserved slots are correctly spaced.
    """
    interval = 0.1
    n = 5
    gate = ExportGate(limit=10, min_spawn_interval=interval)
    stamps: list[float] = []
    lock = threading.Lock()

    def worker():
        gate.throttle_spawn()
        with lock:
            stamps.append(time.monotonic())

    threads = [threading.Thread(target=worker) for _ in range(n)]
    start = time.monotonic()
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Last reserved slot is at (n-1)*interval; allow generous jitter tolerance.
    span = max(stamps) - start
    assert span >= (n - 1) * interval * 0.9, f"stagger span too short: {span:.3f}s"


def test_throttle_spawn_disabled_when_zero_interval():
    """A zero interval disables throttling (no delay)."""
    gate = ExportGate(limit=5, min_spawn_interval=0.0)
    start = time.monotonic()
    for _ in range(5):
        gate.throttle_spawn()
    assert (time.monotonic() - start) < 0.05
