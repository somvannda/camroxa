"""Defer an album after export retries are exhausted so auto-video can start the next run."""

from __future__ import annotations

import time

# Long enough that overnight auto-video moves on; manual Start Export still works.
EXPORT_RUN_DEFER_SEC = 6 * 60 * 60

_defer_until: dict[str, float] = {}


def defer_export_run(run_key: str, *, seconds: float = EXPORT_RUN_DEFER_SEC) -> None:
    key = str(run_key or "").strip()
    if not key:
        return
    _defer_until[key] = time.time() + max(1.0, float(seconds))


def deferred_export_run_keys(*, now: float | None = None) -> set[str]:
    stamp = time.time() if now is None else float(now)
    expired = [key for key, until in _defer_until.items() if until <= stamp]
    for key in expired:
        _defer_until.pop(key, None)
    return {key for key, until in _defer_until.items() if until > stamp}


def clear_export_run_defer(run_key: str | None = None) -> None:
    if run_key is None:
        _defer_until.clear()
        return
    _defer_until.pop(str(run_key).strip(), None)
