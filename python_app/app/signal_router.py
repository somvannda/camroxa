"""
SignalRouter — centralised UiBus event subscription and dispatch.

Owns every ``UiBus`` signal connection and dispatches incoming events to the
correct handler by ``event["type"]``. Extracted from ``MainWindow`` as part of
the God-class decomposition so the event routing topology is explicit,
testable, and not scattered across ``MainWindow.__init__`` and handler methods.

Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.7
"""
from __future__ import annotations

import logging
from collections.abc import Callable

from .ui_bus import UiBus

logger = logging.getLogger(__name__)


class SignalRouter:
    """Routes ``UiBus`` events to registered handlers by event type.

    The router subscribes to the ``music_event`` and ``export_event`` signals
    on construction. When an event arrives, its ``"type"`` field is looked up
    in the *handlers* mapping and the matching callable is invoked with the
    event dict. Unregistered event types are logged at DEBUG level and
    discarded — they are not treated as errors.
    """

    def __init__(
        self,
        *,
        bus: UiBus,
        handlers: dict[str, Callable[[dict], None]],
    ) -> None:
        """Subscribe to UiBus signals and store a copy of *handlers*.

        Parameters
        ----------
        bus:
            The ``UiBus`` instance whose ``music_event`` and ``export_event``
            signals are connected to this router.
        handlers:
            Mapping from event type string to a handler callable. A shallow
            copy is taken so later mutation of the caller's dict does not
            affect routing; use :meth:`register` for late registration.
        """
        self._handlers: dict[str, Callable[[dict], None]] = dict(handlers)
        bus.music_event.connect(self._on_music_event)
        bus.export_event.connect(self._on_export_event)

    def register(self, event_type: str, handler: Callable[[dict], None]) -> None:
        """Register (or replace) a handler for *event_type* after construction."""
        self._handlers[event_type] = handler

    def _on_music_event(self, event: dict) -> None:
        """Dispatch a ``music_event`` to its registered handler."""
        self._dispatch(event, source="music_event")

    def _on_export_event(self, event: dict) -> None:
        """Dispatch an ``export_event`` to its registered handler."""
        self._dispatch(event, source="export_event")

    def _dispatch(self, event: dict, *, source: str) -> None:
        """Look up ``event["type"]`` in the handlers map and invoke it.

        If no handler is registered for the event type, a DEBUG-level message
        is logged and the event is discarded without raising.
        """
        event_type = str((event or {}).get("type", "")).strip()
        handler = self._handlers.get(event_type)
        if handler is not None:
            handler(event)
        else:
            logger.debug("SignalRouter: no handler for %s.%s", source, event_type)
