"""Quiet Qt signal disconnect helpers (avoid PySide RuntimeWarning noise)."""

from __future__ import annotations

import warnings
from typing import Any


def disconnect_quietly(signal: Any, slot: Any | None = None) -> None:
    """Disconnect a signal without warning when nothing is connected.

    ``signal.disconnect()`` with no receivers emits::
        RuntimeWarning: libpyside: Failed to disconnect (None) from signal "..."
    """
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message=r".*Failed to disconnect.*",
            category=RuntimeWarning,
        )
        try:
            if slot is None:
                signal.disconnect()
            else:
                signal.disconnect(slot)
        except (TypeError, RuntimeError):
            pass


def disconnect_worker_signals(worker: Any, *signal_names: str) -> None:
    """Disconnect listed signals on a QThread worker (if present)."""
    for name in signal_names:
        signal = getattr(worker, name, None)
        if signal is not None:
            disconnect_quietly(signal)
