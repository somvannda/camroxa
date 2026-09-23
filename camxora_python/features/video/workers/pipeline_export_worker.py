"""Background worker for pipeline batch GPU video export."""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QThread, Signal

from features.video.export_gate import export_gate
from features.video.lib.export_failure_log import (
    format_export_failure_message,
    is_export_milestone_message,
)
from features.video.lib.export_output_validity import (
    describe_export_output_failure,
    export_matches_batch_specs,
    is_usable_export_output,
)
from features.video.lib.render_scene_request import (
    build_pipeline_export_output_path,
    build_pipeline_long_output_path,
)
from features.video.lib.text_domain_runtime import inject_text_domains_into_template
from features.video.services.export_coordinator import (
    PipelineCoordinatorExportRequest,
    run_subprocess_export,
)
from features.video.services.export_job import ExportJob, ExportSettings, find_ffmpeg_from_path_hint
from shared.services.app_logger import log_error, log_info

TRACK_EXPORT_MAX_ATTEMPTS = 3


@dataclass(frozen=True)
class PipelineExportRequest:
    run_dir: str
    background_path: str
    logo_path: str
    branch: str
    batch_id: str
    role: str
    template: dict
    mp3_paths: list[str]
    settings: dict
    width: int
    height: int
    fps: int = 30
    speed_mode: str = "fast"
    album_mp3_paths: list[str] | None = None


@dataclass(frozen=True, slots=True)
class TrackExportAttemptResult:
    output_path: str | None
    attempts: int
    error: str = ""
    skipped: bool = False


def export_one_track_with_retries(
    mp3_path: str,
    *,
    export_one: Callable[[str], str],
    max_attempts: int = TRACK_EXPORT_MAX_ATTEMPTS,
    should_stop: Callable[[], bool] | None = None,
    on_retry: Callable[[int, int, str], None] | None = None,
) -> TrackExportAttemptResult:
    """Run one track up to ``max_attempts`` times, then skip instead of aborting the album."""
    last_error = ""
    attempts = max(1, int(max_attempts))
    for attempt in range(1, attempts + 1):
        if should_stop is not None and should_stop():
            return TrackExportAttemptResult(None, attempt - 1, "Video export stopped.", skipped=False)
        try:
            output_path = export_one(mp3_path)
        except Exception as exc:
            last_error = str(exc) or "Video export failed."
            if attempt < attempts:
                if on_retry is not None:
                    on_retry(attempt, attempts, last_error)
                continue
            return TrackExportAttemptResult(None, attempt, last_error, skipped=True)
        return TrackExportAttemptResult(output_path, attempt, skipped=False)
    return TrackExportAttemptResult(None, attempts, last_error, skipped=True)


