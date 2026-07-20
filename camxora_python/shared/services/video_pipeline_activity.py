"""Track live export/merge worker threads for stale-state recovery."""

from __future__ import annotations

import time
import weakref
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtCore import QThread

_threads: weakref.WeakSet[QThread] = weakref.WeakSet()
# Strong refs so closing the video page / main window cannot GC a live QThread
# when workers are created with parent=None.
_alive: list[QThread] = []
# Set during RootWindow.closeEvent so finished handlers do not start the next
# batch track after cancel (which would recreate a live QThread during teardown).
_app_quitting: bool = False


def set_app_quitting(value: bool) -> None:
    global _app_quitting
    _app_quitting = bool(value)


def is_app_quitting() -> bool:
    return _app_quitting


def track_video_pipeline_thread(thread: QThread | None) -> None:
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


def untrack_video_pipeline_thread(thread: QThread | None) -> None:
    """Drop a worker before ``deleteLater`` so UI probes never touch a zombie."""
    if thread is None:
        return
    try:
        _alive.remove(thread)
    except ValueError:
        pass
    try:
        _threads.discard(thread)
    except Exception:
        pass


def _qthread_is_running(thread: QThread) -> bool | None:
    """Return True/False, or None when the C++ QThread was already destroyed."""
    try:
        return bool(thread.isRunning())
    except RuntimeError:
        # PySide: ``deleteLater`` destroyed C++ while the Python wrapper remains.
        return None
    except Exception:
        return None


def any_video_pipeline_threads_running() -> bool:
    """True if any tracked export/merge worker is still running.

    Safe across quit races: ``deleteLater`` can destroy the C++ QThread while
    the Python wrapper is still listed in ``_threads`` / ``_alive``.
    """
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


def shutdown_video_pipeline_threads(*, wait_ms: int = 8_000) -> None:
    """Cancel and join export/merge workers before QApplication tears down widgets.

    Uses one shared deadline so multiple live workers do not stack waits.
    """
    budget_ms = max(0, int(wait_ms))
    deadline = time.monotonic() + (budget_ms / 1000.0)
    for thread in list(_alive):
        if thread is None:
            continue
        try:
            if _qthread_is_running(thread) is not True:
                continue
            cancel = getattr(thread, "cancel", None)
            if callable(cancel):
                try:
                    cancel()
                except Exception:
                    pass
            remaining_ms = int(max(0.0, (deadline - time.monotonic()) * 1000.0))
            if remaining_ms > 0:
                thread.wait(remaining_ms)
        except Exception:
            pass

    # Drop finished/zombie wrappers; keep still-running refs so Python GC cannot
    # destroy a live QThread while the OS thread is alive.
    still: list[QThread] = []
    for thread in list(_alive):
        if _qthread_is_running(thread) is True:
            still.append(thread)
    _alive[:] = still


def terminate_video_pipeline_threads() -> None:
    """Last-resort stop for stuck export workers during app quit."""
    for thread in list(_alive):
        if _qthread_is_running(thread) is not True:
            continue
        try:
            cancel = getattr(thread, "cancel", None)
            if callable(cancel):
                cancel()
        except Exception:
            pass
        try:
            thread.terminate()
            thread.wait(3_000)
        except Exception:
            pass
    still: list[QThread] = []
    for thread in list(_alive):
        if _qthread_is_running(thread) is True:
            still.append(thread)
    _alive[:] = still
