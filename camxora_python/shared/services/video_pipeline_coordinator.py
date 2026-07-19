"""Background auto-video pipeline coordinator — port of DesktopVideoPipelineCoordinator.tsx."""

from __future__ import annotations

import time

from PySide6.QtCore import QObject, QTimer

from features.video.lib.desktop_video_automation import select_next_auto_video_candidate
from features.video.services.pipeline_automation_service import PipelineAutomationService
from shared.models.desktop import VideoWorkspaceState
from shared.services.platform_api import PlatformApi
from shared.workers.data_workers import VideoPipelineOrchestrationPayload, VideoPipelineOrchestrationWorker


class VideoPipelineCoordinator(QObject):
    """Polls progress rows and starts pipeline export when automation toggles are enabled."""

    def __init__(self, api: PlatformApi, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._api = api
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll)
        self._worker: VideoPipelineOrchestrationWorker | None = None
        self._automation = PipelineAutomationService(self._api, self)
        self._cooldown_until: dict[str, float] = {}
        self._active = False

    def start(self) -> None:
        self._active = True
        self._timer.start(6_000)
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
        if self._automation.is_busy():
            return
        if self._worker is not None and self._worker.isRunning():
            return
        worker = VideoPipelineOrchestrationWorker(self._api, parent=self)
        worker.succeeded.connect(self._on_payload_ready)
        worker.failed.connect(self._on_poll_failed)
        worker.finished.connect(self._on_worker_finished)
        self._worker = worker
        worker.start()

    def _on_payload_ready(self, payload: object) -> None:
        if not isinstance(payload, VideoPipelineOrchestrationPayload):
            return
        workspace = payload.workspace
        if not isinstance(workspace, VideoWorkspaceState):
            return

        candidate = select_next_auto_video_candidate(
            rows=payload.rows,
            profiles=payload.profiles,
            settings=payload.settings,
            inspections=payload.inspections,
            runtime_by_key=payload.runtime_by_key,
            workspace=workspace,
        )
        if candidate is None:
            return

        cooldown_key = f"{candidate.key}:{candidate.branch}"
        if (self._cooldown_until.get(cooldown_key) or 0) > time.time():
            return

        started = self._automation.start(candidate, settings=payload.settings)
        if started:
            self._cooldown_until[cooldown_key] = time.time() + 4.0
        elif self._automation.auth_blocked():
            self._cooldown_until[cooldown_key] = time.time() + 120.0
        else:
            self._cooldown_until[cooldown_key] = time.time() + 12.0

    def _on_poll_failed(self, _message: str) -> None:
        return

    def _on_worker_finished(self) -> None:
        self._worker = None
