"""Debounced push of local workspace prefs to the platform API."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from shared.services.session_service import SessionService

_session: SessionService | None = None
_timer: threading.Timer | None = None
_lock = threading.Lock()


def bind_session(session: SessionService) -> None:
    global _session
    _session = session


def schedule_workspace_prefs_push(delay_s: float = 2.0) -> None:
    if _session is None:
        return

    def _push() -> None:
        try:
            _session.push_workspace_prefs_to_server()
        except Exception:
            pass

    global _timer
    with _lock:
        if _timer is not None:
            _timer.cancel()
        _timer = threading.Timer(delay_s, _push)
        _timer.daemon = True
        _timer.start()
