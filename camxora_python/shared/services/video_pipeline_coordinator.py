"""Background auto-video pipeline coordinator — port of DesktopVideoPipelineCoordinator.tsx."""

from __future__ import annotations

import time
from typing import Literal

from PySide6.QtCore import QObject, QTimer

from features.video.lib.desktop_video_automation import (
    branch_is_conclusively_complete,
    select_next_auto_video_candidate,
)
from features.video.lib.export_run_defer import deferred_export_run_keys
from features.video.lib.pipeline_inputs import build_video_pipeline_run_key
from features.video.lib.export_track_health import manual_pipeline_start_kwargs
from features.video.services.pipeline_automation_service import PipelineAutomationService
from shared.lib.qt_signals import disconnect_quietly
from shared.models.desktop import VideoWorkspaceState
from shared.models.platform import ProgressRow
from shared.services.app_thread_registry import track_app_thread
from shared.services.platform_api import PlatformApi
from shared.services.video_workspace_service import get_video_workspace_service
from shared.workers.data_workers import VideoPipelineOrchestrationPayload, VideoPipelineOrchestrationWorker

ManualPipelineAction = Literal["rebuild_export", "force_export", "merge", "repair_export"]

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
        self._pending_manual: tuple[ProgressRow, ManualPipelineAction, str, tuple[str, ...]] | None = None
        self._last_poll_error_at = 0.0
        self._last_poll_error_message = ""
        self._api_outage = False
        self._user_cancel_until = 0.0

    def start(self) -> None:
        self._active = True
        self._timer.start(12_000)
        self._poll()

    def stop(self) -> None:
        self._active = False
        self._timer.stop()
        self._pending_manual = None
        worker = self._worker
        if worker is not None:
            # Drop queued succeeded/failed so closeEvent processEvents cannot
            # start a new export after coordinators were stopped.
            self._disconnect_worker(worker)
            if worker.isRunning():
                # Short join only; RootWindow.closeEvent uses app_thread_registry for the rest.
                worker.wait(1_500)
            self._worker = None

    @staticmethod
    def _disconnect_worker(worker: VideoPipelineOrchestrationWorker) -> None:
        disconnect_quietly(worker.succeeded)
        disconnect_quietly(worker.failed)
        disconnect_quietly(worker.finished)

    def set_preview_playing(self, playing: bool) -> None:
        """Pause orchestration polls while Video preview is playing."""
        if not self._active:
            return
        if playing:
            self._timer.stop()
            return
        if not self._timer.isActive():
            self._timer.start(12_000)

    def kick(self) -> None:
        """Force an immediate orchestration poll (e.g. after API recovery or Continue)."""
        if not self._active:
            return
        self._poll()

    def _poll(self) -> None:
        if not self._active:
            return
        from shared.services.video_pipeline_activity import is_app_quitting

        if is_app_quitting():
            return
        from shared.services.platform_client import api_has_access_token

        if not api_has_access_token(self._api):
            return
        if self._last_poll_error_message == "auth":
            self._last_poll_error_message = ""
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
        if not self._active:
            return
        from shared.services.video_pipeline_activity import is_app_quitting

        if is_app_quitting():
            return
        if not isinstance(payload, VideoPipelineOrchestrationPayload):
            return

        # Manual Start Merging / Rebuild queued while a poll worker was loading —
        # always prefer that over auto-export (was dropping merge with "still loading").
        if self._pending_manual is not None:
            self._on_manual_payload_ready(payload)
            return

        workspace = payload.workspace
        if not isinstance(workspace, VideoWorkspaceState):
            return

        recovered_from_outage = self._api_outage
        if recovered_from_outage:
            self._api_outage = False
            self._automation.recover_stale_state()
            self._cooldown_until.clear()

        if time.time() < float(self._user_cancel_until or 0.0):
            return

        from shared.services.auto_pipeline_pause import is_auto_pipeline_paused
        from shared.services.shell_status import emit_shell_status

        if is_auto_pipeline_paused():
            if recovered_from_outage:
                emit_shell_status(
                    "API recovered — auto-video is paused (Stop Exporting). Resume from Progress when ready.",
                    tone="neutral",
                )
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
            skip_keys=deferred_export_run_keys(),
        )
        if candidate is None:
            if recovered_from_outage:
                emit_shell_status(
                    "API recovered — no export-ready run yet (waiting for BG/MP3s/template or outputs).",
                    tone="neutral",
                )
            return
        if recovered_from_outage:
            emit_shell_status(
                "API recovered — resuming auto-video pipeline…",
                tone="success",
            )

        cooldown_key = f"{candidate.key}:{candidate.branch}"
        if (self._cooldown_until.get(cooldown_key) or 0) > time.time():
            return

        row = next(
            (item for item in payload.rows if build_video_pipeline_run_key(item) == candidate.key),
            None,
        )
        if row is not None and branch_is_conclusively_complete(
            row,
            candidate.branch,
            runtime=payload.runtime_by_key.get(candidate.key),
            inspection=payload.inspections.get(candidate.key),
        ):
            # Missing track MP4s after a known merge are archived, not unfinished.
            # Keep repair_unhealthy for first-time / stub-MP4 rows only.
            return

        started = self._automation.start(
            candidate,
            settings=payload.settings,
            repair_unhealthy=True,
        )
        if started:
            self._cooldown_until[cooldown_key] = time.time() + 4.0
        elif self._automation.auth_blocked():
            self._cooldown_until[cooldown_key] = time.time() + 120.0
        else:
            self._cooldown_until[cooldown_key] = time.time() + 12.0

    def auth_blocked(self) -> bool:
        return self._automation.auth_blocked()

    def is_busy(self) -> bool:
        return self._automation.is_busy()

    def cancel_active_export(self) -> bool:
        """Cancel the active pipeline export/merge so another job can start."""
        self._pending_manual = None
        # Prevent auto-video from immediately re-starting the same batch after
        # the user explicitly cancelled (feels like "stuck / won't stop").
        self._user_cancel_until = time.time() + 45.0
        return self._automation.cancel_active()

    def run_manual_action(
        self,
        row: ProgressRow,
        action: ManualPipelineAction,
        *,
        branch: str = "long",
        mp3_paths: list[str] | tuple[str, ...] | None = None,
    ) -> None:
        from shared.services.auto_pipeline_pause import resume_auto_pipeline
        from shared.services.shell_status import emit_shell_status

        if self._automation.recover_stale_state():
            emit_shell_status("Cleared stale video export state.", tone="neutral")
        if self._automation.is_busy():
            emit_shell_status("Video pipeline is already running.", tone="warning")
            return

        # Explicit Start/Rebuild/Merge from Progress clears Stop Exporting pause.
        # Keep pending_manual set BEFORE any poll completes so auto-export cannot steal.
        resume_auto_pipeline()
        self._user_cancel_until = 0.0
        selected = tuple(str(path).strip() for path in (mp3_paths or []) if str(path).strip())
        self._pending_manual = (row, action, branch, selected)

        if self._worker is not None and self._worker.isRunning():
            # Reuse the in-flight settings load — _on_payload_ready routes to merge/export.
            emit_shell_status(
                "Queued — starting when settings finish loading…",
                tone="neutral",
            )
            return

        # parent=None + track: same quit-safety as the poll worker.
        worker = VideoPipelineOrchestrationWorker(self._api, parent=None)
        worker.succeeded.connect(self._on_payload_ready)
        worker.failed.connect(self._on_manual_action_failed)
        worker.finished.connect(self._on_worker_finished)
        self._worker = worker
        track_app_thread(worker)
        worker.start()

    def _on_manual_payload_ready(self, payload: object) -> None:
        if not self._active:
            return
        from shared.services.video_pipeline_activity import is_app_quitting

        if is_app_quitting():
            return
        pending = getattr(self, "_pending_manual", None)
        if pending is None:
            return
        row, action, branch, *rest = pending
        selected_mp3s = tuple(rest[0]) if rest else ()
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
        from features.video.lib.desktop_video_automation import (
            build_auto_video_candidate_from_row_with_reason,
            build_merge_candidate_from_row,
        )
        from shared.services.shell_status import emit_shell_status

        self._automation.recover_stale_state()
        if action == "merge":
            # Merge only needs valid exported MP4s — do not re-gate on BG/template.
            candidate, merge_reason = build_merge_candidate_from_row(
                overlay_row,
                profile,
                normalized_branch,
            )
            if candidate is None:
                emit_shell_status(
                    f"Unable to start merge: {merge_reason or 'run folder is not ready'}.",
                    tone="warning",
                )
                return
            started = self._automation.start_manual_merge(candidate, settings=payload.settings)
            if not started:
                emit_shell_status(
                    "Merge did not start — need valid exported MP4s "
                    "(>50KB per track; 0KB stubs like video-main-1080p.mp4 do not count).",
                    tone="warning",
                )
            return

        candidate, ready_reason = build_auto_video_candidate_from_row_with_reason(
            overlay_row,
            profile,
            normalized_branch,
            workspace=payload.workspace if isinstance(payload.workspace, VideoWorkspaceState) else None,
        )
        if candidate is None:
            emit_shell_status(
                f"Unable to start video action: {ready_reason or 'local assets are not ready'}.",
                tone="warning",
            )
            return

        force_kwargs = manual_pipeline_start_kwargs(action, selected_mp3s)
        # Same as auto-video: honor Music → Auto Merge so rebuild/force continues
        # export → merge instead of stopping after MP4 jobs.
        self._automation.start(
            candidate,
            settings=payload.settings,
            **force_kwargs,
        )

    def _on_manual_action_failed(self, message: str) -> None:
        self._pending_manual = None
        from shared.services.shell_status import emit_shell_status

        emit_shell_status(message or "Video pipeline action failed.", tone="warning")

    def _on_poll_failed(self, message: str) -> None:
        if not self._active:
            return
        from shared.services.video_pipeline_activity import is_app_quitting

        if is_app_quitting():
            return
        from shared.services.shell_status import emit_shell_status

        if self._pending_manual is not None:
            self._on_manual_action_failed(
                message or "Unable to load settings for the requested video action."
            )
            return

        self._api_outage = True
        # Wedged busy flags during an outage prevent resume after recovery.
        self._automation.recover_stale_state()
        from shared.services.platform_client import is_auth_failure_message

        text = str(message or "").strip() or "Auto-video paused: unable to load progress rows."
        if is_auth_failure_message(text):
            if self._last_poll_error_message == "auth":
                return
            self._last_poll_error_message = "auth"
            emit_shell_status("Auto-video paused: sign in to continue.", tone="warning")
            return
        now = time.time()
        if text == self._last_poll_error_message and (now - self._last_poll_error_at) < 60.0:
            return
        self._last_poll_error_at = now
        self._last_poll_error_message = text
        emit_shell_status(f"Auto-video paused: {text}", tone="warning")

    def _on_worker_finished(self) -> None:
        self._worker = None
