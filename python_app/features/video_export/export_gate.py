"""Process-global concurrency gate for video export subprocesses.

Why this exists
---------------
Each video export spawns a heavy subprocess (the GPU visualizer) which in
turn launches an ffmpeg encoder. On consumer NVIDIA GPUs the number of
simultaneous NVENC encode sessions is limited (historically 3-5). If more
ffmpeg processes than the hardware allows request ``h264_nvenc`` at once,
the excess sessions block waiting for a free encoder slot. The subprocesses
then sit at 0% CPU, the frame pipe fills, and the UI freezes.

The auto-video pipeline can run multiple channels (OK + ALT) in parallel,
and each channel previously spawned up to ``videoExportWorkers`` worker
threads. That multiplied the intended concurrency by the number of parallel
channels (e.g. 2 channels x 5 workers = 10 concurrent subprocesses) instead
of honouring ``videoExportWorkers`` as a single global limit.

This gate restores the documented contract: *``videoExportWorkers`` limits
the total number of concurrent export subprocesses*, regardless of how many
channels run in parallel.

Design
------
A condition-variable counter (rather than a fixed ``Semaphore``) so the limit
can be adjusted between runs without the hazards of replacing a semaphore that
threads may still be holding. ``acquire``/``release`` are always balanced by
callers via try/finally.
"""
from __future__ import annotations

import threading
import time


class ExportGate:
    """A resizable, process-global concurrency limiter.

    Provides two coordinated controls:

    1. ``acquire``/``release`` — cap the number of *concurrently running*
       export subprocesses (NVENC/GPU session protection).
    2. ``throttle_spawn`` — space out the *moment of spawning* so that many
       heavy interpreter cold-starts don't hit the disk simultaneously. The
       first subprocess warms the OS file cache for numpy/moderngl/pygame/PIL;
       staggered later starts then read those libraries from RAM instead of
       thrashing the disk with simultaneous random reads.
    """

    def __init__(self, limit: int = 1, min_spawn_interval: float = 1.2) -> None:
        self._cv = threading.Condition()
        self._limit = max(1, min(10, int(limit or 1)))
        self._active = 0
        # Spawn-rate throttle state
        self._spawn_lock = threading.Lock()
        self._min_spawn_interval = max(0.0, float(min_spawn_interval))
        self._last_spawn = 0.0

    def set_limit(self, limit: int) -> None:
        """Adjust the maximum number of concurrent permits.

        Raising the limit wakes any waiting threads. Lowering it simply means
        new acquisitions wait until enough permits are released; threads that
        already hold a permit are never interrupted.
        """
        new_limit = max(1, min(10, int(limit or 1)))
        with self._cv:
            self._limit = new_limit
            self._cv.notify_all()

    def set_min_spawn_interval(self, seconds: float) -> None:
        """Adjust the minimum gap between consecutive subprocess spawns."""
        with self._spawn_lock:
            self._min_spawn_interval = max(0.0, float(seconds))

    @property
    def limit(self) -> int:
        with self._cv:
            return self._limit

    @property
    def active(self) -> int:
        with self._cv:
            return self._active

    def acquire(self) -> None:
        """Block until a permit is available, then take it."""
        with self._cv:
            while self._active >= self._limit:
                self._cv.wait()
            self._active += 1

    def release(self) -> None:
        """Return a permit and wake one waiter."""
        with self._cv:
            if self._active > 0:
                self._active -= 1
            self._cv.notify()

    def throttle_spawn(self) -> None:
        """Block briefly so subprocess spawns are spaced out in time.

        Reserves the next time slot under a lock, then sleeps outside the lock
        so multiple callers each get a distinct, spaced spawn moment without
        serialising for the whole sleep duration.
        """
        if self._min_spawn_interval <= 0.0:
            return
        with self._spawn_lock:
            now = time.monotonic()
            scheduled = max(now, self._last_spawn + self._min_spawn_interval)
            self._last_spawn = scheduled
        wait = scheduled - time.monotonic()
        if wait > 0:
            time.sleep(wait)


# Process-wide singleton shared by all export channels.
export_gate = ExportGate(limit=1)
