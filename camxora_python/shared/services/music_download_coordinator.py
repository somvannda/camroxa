"""Background Suno MP3 download coordinator — shell-level service."""

from __future__ import annotations

from PySide6.QtCore import QObject, QTimer

from shared.services.app_thread_registry import track_app_thread
from shared.services.platform_api import PlatformApi
from shared.workers.data_workers import MusicDownloadSyncResult, MusicDownloadSyncWorker


class MusicDownloadCoordinator(QObject):
    """Polls pending downloads and saves MP3 files locally.

    Network I/O runs on a worker thread so the UI never freezes on the
    12s (empty) / 4s (pending) poll cadence.
    """

    def __init__(self, api: PlatformApi, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._api = api
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll)
        self._worker: MusicDownloadSyncWorker | None = None
        self._active = False

    def start(self) -> None:
        self._active = True
        self._timer.start(12_000)
        self._poll()

    def stop(self) -> None:
        self._active = False
        self._timer.stop()
        worker = self._worker
        if worker is not None and worker.isRunning():
            # Short join only; RootWindow.closeEvent uses app_thread_registry for the rest.
            worker.wait(1_500)

    def _poll(self) -> None:
        if not self._active:
            return
        if self._worker is not None and self._worker.isRunning():
            return
        # parent=None: window close must not destroy a live QThread.
        worker = MusicDownloadSyncWorker(self._api, limit=24, parent=None)
        worker.succeeded.connect(self._on_sync_succeeded)
        worker.failed.connect(self._on_sync_failed)
        worker.finished.connect(self._on_worker_finished)
        self._worker = worker
        track_app_thread(worker)
        worker.start()

    def _on_sync_succeeded(self, payload: object) -> None:
        if not isinstance(payload, MusicDownloadSyncResult):
            self._timer.setInterval(12_000)
            return
        if payload.pending_count > 0:
            self._timer.setInterval(4_000)
        else:
            self._timer.setInterval(12_000)

    def _on_sync_failed(self, _message: str) -> None:
        # Keep the idle cadence on API/network errors so a down backend
        # does not hammer the UI thread with rapid retries.
        self._timer.setInterval(12_000)

    def _on_worker_finished(self) -> None:
        self._worker = None
