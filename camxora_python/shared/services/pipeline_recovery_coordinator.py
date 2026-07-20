"""Background pipeline failure recovery — shell-level helper agent."""

from __future__ import annotations

import time
from dataclasses import dataclass

from PySide6.QtCore import QObject, QTimer

from shared.services.app_thread_registry import track_app_thread
from shared.services.platform_api import PlatformApi
from shared.services.shell_status import emit_shell_status
from shared.workers.data_workers import PipelineRecoveryScanResult, PipelineRecoveryScanWorker

_IDLE_POLL_MS = 45_000
_ACTIVE_POLL_MS = 20_000
_SONG_COOLDOWN_SEC = 15 * 60
_MAX_TARGETS_PER_CYCLE = 3
_MAX_SESSION_ATTEMPTS_PER_SONG = 2


@dataclass
class _SongAttemptState:
    attempts: int = 0
    last_attempt_at: float = 0.0


class PipelineRecoveryCoordinator(QObject):
    """Poll music history and auto-recover failed draft/Suno songs.

    Complements server-side Suno reject rewrite. This client helper also
    catches draft failures and stuck Suno rows that never got a callback.
    """

    def __init__(self, api: PlatformApi, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._api = api
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll)
        self._worker: PipelineRecoveryScanWorker | None = None
        self._active = False
        self._song_state: dict[str, _SongAttemptState] = {}
        self._enabled = True

    def start(self) -> None:
        self._active = True
        self._timer.start(_IDLE_POLL_MS)
        # Delay first scan so login/bootstrap isn't competing for API.
        QTimer.singleShot(20_000, self._poll)

    def stop(self) -> None:
        self._active = False
        self._timer.stop()
        worker = self._worker
        if worker is not None and worker.isRunning():
            worker.wait(1_500)

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = bool(enabled)

    def _filter_targets(self, targets: list) -> list:
        now = time.time()
        selected: list = []
        for target in targets:
            song_id = str(getattr(target, "song_id", "") or "").strip()
            if not song_id:
                continue
            state = self._song_state.get(song_id) or _SongAttemptState()
            if state.attempts >= _MAX_SESSION_ATTEMPTS_PER_SONG:
                continue
            if state.last_attempt_at and (now - state.last_attempt_at) < _SONG_COOLDOWN_SEC:
                continue
            selected.append(target)
            if len(selected) >= _MAX_TARGETS_PER_CYCLE:
                break
        return selected

    def _mark_attempted(self, targets: tuple | list) -> None:
        now = time.time()
        for target in targets:
            song_id = str(getattr(target, "song_id", "") or "").strip()
            if not song_id:
                continue
            state = self._song_state.get(song_id) or _SongAttemptState()
            state.attempts += 1
            state.last_attempt_at = now
            self._song_state[song_id] = state

    def _poll(self) -> None:
        if not self._active or not self._enabled:
            return
        if self._worker is not None and self._worker.isRunning():
            return
        worker = PipelineRecoveryScanWorker(
            self._api,
            history_limit=25,
            max_targets=_MAX_TARGETS_PER_CYCLE,
            target_filter=self._filter_targets,
            parent=None,
        )
        worker.succeeded.connect(self._on_succeeded)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(self._on_worker_finished)
        self._worker = worker
        track_app_thread(worker)
        worker.start()

    def _on_succeeded(self, payload: object) -> None:
        if not isinstance(payload, PipelineRecoveryScanResult):
            self._timer.setInterval(_IDLE_POLL_MS)
            return
        if payload.attempted_targets:
            self._mark_attempted(payload.attempted_targets)
        if payload.recovered > 0:
            emit_shell_status(
                f"Pipeline helper recovered {payload.recovered} song(s) "
                f"(draft {payload.draft}, rewrite {payload.rewrite}, Suno {payload.suno}).",
                tone="success",
            )
            self._timer.setInterval(_ACTIVE_POLL_MS)
            return
        if payload.candidate_count > 0:
            self._timer.setInterval(_ACTIVE_POLL_MS)
            return
        self._timer.setInterval(_IDLE_POLL_MS)

    def _on_failed(self, message: str) -> None:
        text = str(message or "").strip()
        if text and "No failed songs" not in text:
            emit_shell_status(f"Pipeline helper paused: {text}", tone="warning")
        self._timer.setInterval(_IDLE_POLL_MS)

    def _on_worker_finished(self) -> None:
        self._worker = None
