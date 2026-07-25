"""Background image output sync — pulls server-generated PNGs to local run folders."""

from __future__ import annotations

from PySide6.QtCore import QObject, QTimer

from shared.lib.qt_signals import disconnect_quietly
from shared.services.app_thread_registry import track_app_thread
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
        if worker is not None:
            # succeeded uses a lambda — disconnect all receivers on that signal only.
            disconnect_quietly(worker.succeeded)
            disconnect_quietly(worker.finished, self._on_worker_finished)
            if worker.isRunning():
                # Short join only; RootWindow.closeEvent uses app_thread_registry for the rest.
                worker.wait(1_500)
            self._worker = None

    def _poll(self) -> None:
        if not self._active:
            return
        from shared.services.video_pipeline_activity import is_app_quitting

        if is_app_quitting():
            return
        if self._worker is not None and self._worker.isRunning():
            return
        # parent=None: window close must not destroy a live QThread.
        worker = ImageOutputSyncWorker(self._api, limit=40, parent=None)
        worker.succeeded.connect(lambda _count: self._after_sync())
        worker.finished.connect(self._on_worker_finished)
        self._worker = worker
        track_app_thread(worker)
        worker.start()

    def _after_sync(self) -> None:
        from shared.services.progress_local_sync_coordinator import get_progress_local_sync_coordinator

        coordinator = get_progress_local_sync_coordinator()
        if coordinator is not None:
            coordinator.sync_now()

    def _on_worker_finished(self) -> None:
        self._worker = None
