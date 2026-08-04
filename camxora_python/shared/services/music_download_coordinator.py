"""Background Suno MP3 download coordinator — shell-level service."""

from __future__ import annotations

from PySide6.QtCore import QObject, QTimer

from shared.lib.qt_signals import disconnect_quietly
from shared.services.app_thread_registry import track_app_thread
from shared.services.platform_api import PlatformApi
from shared.workers.data_workers import MusicDownloadSyncResult, MusicDownloadSyncWorker


_IDLE_POLL_MS = 12_000
_PENDING_POLL_MS = 4_000

_bound_music_download_coordinator: "MusicDownloadCoordinator | None" = None


def bind_music_download_coordinator(coordinator: "MusicDownloadCoordinator | None") -> None:
    global _bound_music_download_coordinator
    _bound_music_download_coordinator = coordinator


def get_music_download_coordinator() -> "MusicDownloadCoordinator | None":
    return _bound_music_download_coordinator


class MusicDownloadCoordinator(QObject):
    """Polls pending downloads and saves MP3 files locally.

    Network I/O runs on a worker thread so the UI never freezes on the
    12s (empty) / 4s (pending) poll cadence.

    While Video preview is playing, polling is fully paused — the old 4s
    pending cadence was hitching ``paintGL`` every few seconds.
    """

    def __init__(self, api: PlatformApi, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._api = api
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll)
        self._worker: MusicDownloadSyncWorker | None = None
        self._active = False
        self._preview_playing = False
        self._had_pending = False

    def start(self) -> None:
        self._active = True
        self._timer.start(_IDLE_POLL_MS)
        self._poll()

    def request_poll(self) -> None:
        """Kick an immediate sync after path/settings changes (no restart needed)."""
        if not self._active:
            return
        self._apply_interval(_PENDING_POLL_MS)
        self._poll()

    def set_preview_playing(self, playing: bool) -> None:
        """Pause download polls entirely while Video preview is playing."""
        playing = bool(playing)
        if self._preview_playing == playing:
            return
        self._preview_playing = playing
        if not self._active:
            return
        if playing:
            # Stop the timer so nothing fires mid-playback (4s pending was the hitch).
            self._timer.stop()
            return
        # Resume: prefer pending cadence if we last saw work, else idle.
        interval = _PENDING_POLL_MS if self._had_pending else _IDLE_POLL_MS
        self._timer.start(interval)

    def stop(self) -> None:
        self._active = False
        self._preview_playing = False
        self._timer.stop()
        worker = self._worker
        if worker is not None:
            disconnect_quietly(worker.succeeded, self._on_sync_succeeded)
            disconnect_quietly(worker.failed, self._on_sync_failed)
            disconnect_quietly(worker.finished, self._on_worker_finished)
            if worker.isRunning():
                # Short join only; RootWindow.closeEvent uses app_thread_registry for the rest.
                worker.wait(1_500)
            self._worker = None

    def _poll(self) -> None:
        if not self._active:
            return
        # Hard gate — do not start workers while preview owns the UI/GPU thread.
        if self._preview_playing:
            return
        from shared.services.video_pipeline_activity import is_app_quitting

        if is_app_quitting():
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

    def _apply_interval(self, interval_ms: int) -> None:
        if self._preview_playing:
            # Never re-arm the 4s pending cadence over a live preview.
            self._timer.stop()
            return
        self._timer.setInterval(int(interval_ms))
        if self._active and not self._timer.isActive():
            self._timer.start()

    def _on_sync_succeeded(self, payload: object) -> None:
        if not isinstance(payload, MusicDownloadSyncResult):
            self._had_pending = False
            self._apply_interval(_IDLE_POLL_MS)
            return
        self._had_pending = bool(payload.pending_count > 0)
        if self._had_pending:
            self._apply_interval(_PENDING_POLL_MS)
        else:
            self._apply_interval(_IDLE_POLL_MS)

    def _on_sync_failed(self, _message: str) -> None:
        # Keep the idle cadence on API/network errors so a down backend
        # does not hammer the UI thread with rapid retries.
        self._apply_interval(_IDLE_POLL_MS)

    def _on_worker_finished(self) -> None:
        self._worker = None
