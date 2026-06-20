"""
TimerRegistry — centralised QTimer lifecycle management.

Owns every QTimer instance: creation, start, stop, page-gate filtering,
and exception-safe teardown. Extracted from MainWindow as part of the
God-class refactor.

Requirements: 5.1, 5.2, 5.4, 5.5, 5.6, 12.4
"""
from __future__ import annotations

import logging
from collections.abc import Callable

from PyQt6.QtCore import QObject, QTimer

logger = logging.getLogger(__name__)


class TimerRegistry:
    """Centralised registry that owns every QTimer in the application.

    Timers are registered once (typically in ``MainWindow.__init__`` after the
    UI build), started/stopped idempotently via ``sync``, and torn down safely
    via ``stop_all`` during ``closeEvent``.

    The optional *page_gate* mechanism wraps a callback so it only fires when
    the current active page matches the gate value. The underlying QTimer
    always fires on its interval; the guard simply skips the callback
    invocation when the page does not match.
    """

    def __init__(self, parent: QObject | None = None) -> None:
        self._parent = parent
        self._timers: dict[str, QTimer] = {}
        self._active_page: str = ""

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(
        self,
        name: str,
        interval_ms: int,
        callback: Callable[[], None],
        *,
        page_gate: str | None = None,
    ) -> QTimer:
        """Create, store, and return a QTimer bound to *callback*.

        Parameters
        ----------
        name:
            Unique identifier for this timer. Raises ``ValueError`` if the
            name is already registered.
        interval_ms:
            Timer interval in milliseconds.
        callback:
            Zero-argument callable invoked on each timeout.
        page_gate:
            When not ``None``, the callback is wrapped so it only executes
            when ``self._active_page == page_gate``.

        Returns
        -------
        QTimer
            The newly created timer (not yet started).
        """
        if name in self._timers:
            raise ValueError(
                f"Timer '{name}' is already registered"
            )

        timer = QTimer(self._parent)
        timer.setInterval(interval_ms)

        # Wrap callback with page-gate guard when applicable.
        if page_gate is not None:
            effective_callback = self._make_page_guard(callback, page_gate)
        else:
            effective_callback = callback

        timer.timeout.connect(effective_callback)
        self._timers[name] = timer
        return timer

    # ------------------------------------------------------------------
    # Lifecycle control
    # ------------------------------------------------------------------

    def stop_all(self) -> None:
        """Stop every registered timer. Each stop is exception-safe.

        Called from ``MainWindow.closeEvent`` to ensure all polling ceases
        before the application shuts down.
        """
        for name, timer in self._timers.items():
            try:
                timer.stop()
            except Exception:  # noqa: BLE001
                logger.debug("Exception stopping timer '%s'", name, exc_info=True)

    def sync(self, name: str, *, enabled: bool) -> None:
        """Idempotently start or stop the named timer.

        - If *enabled* is ``True`` and the timer is not already running, it is
          started.
        - If *enabled* is ``False`` and the timer is running, it is stopped.
        - If the timer is already in the requested state, this is a no-op.
        - If *name* is not registered, a DEBUG-level warning is logged and the
          call is a no-op.
        """
        timer = self._timers.get(name)
        if timer is None:
            logger.debug("sync called for unregistered timer '%s'", name)
            return

        if enabled:
            if not timer.isActive():
                timer.start()
        else:
            if timer.isActive():
                timer.stop()

    # ------------------------------------------------------------------
    # Page-gate
    # ------------------------------------------------------------------

    def set_active_page(self, page: str) -> None:
        """Set the active page identifier used by page-gate guards."""
        self._active_page = page

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _make_page_guard(
        self,
        callback: Callable[[], None],
        page_gate: str,
    ) -> Callable[[], None]:
        """Return a wrapper that invokes *callback* only when the active page
        matches *page_gate*."""

        def _guarded() -> None:
            if self._active_page == page_gate:
                callback()

        return _guarded
