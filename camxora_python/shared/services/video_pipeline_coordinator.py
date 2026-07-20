"""Background auto-video pipeline coordinator — port of DesktopVideoPipelineCoordinator.tsx."""

from __future__ import annotations

import time
from typing import Literal

from PySide6.QtCore import QObject, QTimer

from features.video.lib.desktop_video_automation import (
    build_auto_video_candidate_from_row,
    select_next_auto_video_candidate,
)
from features.video.services.pipeline_automation_service import PipelineAutomationService
from shared.models.desktop import VideoWorkspaceState
from shared.models.platform import ProgressRow
from shared.services.app_thread_registry import track_app_thread
from shared.services.platform_api import PlatformApi
from shared.services.video_workspace_service import get_video_workspace_service
from shared.workers.data_workers import VideoPipelineOrchestrationPayload, VideoPipelineOrchestrationWorker

ManualPipelineAction = Literal["rebuild_export", "force_export", "merge"]

_bound_coordinator: "VideoPipelineCoordinator | None" = None


def bind_video_pipeline_coordinator(coordinator: "VideoPipelineCoordinator") -> None:
    global _bound_coordinator
    _bound_coordinator = coordinator


def get_video_pipeline_coordinator() -> "VideoPipelineCoordinator | None":
    return _bound_coordinator


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
        self._pending_manual: tuple[ProgressRow, ManualPipelineAction, str] | None = None
        self._last_poll_error_at = 0.0
        self._last_poll_error_message = ""

    def start(self) -> None:
        self._active = True
        self._timer.start(6_000)
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
        if self._automation.is_busy():
            return
        if self._worker is not None and self._worker.isRunning():
            return
        # parent=None: window close must not destroy a live QThread.
        worker = VideoPipelineOrchestrationWorker(self._api, parent=None)
        worker.succeeded.connect(self._on_payload_ready)
        worker.failed.connect(self._on_poll_failed)
        worker.finished.connect(self._on_worker_finished)
        self._worker = worker
        track_app_thread(worker)
        worker.start()

    def _on_payload_ready(self, payload: object) -> None:
        if not isinstance(payload, VideoPipelineOrchestrationPayload):
            return
        workspace = payload.workspace
        if not isinstance(workspace, VideoWorkspaceState):
            return

        self._automation.recover_stale_state()
        if isinstance(workspace, VideoWorkspaceState):
            active = get_video_workspace_service().get_workspace_state()
            if active is not None:
                workspace = active

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

    def auth_blocked(self) -> bool:
        return self._automation.auth_blocked()

    def run_manual_action(
        self,
        row: ProgressRow,
        action: ManualPipelineAction,
        *,
        branch: str = "long",
    ) -> None:
        from shared.services.shell_status import emit_shell_status

        if self._automation.recover_stale_state():
            emit_shell_status("Cleared stale video export state.", tone="neutral")
        if self._automation.is_busy():
            emit_shell_status("Video pipeline is already running.", tone="warning")
            return
        if self._worker is not None and self._worker.isRunning():
            emit_shell_status("Video pipeline is still loading settings.", tone="warning")
            return

        self._pending_manual = (row, action, branch)
        worker = VideoPipelineOrchestrationWorker(self._api, parent=self)
        worker.succeeded.connect(self._on_manual_payload_ready)
        worker.failed.connect(self._on_manual_action_failed)
        worker.finished.connect(self._on_worker_finished)
        self._worker = worker
        worker.start()

    def _on_manual_payload_ready(self, payload: object) -> None:
        pending = getattr(self, "_pending_manual", None)
        if pending is None:
            self._on_payload_ready(payload)
            return
        row, action, branch = pending
        self._pending_manual = None
        if not isinstance(payload, VideoPipelineOrchestrationPayload):
            return

        profiles_by_id = {profile.id: profile for profile in payload.profiles}
        profile = profiles_by_id.get(row.meta.profile_id)
        if profile is None:
            from shared.services.shell_status import emit_shell_status

            emit_shell_status("Unable to start video action: channel profile not found.", tone="warning")
            return

        normalized_branch = "reel" if str(branch or "").strip().lower() == "reel" else "long"
        overlay_rows = [item for item in payload.rows if item.meta.batch_id == row.meta.batch_id]
        overlay_row = next(
            (
                item
                for item in overlay_rows
                if item.meta.profile_id == row.meta.profile_id and item.meta.role == row.meta.role
            ),
            row,
        )
        candidate = build_auto_video_candidate_from_row(
            overlay_row,
            profile,
            normalized_branch,
            workspace=payload.workspace if isinstance(payload.workspace, VideoWorkspaceState) else None,
        )
        if candidate is None:
            from shared.services.shell_status import emit_shell_status

            emit_shell_status(
                "Unable to start video action: local run folder is missing MP3s, image assets, or a catalog template.",
                tone="warning",
            )
            return

        self._automation.recover_stale_state()
        if action == "merge":
            self._automation.start_manual_merge(candidate, settings=payload.settings)
            return

        force_regenerate = action == "force_export"
        self._automation.start(
            candidate,
            settings=payload.settings,
            force_regenerate=force_regenerate,
            auto_merge=False,
        )

    def _on_manual_action_failed(self, message: str) -> None:
        self._pending_manual = None
        from shared.services.shell_status import emit_shell_status

        emit_shell_status(message or "Video pipeline action failed.", tone="warning")

    def _on_poll_failed(self, message: str) -> None:
        from shared.services.shell_status import emit_shell_status

        text = str(message or "").strip() or "Auto-video paused: unable to load progress rows."
        now = time.time()
        if text == self._last_poll_error_message and (now - self._last_poll_error_at) < 60.0:
            return
        self._last_poll_error_at = now
        self._last_poll_error_message = text
        emit_shell_status(f"Auto-video paused: {text}", tone="warning")

    def _on_worker_finished(self) -> None:
        self._worker = None
