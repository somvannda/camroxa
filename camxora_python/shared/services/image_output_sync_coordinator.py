"""Background image output sync — pulls server-generated PNGs to local run folders."""

from __future__ import annotations

from PySide6.QtCore import QObject, QTimer

from shared.services.platform_api import PlatformApi
from shared.workers.data_workers import ImageOutputSyncWorker


class ImageOutputSyncCoordinator(QObject):
    """Poll successful image jobs and save missing PNG files locally."""

    def __init__(self, api: PlatformApi, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._api = api
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll)
        self._worker: ImageOutputSyncWorker | None = None
        self._active = False

    def start(self) -> None:
        self._active = True
        self._timer.start(15_000)
        self._poll()

    def stop(self) -> None:
        self._active = False
        self._timer.stop()
        worker = self._worker
        if worker is not None and worker.isRunning():
            worker.wait(2_000)

    def _poll(self) -> None:
        if not self._active:
            return
        if self._worker is not None and self._worker.isRunning():
            return
        worker = ImageOutputSyncWorker(self._api, limit=40, parent=self)
        worker.finished.connect(self._on_worker_finished)
        self._worker = worker
        worker.start()

    def _on_worker_finished(self) -> None:
        self._worker = None
