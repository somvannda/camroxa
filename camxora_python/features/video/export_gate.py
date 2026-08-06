"""Process-global concurrency gate for video export subprocesses."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable


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

    def acquire(
        self,
        *,
        cancel_check: Callable[[], bool] | None = None,
        timeout_sec: float | None = None,
        on_wait: Callable[[int, int], None] | None = None,
    ) -> None:
        """Acquire a slot. Raises RuntimeError on cancel or timeout while waiting."""
        deadline = None if timeout_sec is None else (time.monotonic() + max(0.0, float(timeout_sec)))
        waited_notice = False
        with self._cv:
            while self._active >= self._limit:
                if cancel_check is not None and cancel_check():
                    raise RuntimeError("Export cancelled while waiting for a free worker slot.")
                if deadline is not None and time.monotonic() >= deadline:
                    raise RuntimeError(
                        f"Timed out waiting for an export worker slot "
                        f"({self._active}/{self._limit} busy). Stop the other export or lower Workers."
                    )
                if on_wait is not None and not waited_notice:
                    on_wait(int(self._active), int(self._limit))
                    waited_notice = True
                remaining = None
                if deadline is not None:
                    remaining = max(0.05, deadline - time.monotonic())
                self._cv.wait(timeout=0.25 if remaining is None else min(0.25, remaining))
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
