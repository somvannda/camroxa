"""Unified export routing — REQ-2.5 / REQ-2.6."""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass
from typing import Any, Callable

from features.video.export_gate import export_gate
from features.video.lib.render_scene_request import ManualRenderSceneRequest
from features.video.services.export_job import ExportJob, ExportSettings
from features.video.services.in_process_export import (
    InProcessExportSession,
    build_gpu_options,
    resolve_manual_export_backend,
)

log = logging.getLogger(__name__)

ExportEventHandler = Callable[[dict], None]


@dataclass(frozen=True)
class CoordinatorExportRequest:
    mp3_path: str
    template: dict
    background_path: str
    logo_path: str
    settings: ExportSettings
    scene: ManualRenderSceneRequest
    preview: Any | None = None
    speed_mode: str = "fast"
    acquire_gate: bool = True


@dataclass(frozen=True)
class PipelineCoordinatorExportRequest:
    """Pipeline track export — always daemon/subprocess (no preview GL)."""

    mp3_path: str
    template: dict
    background_path: str
    logo_path: str
    settings: ExportSettings
    speed_mode: str = "fast"


@dataclass
class _ActiveJob:
    job_id: str
    backend: ExportJob | InProcessExportSession | None = None
    backend_name: str = ""
    fallback_from: str = ""


def resolve_coordinator_backend(request: CoordinatorExportRequest) -> str:
    """Primary backend before subprocess fallback: in-process or subprocess."""
    if (
        resolve_manual_export_backend(
            request.preview,
            scene=request.scene,
            background_path=request.background_path,
            logo_path=request.logo_path,
            mp3_path=request.mp3_path,
        )
        == "in-process"
    ):
        return "in-process"
    return "subprocess"


def _enrich_event(
    event: dict,
    *,
    backend_used: str,
    fallback_from: str = "",
) -> dict:
    payload = dict(event)
    if backend_used:
        payload["backendUsed"] = backend_used
        payload.setdefault("backend", backend_used)
    if fallback_from:
        payload["fallbackFrom"] = fallback_from
    return payload


def _log_export_backend(
    *,
    job_id: str,
    backend_used: str,
    fallback_from: str,
    exit_code: int,
    mp3_path: str,
) -> None:
    log.info(
        "export job finished job_id=%s backendUsed=%s fallbackFrom=%s exit_code=%d mp3=%s",
        job_id,
        backend_used or "unknown",
        fallback_from or "-",
        exit_code,
        mp3_path,
    )


def run_subprocess_export(
    request: PipelineCoordinatorExportRequest,
    *,
    on_event: ExportEventHandler | None = None,
    fallback_from: str = "",
    on_job_started: Callable[[ExportJob], None] | None = None,
    allow_daemon: bool = True,
) -> tuple[int, str, ExportJob]:
    """Run a single daemon/subprocess export (pipeline or manual fallback path)."""
    job = ExportJob(
        mp3_path=request.mp3_path,
        template=request.template,
        background_path=request.background_path,
        logo_path=request.logo_path,
        settings=request.settings,
        on_event=None,
    )
    if on_job_started is not None:
        on_job_started(job)

    def _on_event(event: dict) -> None:
        if on_event is None:
            return
        backend = getattr(job, "backend_used", "") or "subprocess"
        on_event(_enrich_event(event, backend_used=backend, fallback_from=fallback_from))

    job.on_event = _on_event
    code = int(job.run_blocking(allow_daemon=allow_daemon))
    backend_used = getattr(job, "backend_used", "") or "subprocess"
    return code, backend_used, job


