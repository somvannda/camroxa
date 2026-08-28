"""Short busy-state cycle for the Generate Music button."""

from __future__ import annotations

from PySide6.QtCore import QObject, QTimer, Signal


class GenerationService(QObject):
    started = Signal()
    finished = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.finished.emit)
        self.busy = False

    def start(self, duration_ms: int = 1800) -> None:
        if self.busy:
            return
        self.busy = True
        self.started.emit()
        self._timer.start(duration_ms)