class VideoPipelineExportWorker(QThread):
    progressed = Signal(object)
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, request: PipelineExportRequest, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("VideoPipelineExportWorker")
        self._request = request
        self._cancel_requested = False
        self._active_jobs: dict[str, ExportJob] = {}
        self._jobs_lock = threading.Lock()

    def cancel(self) -> None:
        self._cancel_requested = True
        with self._jobs_lock:
            jobs = list(self._active_jobs.values())
        for job in jobs:
            job.cancel()

    def run(self) -> None:
        request = self._request
        mp3_paths = [str(path).strip() for path in request.mp3_paths if str(path).strip()]
        album_mp3_paths = [
            str(path).strip()
            for path in (request.album_mp3_paths or mp3_paths)
            if str(path).strip()
        ]
        if not mp3_paths:
            self.failed.emit("No MP3 files were found in the selected run directory.")
            return

        workers_raw = request.settings.get("videoExportWorkers", request.settings.get("perfExportWorkers", 1))
        from visualizer.export_gpu_tier import resolve_pipeline_export_workers

        worker_limit = resolve_pipeline_export_workers(
            workers_raw,
            default=1,
            speed_mode=request.speed_mode,
            width=int(request.width),
            height=int(request.height),
        )
        worker_count = min(worker_limit, len(mp3_paths))
        export_gate.set_limit(worker_limit)
        # Parallel tracks cannot share the single-job warm daemon.
        allow_daemon = worker_count <= 1
        ffmpeg_path = find_ffmpeg_from_path_hint(str(request.settings.get("ffmpegPath") or "ffmpeg"))

        total = len(mp3_paths)
        completed = 0
        last_output_path: str | None = None
        skipped: list[str] = []
        skipped_errors: list[str] = []
        progress_lock = threading.Lock()
        queue: list[str] = list(mp3_paths)
        queue_lock = threading.Lock()

        def emit_progress(
            *,
            message: str,
            current_path: str = "",
            output_path: str = "",
            track_progress: float | None = None,
            video_codec: str | None = None,
            backend_used: str | None = None,
            fallback_from: str | None = None,
            status: str = "running",
        ) -> None:
            with progress_lock:
                done = completed
            if track_progress is not None and total > 0:
                blended = (done + max(0.0, min(1.0, float(track_progress)))) / total
                percent = int(round(blended * 100))
            else:
                percent = int(round((done / total) * 100)) if total > 0 else 0
            payload: dict[str, object] = {
                "status": status,
                "message": message,
                "progressPercent": percent,
                "completedJobs": done,
                "totalJobs": total,
                "currentMp3Path": current_path,
                "outputPath": output_path,
                "workers": worker_count,
            }
            if video_codec:
                payload["videoCodec"] = video_codec
            if backend_used:
                payload["backendUsed"] = backend_used
                payload["backend"] = backend_used
            if fallback_from:
                payload["fallbackFrom"] = fallback_from
            self.progressed.emit(payload)

        def run_single_job(mp3_path: str) -> str:
            if self._cancel_requested:
                raise RuntimeError("Video export stopped.")

            final_output_path = build_pipeline_export_output_path(
                mp3_path=mp3_path,
                output_dir=request.run_dir,
                branch=request.branch,
            )
            # Skip only when existing file matches THIS batch's resolution/FPS/audio
            # (rejects stale leftovers from Draft/other FPS/old audio layout).
            if export_matches_batch_specs(
                final_output_path,
                width=int(request.width),
                height=int(request.height),
                fps=int(request.fps),
                ffmpeg_path=ffmpeg_path,
                audio_path=mp3_path,
            ):
                return final_output_path

            long_output_path = build_pipeline_long_output_path(
                mp3_path=mp3_path,
                output_dir=request.run_dir,
            )
            backup_path = f"{long_output_path}._std_backup"
            backed_up_standard = False
            if request.branch == "reel" and Path(long_output_path).exists():
                Path(long_output_path).rename(backup_path)
                backed_up_standard = True

            export_gate.acquire(
                cancel_check=lambda: self._cancel_requested,
                timeout_sec=300.0,
                on_wait=lambda active, limit: emit_progress(
                    message=f"Waiting for export slot ({active}/{limit} busy)…",
                    current_path=mp3_path,
                    output_path=long_output_path,
                    track_progress=0.01,
                ),
            )
            try:
                if self._cancel_requested:
                    raise RuntimeError("Video export stopped.")
                export_gate.throttle_spawn()
                # Highlight the song being rendered in the title list for this job.
                job_template = inject_text_domains_into_template(
                    dict(request.template),
                    track_paths=list(album_mp3_paths),
                    active_track_path=mp3_path,
                )
                export_request = PipelineCoordinatorExportRequest(
                    mp3_path=mp3_path,
                    template=job_template,
                    background_path=request.background_path,
                    logo_path=request.logo_path,
                    settings=ExportSettings(
                        ffmpeg_path=ffmpeg_path,
                        output_dir=request.run_dir,
                        output_path=long_output_path,
                        fps=int(request.fps),
                        width=int(request.width),
                        height=int(request.height),
                        speed_mode=request.speed_mode,
                    ),
                    speed_mode=request.speed_mode,
                )
                try:
                    def _register_active_job(export_job: ExportJob, path: str = mp3_path) -> None:
                        with self._jobs_lock:
                            self._active_jobs[path] = export_job

                    last_logged_milestone = ""

                    def _on_export_event(event: dict, path: str = mp3_path) -> None:
                        nonlocal last_logged_milestone
                        message = str(event.get("message") or event.get("status") or "Exporting…")
                        status = str(event.get("status") or "running").strip().lower()
                        if status in {"failed", "error"} or is_export_milestone_message(message):
                            stamped = f"{Path(path).name}: {message}"
                            if stamped != last_logged_milestone:
                                last_logged_milestone = stamped
                                if status in {"failed", "error"}:
                                    log_error(stamped, category="export")
                                else:
                                    log_info(stamped, category="export")
                        emit_progress(
                            status=str(event.get("status") or "running"),
                            message=message,
                            current_path=path,
                            output_path=long_output_path,
                            track_progress=(
                                float(event["progress"])
                                if isinstance(event.get("progress"), (int, float))
                                else None
                            ),
                            video_codec=str(event.get("videoCodec") or "").strip() or None,
                            backend_used=str(event.get("backendUsed") or event.get("backend") or "").strip()
                            or None,
                            fallback_from=str(event.get("fallbackFrom") or "").strip() or None,
                        )

                    log_info(f"Starting export · {Path(mp3_path).name}", category="export")
                    code, backend_used, job = run_subprocess_export(
                        export_request,
                        on_event=_on_export_event,
                        on_job_started=_register_active_job,
                        allow_daemon=allow_daemon,
                    )
                finally:
                    with self._jobs_lock:
                        self._active_jobs.pop(mp3_path, None)
                if self._cancel_requested:
                    raise RuntimeError("Video export stopped.")
                if code != 0:
                    detail = str(getattr(job, "last_error_detail", "") or "").strip()
                    message = format_export_failure_message(
                        exit_code=code,
                        mp3_path=mp3_path,
                        detail=detail,
                        backend_used=backend_used,
                    )
                    log_error(message, category="export")
                    raise RuntimeError(message)
            finally:
                export_gate.release()

            try:
                if request.branch == "reel":
                    if not Path(long_output_path).exists():
                        raise RuntimeError(f"Reel export did not produce {Path(long_output_path).name}.")
                    Path(long_output_path).rename(final_output_path)
                if not is_usable_export_output(
                    final_output_path,
                    ffmpeg_path=ffmpeg_path,
                    audio_path=mp3_path,
                    require_media=True,
                    expected_duration_sec=float(
                        getattr(job, "rendered_duration_sec", 0.0) or 0.0
                    ),
                ):
                    reason = describe_export_output_failure(
                        final_output_path,
                        ffmpeg_path=ffmpeg_path,
                        audio_path=mp3_path,
                        expected_duration_sec=float(
                            getattr(job, "rendered_duration_sec", 0.0) or 0.0
                        ),
                    )
                    raise RuntimeError(
                        f"Video export did not produce a usable output for "
                        f"{Path(mp3_path).name} ({reason})."
                    )
                return final_output_path
            finally:
                if backed_up_standard and Path(backup_path).exists():
                    try:
                        Path(backup_path).rename(long_output_path)
                    except OSError:
                        pass

        def worker_loop() -> None:
            nonlocal completed, last_output_path
            while not self._cancel_requested:
                with queue_lock:
                    if not queue:
                        return
                    mp3_path = queue.pop(0)
                    index = total - len(queue)

                branch_label = "Long" if request.branch == "long" else "Reel"
                emit_progress(
                    message=(
                        f"Exporting {branch_label} {index}/{total} · {Path(mp3_path).name}"
                        f" · {worker_count} worker{'s' if worker_count != 1 else ''}"
                    ),
                    current_path=mp3_path,
                )

                def _on_retry(attempt: int, attempts: int, error: str, path: str = mp3_path) -> None:
                    log_error(
                        f"Retry {attempt}/{attempts} · {Path(path).name}: {error}",
                        category="export",
                    )
                    emit_progress(
                        message=f"Retry {attempt}/{attempts} · {Path(path).name}",
                        current_path=path,
                    )

                result = export_one_track_with_retries(
                    mp3_path,
                    export_one=run_single_job,
                    should_stop=lambda: self._cancel_requested,
                    on_retry=_on_retry,
                )
                if self._cancel_requested:
                    return
                if result.skipped or not result.output_path:
                    with progress_lock:
                        skipped.append(mp3_path)
                        if result.error:
                            skipped_errors.append(f"{Path(mp3_path).name}: {result.error}")
                    log_error(
                        f"Skipped after {result.attempts} attempt(s) · {Path(mp3_path).name}: "
                        f"{result.error or 'Video export failed.'}",
                        category="export",
                    )
                    emit_progress(
                        message=(
                            f"Skipped {Path(mp3_path).name} after {result.attempts} attempt(s) — "
                            "continuing album."
                        ),
                        current_path=mp3_path,
                    )
                    continue

                with progress_lock:
                    completed += 1
                    last_output_path = result.output_path
                branch_label = "long" if request.branch == "long" else "reel"
                emit_progress(
                    message=f"Exported {completed}/{total} {branch_label} video(s).",
                    current_path=mp3_path,
                    output_path=result.output_path,
                )

        started_at = time.time()
        worker_label = f"{worker_count} worker{'s' if worker_count != 1 else ''}"
        emit_progress(message=f"Starting {request.branch} export · {worker_label}…")
        try:
            with ThreadPoolExecutor(max_workers=worker_count) as pool:
                futures = [pool.submit(worker_loop) for _ in range(worker_count)]
                for future in as_completed(futures):
                    future.result()
        except Exception as exc:
            if not self._cancel_requested:
                self.failed.emit(str(exc) or "Video export failed.")
            return

        if self._cancel_requested:
            self.failed.emit("Video export stopped.")
            return
        if completed <= 0:
            detail = skipped_errors[0] if skipped_errors else "Video export failed."
            self.failed.emit(
                f"Album export failed after {TRACK_EXPORT_MAX_ATTEMPTS} attempt(s) per track. {detail}"
            )
            return

        elapsed = max(0.0, time.time() - started_at)
        branch_label = "long" if request.branch == "long" else "reel"
        skipped_note = f" · {len(skipped)} skipped" if skipped else ""
        self.succeeded.emit(
            {
                "completed": completed,
                "total": total,
                "skipped": len(skipped),
                "skippedPaths": list(skipped),
                "lastOutputPath": last_output_path,
                "branch": request.branch,
                "elapsedSec": elapsed,
                "message": (
                    f"Export complete · {completed}/{total} {branch_label} video(s){skipped_note}."
                ),
            }
        )
