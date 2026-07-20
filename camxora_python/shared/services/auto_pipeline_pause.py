"""Session-level pause for auto-video and helper agents.

When the user chooses **Stop Exporting** on Progress, background automation
must not restart work until they explicitly Start Export / Continue / Merge
from a row.
"""

from __future__ import annotations

import threading

_lock = threading.Lock()
_paused = False
_reason = ""


def pause_auto_pipeline(reason: str = "Stopped by user") -> None:
    global _paused, _reason
    with _lock:
        _paused = True
        _reason = str(reason or "Stopped by user").strip() or "Stopped by user"


def resume_auto_pipeline() -> bool:
    """Clear the pause. Returns True if a pause was active."""
    global _paused, _reason
    with _lock:
        was = _paused
        _paused = False
        _reason = ""
        return was


def is_auto_pipeline_paused() -> bool:
    with _lock:
        return _paused


def auto_pipeline_pause_reason() -> str:
    with _lock:
        return _reason
