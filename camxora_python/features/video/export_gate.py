"""Process-global concurrency gate for video export subprocesses."""

from __future__ import annotations

import threading
import time


class ExportGate:
    """A resizable, process-global concurrency limiter."""

    def __init__(self, limit: int = 1, min_spawn_interval: float = 1.2) -> None:
        self._cv = threading.Condition()
        self._limit = max(1, min(10, int(limit or 1)))
        self._active = 0
        self._spawn_lock = threading.Lock()
        self._min_spawn_interval = max(0.0, float(min_spawn_interval))
        self._last_spawn = 0.0

    def set_limit(self, limit: int) -> None:
        new_limit = max(1, min(10, int(limit or 1)))
        with self._cv:
            self._limit = new_limit
            self._cv.notify_all()

    def set_min_spawn_interval(self, seconds: float) -> None:
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
        with self._cv:
            while self._active >= self._limit:
                self._cv.wait()
            self._active += 1

    def release(self) -> None:
        with self._cv:
            if self._active > 0:
                self._active -= 1
            self._cv.notify()

    def throttle_spawn(self) -> None:
        if self._min_spawn_interval <= 0.0:
            return
        with self._spawn_lock:
            now = time.monotonic()
            scheduled = max(now, self._last_spawn + self._min_spawn_interval)
            self._last_spawn = scheduled
        wait = scheduled - time.monotonic()
        if wait > 0:
            time.sleep(wait)


export_gate = ExportGate(limit=1)
