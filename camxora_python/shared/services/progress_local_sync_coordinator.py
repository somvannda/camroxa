"""Background coordinator — pushes desktop run-folder truth back to platform progress."""

from __future__ import annotations

from PySide6.QtCore import QObject, QTimer

from shared.services.app_thread_registry import track_app_thread
from shared.services.platform_api import PlatformApi
from shared.workers.data_workers import ProgressLocalSyncWorker


_bound_coordinator: "ProgressLocalSyncCoordinator | None" = None


def bind_progress_local_sync_coordinator(coordinator: "ProgressLocalSyncCoordinator") -> None:
    global _bound_coordinator
    _bound_coordinator = coordinator


def get_progress_local_sync_coordinator() -> "ProgressLocalSyncCoordinator | None":
    return _bound_coordinator


class ProgressLocalSyncCoordinator(QObject):
    """Periodically sync local asset/music readiness back to the platform API."""

    def __init__(self, api: PlatformApi, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._api = api
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll)
        self._worker: ProgressLocalSyncWorker | None = None
        self._active = False

    def start(self) -> None:
        self._active = True
        self._timer.start(20_000)
        self._poll()

    def stop(self) -> None:
        self._active = False
        self._timer.stop()
        worker = self._worker
        if worker is not None and worker.isRunning():
            # Short join only; RootWindow.closeEvent uses app_thread_registry for the rest.
            worker.wait(1_500)

    def sync_now(self) -> None:
        if not self._active:
            return
        self._poll(force=True)

    def _poll(self, *, force: bool = False) -> None:
        if not self._active:
            return
        if self._worker is not None and self._worker.isRunning():
            return
        # parent=None: window close must not destroy a live QThread.
        worker = ProgressLocalSyncWorker(self._api, parent=None)
        worker.finished.connect(self._on_worker_finished)
        self._worker = worker
        track_app_thread(worker)
        worker.start()

    def _on_worker_finished(self) -> None:
        self._worker = None
