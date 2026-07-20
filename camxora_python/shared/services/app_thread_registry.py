"""Track shell/background QThreads so quit can cancel+join them safely.

Export/merge workers stay in ``video_pipeline_activity``. This registry covers
sync/push/warmup/orchestration workers that are often created with an empty
``objectName`` and a widget parent — closing the window destroys them while
still running and logs ``QThread: Destroyed while thread '' is still running``.
"""

from __future__ import annotations

import weakref
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtCore import QThread

_threads: weakref.WeakSet[QThread] = weakref.WeakSet()
# Strong refs so parent=None workers are not GC'd while the OS thread is alive.
_alive: list[QThread] = []


def track_app_thread(thread: QThread | None) -> None:
    if thread is None:
        return
    _threads.add(thread)
    if thread not in _alive:
        _alive.append(thread)

    def _drop(_obj: object = None, *, _t: QThread = thread) -> None:
        try:
            _alive.remove(_t)
        except ValueError:
            pass

    try:
        thread.finished.connect(_drop)
    except Exception:
        pass


def _qthread_is_running(thread: QThread) -> bool | None:
    try:
        return bool(thread.isRunning())
    except RuntimeError:
        return None
    except Exception:
        return None


def any_app_threads_running() -> bool:
    running = False
    pruned: list[QThread] = []
    seen: set[int] = set()
    for thread in list(_threads) + list(_alive):
        if thread is None:
            continue
        tid = id(thread)
        if tid in seen:
            continue
        seen.add(tid)
        state = _qthread_is_running(thread)
        if state is None:
            continue
        if state:
            running = True
        if thread in _alive:
            pruned.append(thread)
    _alive[:] = pruned
    return running


def shutdown_app_threads(*, wait_ms: int = 10_000) -> None:
    """Cancel (if supported) and join tracked shell workers before teardown.

    Uses one shared deadline so multiple live workers do not stack waits.
    """
    import time

    budget_ms = max(0, int(wait_ms))
    deadline = time.monotonic() + (budget_ms / 1000.0)
    for thread in list(_alive):
        if thread is None:
            continue
        try:
            if _qthread_is_running(thread) is not True:
                continue
            for attr in ("request_stop", "cancel"):
                stopper = getattr(thread, attr, None)
                if callable(stopper):
                    try:
                        stopper()
                    except Exception:
                        pass
                    break
            remaining_ms = int(max(0.0, (deadline - time.monotonic()) * 1000.0))
            if remaining_ms > 0:
                thread.wait(remaining_ms)
        except Exception:
            pass

    still: list[QThread] = []
    for thread in list(_alive):
        if _qthread_is_running(thread) is True:
            still.append(thread)
    _alive[:] = still
