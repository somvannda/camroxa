"""Optional audible feedback when magnetic snap engages (S10)."""

from __future__ import annotations

import logging
import sys

logger = logging.getLogger(__name__)

_last_click_time = 0.0
_MIN_INTERVAL_SEC = 0.08


def play_snap_click(enabled: bool = True) -> None:
    if not enabled:
        return
    global _last_click_time
    import time

    now = time.monotonic()
    if now - _last_click_time < _MIN_INTERVAL_SEC:
        return
    _last_click_time = now
    try:
        if sys.platform == "win32":
            import winsound

            winsound.MessageBeep(winsound.MB_OK)
        else:
            print("\a", end="", flush=True)
    except Exception:
        logger.debug("Snap click feedback unavailable", exc_info=True)
