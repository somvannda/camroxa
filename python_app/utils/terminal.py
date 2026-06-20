"""Terminal output helpers for inline progress rendering."""
from __future__ import annotations

import sys
import threading

_inline_lock = threading.Lock()
_inline_last_len = 0


def print_inline(msg: str) -> None:
    """Print a message that overwrites the current terminal line."""
    global _inline_last_len
    text = str(msg or "")
    if not text:
        return
    with _inline_lock:
        try:
            pad = ""
            try:
                pad_len = max(0, int(_inline_last_len) - len(text))
                if pad_len:
                    pad = " " * pad_len
            except Exception:
                pad = ""
            sys.stdout.write("\r" + text + pad)
            sys.stdout.flush()
            _inline_last_len = max(int(_inline_last_len), len(text))
        except Exception:
            pass


def end_inline() -> None:
    """End the current inline line and move to a new line."""
    global _inline_last_len
    with _inline_lock:
        try:
            if int(_inline_last_len) > 0:
                sys.stdout.write("\n")
                sys.stdout.flush()
        except Exception:
            pass
        _inline_last_len = 0
