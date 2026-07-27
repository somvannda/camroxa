"""Soft DistroKid coordinator — queued, Short-gated, role-aware."""

from __future__ import annotations

from PySide6.QtCore import QObject, QTimer

from features.distrokid.lib.distrokid_job_store import DistroKidJob, DistroKidJobStore
from features.distrokid.lib.distrokid_artist import resolve_distrokid_artist
from features.distrokid.lib.distrokid_readiness import short_exports_ready
from features.distrokid.lib.distrokid_settings import DistroKidSettingsStore
from features.distrokid.workers.distrokid_upload_worker import DistroKidUploadRequest, DistroKidUploadWorker
from shared.lib.music_settings import read_boolean_setting
from shared.lib.qt_signals import disconnect_quietly
from shared.services.app_thread_registry import track_app_thread
from shared.services.platform_api import PlatformApi
from shared.services.platform_client import PlatformApiError
from shared.services.shell_status import emit_shell_status

_bound: "DistroKidPipelineCoordinator | None" = None


def bind_distrokid_pipeline_coordinator(coordinator: "DistroKidPipelineCoordinator") -> None:
    global _bound
    _bound = coordinator


def get_distrokid_pipeline_coordinator() -> "DistroKidPipelineCoordinator | None":
    return _bound


class DistroKidPipelineCoordinator(QObject):
    """Queues DistroKid uploads after long stage (+ Short when enabled)."""

    def __init__(self, api: PlatformApi, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._api = api
        self._store = DistroKidJobStore()
        self._worker: DistroKidUploadWorker | None = None
        self._active_job_id: str | None = None
        self._active = False
        self._batch_context_cache: dict[str, dict] = {}
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    def start(self) -> None:
        self._active = True
        self._timer.start(8_000)
        self._tick()

    def stop(self) -> None:
        self._active = False
        self._timer.stop()
        worker = self._worker
        if worker is None:
            return
        self._disconnect(worker)
        try:
            worker.cancel()
        except Exception:
            pass
        if worker.isRunning():
            worker.wait(1_500)
        self._worker = None
        self._active_job_id = None

    def kick(self) -> None:
        if self._active:
            self._tick()

    @staticmethod
    def _disconnect(worker: DistroKidUploadWorker) -> None:
        disconnect_quietly(worker.progressed)
        disconnect_quietly(worker.phase_changed)
        disconnect_quietly(worker.succeeded)
        disconnect_quietly(worker.failed)
        disconnect_quietly(worker.finished)

    def _batch_context(self, batch_id: str) -> dict | None:
        key = str(batch_id or "").strip()
        if not key:
            return None
        cached = self._batch_context_cache.get(key)
        if cached is not None:
            return cached
        try:
            data = self._api.distrokid_batch_context(key)
        except (PlatformApiError, Exception):
            return None
        if isinstance(data, dict):
            self._batch_context_cache[key] = data
            return data
        return None

    def maybe_start_after_long_merge(
        self,
        *,
        settings: dict,
        run_dir: str,
        batch_id: str,
        role: str,
        album_name: str = "",
        branch: str = "long",
        profile_id: str = "",
    ) -> None:
        """Register a DistroKid job after long export/merge (not after Short itself)."""
        if not self._active:
            return
        if str(branch or "long").lower() == "reel":
            self.kick()
            return

        context = self._batch_context(batch_id) if batch_id else None
        local = DistroKidSettingsStore().load()
        if context is not None:
            enabled = bool(context.get("auto_distrokid"))
            wait_for_short = bool(context.get("auto_reel_after_video"))
            if not album_name:
                role_key = str(role or "primary").lower()
                album_name = (
                    str(context.get("secondary_album_name") or "").strip()
                    if role_key in {"secondary", "alt"}
                    else str(context.get("primary_album_name") or "").strip()
                )
        else:
            # Legacy batches / API without snapshot — fall back to live settings.
            enabled = read_boolean_setting(settings, "autoDistroKid", False)
            wait_for_short = read_boolean_setting(settings, "autoReelAfterVideo", False)

        from features.distrokid.lib.distrokid_artist import resolve_profile_id_for_role

        resolved_profile_id = resolve_profile_id_for_role(
            role=role or "primary",
            profile_id=profile_id,
            batch_context=context,
        )
        artist = resolve_distrokid_artist(
            role=role or "primary",
            settings=local,
            batch_context=context,
            profile_id=resolved_profile_id,
        )

        if not enabled:
            return

        me = None
        try:
            me = self._api.get_me()
        except Exception:
            me = None
        if me is not None and not bool(getattr(me, "distrokid_active", False)):
            job = self._store.upsert_pending(
                run_dir=run_dir,
                batch_id=batch_id,
                role=role or "primary",
                album_name=album_name,
                wait_for_short=False,
                profile_id=resolved_profile_id,
            )
            self._store.update(
                job.id,
                status="skipped_no_entitlement",
                message="DistroKid add-on not active",
            )
            emit_shell_status("DistroKid skipped: add-on not active.", tone="warning")
            return

        if wait_for_short and short_exports_ready(run_dir):
            wait_for_short = False

        job = self._store.upsert_pending(
            run_dir=run_dir,
            batch_id=batch_id,
            role=role or "primary",
            album_name=album_name,
            wait_for_short=wait_for_short,
            auto_submit=bool(local.auto_submit),
            artist_name=artist,
            profile_id=resolved_profile_id,
        )
        if wait_for_short:
            emit_shell_status(f"DistroKid queued after Short for {role or 'primary'}…")
        else:
            emit_shell_status(f"DistroKid queued for {role or 'primary'}…")
        self._tick()

    def _promote_short_ready(self) -> None:
        for job in self._store.awaiting_short_jobs():
            if short_exports_ready(job.run_dir):
                self._store.update(job.id, status="queued", message="Short ready — DistroKid queued")
                emit_shell_status(f"DistroKid unblocked after Short ({job.role})")

    def _tick(self) -> None:
        if not self._active:
            return
        from shared.services.video_pipeline_activity import is_app_quitting

        if is_app_quitting():
            return
        self._promote_short_ready()
        if self._worker is not None and self._worker.isRunning():
            return
        next_job = self._store.next_queued()
        if next_job is None:
            return
        self._start_job(next_job)

    def _resolve_artist(self, job: DistroKidJob) -> str:
        settings = DistroKidSettingsStore().load()
        context = self._batch_context(job.batch_id) if job.batch_id else None
        return resolve_distrokid_artist(
            role=job.role,
            settings=settings,
            batch_context=context,
            profile_id=job.profile_id,
        )

    def _start_job(self, job: DistroKidJob) -> None:
        self._store.update(job.id, status="running", message="DistroKid stage started")
        self._active_job_id = job.id
        request = DistroKidUploadRequest(
            run_dir=job.run_dir,
            batch_id=job.batch_id,
            album_name=job.album_name,
            role=job.role,
            auto_submit=job.auto_submit,
            job_id=job.id,
            artist_name=self._resolve_artist(job),
        )
        worker = DistroKidUploadWorker(self._api, request, parent=None)
        worker.progressed.connect(self._on_progress)
        worker.phase_changed.connect(self._on_phase)
        worker.succeeded.connect(self._on_succeeded)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(self._on_finished)
        self._worker = worker
        track_app_thread(worker)
        emit_shell_status(f"DistroKid started ({job.role})…")
        worker.start()

    def _on_progress(self, message: str) -> None:
        emit_shell_status(str(message or "DistroKid…"))
        if self._active_job_id:
            self._store.update(self._active_job_id, message=str(message or ""))

    def _on_phase(self, phase: str) -> None:
        key = str(phase or "").strip().lower()
        if key not in {"wav_downloading", "uploading", "running"}:
            return
        if self._active_job_id:
            self._store.update(self._active_job_id, status=key)  # type: ignore[arg-type]

    def _on_succeeded(self, payload: object) -> None:
        job_id = self._active_job_id
        submitted = True
        message = "DistroKid upload completed."
        duplicate = False
        if isinstance(payload, dict):
            message = str(payload.get("message") or message)
            submitted = bool(payload.get("submitted", True))
            duplicate = bool(payload.get("duplicate", False))
            job_id = str(payload.get("job_id") or job_id or "")
        if job_id:
            if duplicate:
                status = "skipped_duplicate"
            elif submitted:
                status = "success"
            else:
                status = "awaiting_manual_submit"
            self._store.update(job_id, status=status, message=message)
        emit_shell_status(message)

    def _on_failed(self, message: str) -> None:
        text = str(message or "DistroKid failed.")
        if self._active_job_id:
            status = "skipped_duplicate" if "duplicate" in text.lower() else "failed"
            self._store.update(self._active_job_id, status=status, message=text)
        emit_shell_status(f"DistroKid failed (soft): {text}", tone="warning")

    def _on_finished(self) -> None:
        worker = self._worker
        if worker is not None:
            self._disconnect(worker)
        self._worker = None
        self._active_job_id = None
        QTimer.singleShot(250, self._tick)
