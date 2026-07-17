"""Base mixin for pages that poll API data while visible."""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QWidget


class PollablePageMixin:
    """Start/stop polling when the page becomes visible."""

    poll_interval_ms: int = 12_000

    def _init_pollable(self) -> None:
        self._poll_timer = QTimer(self)  # type: ignore[arg-type]
        self._poll_timer.setInterval(self.poll_interval_ms)
        self._poll_timer.timeout.connect(self.refresh_data)  # type: ignore[attr-defined]
        self._page_active = False

    def activate_page(self) -> None:
        self._page_active = True
        self.refresh_data()  # type: ignore[attr-defined]
        self._poll_timer.start()

    def deactivate_page(self) -> None:
        self._page_active = False
        self._poll_timer.stop()

    def showEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        QWidget.showEvent(self, event)  # type: ignore[arg-type]
        if self._page_active:
            self._poll_timer.start()

    def hideEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        self._poll_timer.stop()
        QWidget.hideEvent(self, event)  # type: ignore[arg-type]
