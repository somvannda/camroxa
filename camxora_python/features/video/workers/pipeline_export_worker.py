"""Background worker for pipeline batch GPU video export."""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from features.video.export_gate import export_gate
from features.video.lib.render_scene_request import (
    build_pipeline_export_output_path,
    build_pipeline_long_output_path,
    is_valid_export_output,
)
from features.video.lib.text_domain_runtime import inject_text_domains_into_template
from features.video.services.export_job import ExportJob, ExportSettings, find_ffmpeg_from_path_hint


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
    speed_mode: str = "balanced"


class VideoPipelineExportWorker(QThread):
    progressed = Signal(object)
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, request: PipelineExportRequest, parent=None) -> None:
        super().__init__(parent)
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
        if not mp3_paths:
            self.failed.emit("No MP3 files were found in the selected run directory.")
            return

        workers_raw = request.settings.get("videoExportWorkers", request.settings.get("perfExportWorkers", 1))
        try:
            worker_limit = max(1, min(10, int(workers_raw)))
        except (TypeError, ValueError):
            worker_limit = 1
        worker_count = min(worker_limit, len(mp3_paths))
        export_gate.set_limit(worker_limit)

        total = len(mp3_paths)
        completed = 0
        last_output_path: str | None = None
        failures: list[str] = []
        progress_lock = threading.Lock()
        queue: list[str] = list(mp3_paths)
        queue_lock = threading.Lock()

        def emit_progress(*, message: str, current_path: str = "", output_path: str = "") -> None:
            with progress_lock:
                done = completed
            percent = int(round((done / total) * 100)) if total > 0 else 0
            self.progressed.emit(
                {
                    "status": "running",
                    "message": message,
                    "progressPercent": percent,
                    "completedJobs": done,
                    "totalJobs": total,
                    "currentMp3Path": current_path,
                    "outputPath": output_path,
                }
            )

        def run_single_job(mp3_path: str) -> str:
            if self._cancel_requested:
                raise RuntimeError("Video export stopped.")

            final_output_path = build_pipeline_export_output_path(
                mp3_path=mp3_path,
                output_dir=request.run_dir,
                branch=request.branch,
            )
            if is_valid_export_output(final_output_path):
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

            export_gate.acquire()
            try:
                if self._cancel_requested:
                    raise RuntimeError("Video export stopped.")
                export_gate.throttle_spawn()
                ffmpeg_path = find_ffmpeg_from_path_hint(str(request.settings.get("ffmpegPath") or "ffmpeg"))
                # Highlight the song being rendered in the title list for this job.
                job_template = inject_text_domains_into_template(
                    dict(request.template),
                    track_paths=list(mp3_paths),
                    active_track_path=mp3_path,
                )
                job = ExportJob(
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
                    on_event=lambda event, path=mp3_path: emit_progress(
                        message=str(event.get("message") or event.get("status") or "Exporting…"),
                        current_path=path,
                        output_path=long_output_path,
                    ),
                )
                with self._jobs_lock:
                    self._active_jobs[mp3_path] = job
                try:
                    code = job.run_blocking()
                finally:
                    with self._jobs_lock:
                        self._active_jobs.pop(mp3_path, None)
                if self._cancel_requested:
                    raise RuntimeError("Video export stopped.")
                if code != 0:
                    raise RuntimeError(f"Export failed with exit code {code} for {Path(mp3_path).name}.")
            finally:
                export_gate.release()

            try:
                if request.branch == "reel":
                    if not Path(long_output_path).exists():
                        raise RuntimeError(f"Reel export did not produce {Path(long_output_path).name}.")
                    Path(long_output_path).rename(final_output_path)
                if not is_valid_export_output(final_output_path):
                    raise RuntimeError(
                        f"Video export did not produce a valid output for {Path(mp3_path).name}."
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
            while not self._cancel_requested and not failures:
                with queue_lock:
                    if not queue:
                        return
                    mp3_path = queue.pop(0)
                    index = total - len(queue)

                branch_label = "Long" if request.branch == "long" else "Reel"
                emit_progress(
                    message=f"Exporting {branch_label} {index}/{total} · {Path(mp3_path).name}",
                    current_path=mp3_path,
                )
                try:
                    output_path = run_single_job(mp3_path)
                except Exception as exc:
                    if self._cancel_requested:
                        return
                    with progress_lock:
                        failures.append(str(exc) or "Video export failed.")
                    return

                with progress_lock:
                    completed += 1
                    last_output_path = output_path
                branch_label = "long" if request.branch == "long" else "reel"
                emit_progress(
                    message=f"Exported {completed}/{total} {branch_label} video(s).",
                    current_path=mp3_path,
                    output_path=output_path,
                )

        started_at = time.time()
        emit_progress(message=f"Starting {request.branch} export…")
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
        if failures:
            self.failed.emit(failures[0])
            return

        elapsed = max(0.0, time.time() - started_at)
        branch_label = "long" if request.branch == "long" else "reel"
        self.succeeded.emit(
            {
                "completed": completed,
                "total": total,
                "lastOutputPath": last_output_path,
                "branch": request.branch,
                "elapsedSec": elapsed,
                "message": f"Export complete · {completed}/{total} {branch_label} video(s).",
            }
        )