class ExportCoordinator:
    """Routes manual export through in-process GL, daemon, or one-shot subprocess."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: dict[str, _ActiveJob] = {}
        self._progress_callbacks: list[ExportEventHandler] = []
        self._running_job_id: str | None = None
        self._last_exit_code: int = 1
        self._cancel_requested = False

    @property
    def running_job_id(self) -> str | None:
        return self._running_job_id

    @property
    def last_exit_code(self) -> int:
        return self._last_exit_code

    def on_progress(self, callback: ExportEventHandler) -> None:
        self._progress_callbacks.append(callback)

    def cancel_export(self, job_id: str) -> None:
        self._cancel_requested = True
        with self._lock:
            job = self._jobs.get(job_id)
        if job is not None and job.backend is not None:
            job.backend.cancel()

    def start_export(self, request: CoordinatorExportRequest) -> str:
        job_id = uuid.uuid4().hex
        active = _ActiveJob(job_id=job_id)
        self._running_job_id = job_id
        self._last_exit_code = 1
        self._cancel_requested = False
        with self._lock:
            self._jobs[job_id] = active

        if request.acquire_gate:
            def _on_wait(active_count: int, limit: int) -> None:
                self._emit(
                    {
                        "status": "running",
                        "message": f"Waiting for export slot ({active_count}/{limit} busy)…",
                        "progress": 0.01,
                    }
                )

            export_gate.acquire(
                cancel_check=lambda: self._cancel_requested,
                timeout_sec=120.0,
                on_wait=_on_wait,
            )
        try:
            self._last_exit_code = self._run_with_fallback(request, active)
        finally:
            _log_export_backend(
                job_id=job_id,
                backend_used=active.backend_name,
                fallback_from=active.fallback_from,
                exit_code=self._last_exit_code,
                mp3_path=request.mp3_path,
            )
            if request.acquire_gate:
                export_gate.release()
            with self._lock:
                self._jobs.pop(job_id, None)
            self._running_job_id = None
        return job_id

    def _run_with_fallback(self, request: CoordinatorExportRequest, active: _ActiveJob) -> int:
        if resolve_coordinator_backend(request) == "in-process":
            active.backend_name = "in-process"
            code = self._run_in_process(request, active)
            if code == 0:
                return 0
            active.fallback_from = "in-process"
            self._emit(
                {
                    "status": "warning",
                    "message": "In-process export failed; retrying via subprocess…",
                    "fallbackFrom": "in-process",
                    "backendUsed": "subprocess",
                }
            )
        return self._run_subprocess(request, active, fallback_from=active.fallback_from)

    def _run_in_process(self, request: CoordinatorExportRequest, active: _ActiveJob) -> int:
        preview = request.preview
        if preview is None:
            return -1
        analyzer = getattr(preview, "analyzer", None)
        opts = build_gpu_options(
            scene=request.scene,
            export_settings=request.settings,
            speed_mode=request.speed_mode,
        )

        def _on_event(event: dict) -> None:
            self._emit(_enrich_event(event, backend_used="in-process"))

        session = InProcessExportSession(
            preview=preview,
            opts=opts,
            on_event=_on_event,
            analyzer=analyzer,
        )
        active.backend = session
        try:
            return int(session.run())
        except Exception as exc:
            self._emit(
                _enrich_event(
                    {
                        "status": "log",
                        "message": f"In-process export error: {exc}",
                    },
                    backend_used="in-process",
                )
            )
            return -1

    def _run_subprocess(
        self,
        request: CoordinatorExportRequest,
        active: _ActiveJob,
        *,
        fallback_from: str = "",
    ) -> int:
        pipeline_request = PipelineCoordinatorExportRequest(
            mp3_path=request.mp3_path,
            template=request.template,
            background_path=request.background_path,
            logo_path=request.logo_path,
            settings=request.settings,
            speed_mode=request.speed_mode,
        )

        def _on_event(event: dict) -> None:
            job_backend = getattr(job, "backend_used", "") or ""
            if fallback_from:
                backend = job_backend or "subprocess"
            else:
                backend = job_backend or active.backend_name or "subprocess"
            self._emit(_enrich_event(event, backend_used=backend, fallback_from=fallback_from))

        job = ExportJob(
            mp3_path=pipeline_request.mp3_path,
            template=pipeline_request.template,
            background_path=pipeline_request.background_path,
            logo_path=pipeline_request.logo_path,
            settings=pipeline_request.settings,
            on_event=_on_event,
        )
        active.backend = job
        code = int(job.run_blocking())
        active.backend_name = getattr(job, "backend_used", "") or "subprocess"
        return code

    def _emit(self, event: dict) -> None:
        for callback in self._progress_callbacks:
            callback(event)
