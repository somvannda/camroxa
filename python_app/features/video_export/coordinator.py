"""ExportCoordinator — owns video export orchestration.

Uses dependency injection to avoid direct MainWindow references.
"""
from __future__ import annotations

import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from ..ports import EventBusPort, LoggerPort
from ...services.video_export import ExportJob, ExportSettings, find_ffmpeg_from_path_hint
from ...visualizer.contracts import RenderRequest
from ...app.ui_bus import UiBus
from ...database.persistence import DbCfg
from .export_batch import ExportBatch


class ExportCoordinator:
    """Owns video export orchestration extracted from MainWindow.

    All host dependencies are injected via constructor parameters so the
    coordinator is instantiable without a QApplication.
    """

    def __init__(
        self,
        *,
        bus: EventBusPort,
        settings_accessor: Callable[[], dict],
        export_batches_accessor: Callable[[], dict[str, ExportBatch]],
        export_batches_setter: Callable[[dict[str, ExportBatch]], None],
        export_workers_accessor: Callable[[], int],
        export_workers_setter: Callable[[int], None],
        template_accessor: Callable[[], dict],
        resolved_output_resolution_fn: Callable[[], tuple[int, int]],
        ffmpeg_path_accessor: Callable[[], str],
        iter_mp3_paths_fn: Callable[[], list[str]],
        pick_ffmpeg_fn: Callable[[], None],
        prompt_output_dir_fn: Callable[[], str],
        preview_bg_path_accessor: Callable[[], str],
        preview_logo_path_accessor: Callable[[], str],
        set_export_status_fn: Callable[[str], None],
        refresh_export_output_label_fn: Callable[[], None],
        update_export_overall_progress_fn: Callable[[], None],
        refresh_export_detail_fn: Callable[[], None],
        normalize_export_stage_message_fn: Callable[[str], str],
        format_export_percent_fn: Callable[[float], str],
        export_auto_merge_enabled_fn: Callable[[], bool],
        export_worker_limit_fn: Callable[[], int],
        set_last_export_path_fn: Callable[[str], None],
        get_export_merge_state_fn: Callable[[], dict],
        set_export_merge_state_fn: Callable[[dict], None],
        export_detail_label_set_fn: Callable[[str], None],
        export_merge_progress_set_fn: Callable[[bool, int, str], None] | None = None,
        btn_export_merge_stop_set_fn: Callable[[bool], None] | None = None,
        auto_video_coordinator_accessor: Callable[[], Any] | None = None,
        logger: LoggerPort | None = None,
    ) -> None:
        if bus is None:
            raise ValueError("ExportCoordinator requires a non-None bus")
        if settings_accessor is None:
            raise ValueError("ExportCoordinator requires a non-None settings_accessor")
        self._bus = bus
        self._settings_accessor = settings_accessor
        self._export_batches_accessor = export_batches_accessor
        self._export_batches_setter = export_batches_setter
        self._export_workers_accessor = export_workers_accessor
        self._export_workers_setter = export_workers_setter
        self._template_accessor = template_accessor
        self._resolved_output_resolution_fn = resolved_output_resolution_fn
        self._ffmpeg_path_accessor = ffmpeg_path_accessor
        self._iter_mp3_paths_fn = iter_mp3_paths_fn
        self._pick_ffmpeg_fn = pick_ffmpeg_fn
        self._prompt_output_dir_fn = prompt_output_dir_fn
        self._preview_bg_path_accessor = preview_bg_path_accessor
        self._preview_logo_path_accessor = preview_logo_path_accessor
        self._set_export_status_fn = set_export_status_fn
        self._refresh_export_output_label_fn = refresh_export_output_label_fn
        self._update_export_overall_progress_fn = update_export_overall_progress_fn
        self._refresh_export_detail_fn = refresh_export_detail_fn
        self._normalize_export_stage_message_fn = normalize_export_stage_message_fn
        self._format_export_percent_fn = format_export_percent_fn
        self._export_auto_merge_enabled_fn = export_auto_merge_enabled_fn
        self._export_worker_limit_fn = export_worker_limit_fn
        self._set_last_export_path_fn = set_last_export_path_fn
        self._get_export_merge_state_fn = get_export_merge_state_fn
        self._set_export_merge_state_fn = set_export_merge_state_fn
        self._export_detail_label_set_fn = export_detail_label_set_fn
        self._export_merge_progress_set_fn = export_merge_progress_set_fn
        self._btn_export_merge_stop_set_fn = btn_export_merge_stop_set_fn
        self._auto_video_coordinator_accessor = auto_video_coordinator_accessor
        self._logger = logger
        # Internal state for current export tracking
        self._current_export_mp3: str = ""
        self._current_export_frame: int = 0
        self._current_export_total_frames: int = 0
        self._current_export_stage: str = ""

    def start_export_workers(self, batch: ExportBatch) -> None:
        export_batches = self._export_batches_accessor()
        total_active = sum(len(b.jobs) for b in export_batches.values() if b.running)
        max_workers = self._export_workers_accessor()
        while batch.queue and total_active < max_workers:
            mp3 = str(batch.queue.pop(0) or "").strip()
            if not mp3:
                continue
            batch.job_state[mp3] = {
                "progress": 0.0,
                "stage": "Preparing export...",
                "frame": 0,
                "totalFrames": 0,
                "outputPath": "",
            }
            speed_mode = str((self._settings_accessor() or {}).get("videoExportSpeedMode", "balanced")).strip() or "balanced"
            ow, oh = self._resolved_output_resolution_fn()
            template = self._template_accessor()
            render_request = RenderRequest(
                audio_path=mp3,
                output_path=batch.output_dir,
                width=int(ow),
                height=int(oh),
                fps=30,
                template=template,
                background_path=batch.bg_path,
                logo_path=batch.logo_path,
            )
            job = ExportJob.from_render_request(
                render_request,
                ffmpeg_path=batch.ffmpeg_path,
                speed_mode=speed_mode,
                on_event=lambda evt, mp3_path=mp3, bk=batch.batch_key: self._bus.emit(  # type: ignore[misc]
                    "export_event",
                    {**(evt or {}), "mp3Path": mp3_path, "batchKey": bk}
                ),
                on_exit=lambda code, mp3_path=mp3, bk=batch.batch_key: self._bus.emit(  # type: ignore[misc]
                    "export_done",
                    {"mp3Path": mp3_path, "code": int(code), "batchKey": bk}
                ),
            )
            batch.jobs[mp3] = job
            job.start()
            total_active += 1

    def start_batch_export(self) -> None:
        mp3s = self._iter_mp3_paths_fn()
        if not mp3s:
            return
        ffmpeg_path = find_ffmpeg_from_path_hint(self._ffmpeg_path_accessor())
        if not ffmpeg_path:
            self._pick_ffmpeg_fn()
            ffmpeg_path = find_ffmpeg_from_path_hint(self._ffmpeg_path_accessor())
        output_dir = self._prompt_output_dir_fn()
        if not ffmpeg_path or not output_dir:
            return
        settings = self._settings_accessor()
        bg_path = self._preview_bg_path_accessor() or str((settings or {}).get("videoRenderBackgroundPath", "")).strip()
        if not bg_path:
            return
        logo_path = self._preview_logo_path_accessor() or ""

        batch_key = f"{output_dir}_{int(time.time())}"
        batch = ExportBatch(
            batch_key=batch_key,
            output_dir=str(output_dir),
            ffmpeg_path=str(ffmpeg_path),
            bg_path=bg_path,
            logo_path=logo_path,
            queue=list(mp3s),
            mp3s=list(mp3s),
            total_count=len(mp3s),
            auto_merge_after=self._export_auto_merge_enabled_fn(),
        )
        export_batches = self._export_batches_accessor()
        export_batches[batch_key] = batch
        self._export_workers_setter(self._export_worker_limit_fn())
        batch.running = True
        self._set_export_status_fn(f"Starting batch: {len(mp3s)} tracks → {output_dir}")
        self._refresh_export_output_label_fn()
        self._update_export_overall_progress_fn()
        self.start_export_workers(batch)

    def stop_export(self) -> None:
        export_batches = self._export_batches_accessor()
        for batch in list(export_batches.values()):
            for job in list(batch.jobs.values()):
                try:
                    job.cancel()
                except Exception:
                    continue
            batch.queue = []
            batch.jobs = {}
            batch.job_state = {}
            batch.running = False
        self._export_batches_setter({})
        self._set_export_status_fn("Stopped")

    def stop_export_for_batch(self, batch_key: str) -> None:
        export_batches = self._export_batches_accessor()
        batch = export_batches.get(batch_key)
        if not batch:
            return
        for job in list(batch.jobs.values()):
            try:
                job.cancel()
            except Exception:
                continue
        batch.queue = []
        batch.jobs = {}
        batch.job_state = {}
        batch.running = False
        export_batches.pop(batch_key, None)

    def stop_export_merge(self) -> None:
        merge_state = self._get_export_merge_state_fn()
        if not merge_state.get("running", False):
            return
        self._set_export_merge_state_fn({"cancel_requested": True})
        proc = merge_state.get("proc")
        if proc is not None:
            try:
                proc.terminate()
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        self._bus.emit("export_event", {"status": "merge_cancelled", "message": "Stopping merge..."})

    def on_export_event(self, evt: dict) -> None:
        if not isinstance(evt, dict):
            return
        self.handle_export_started(evt)
        self.handle_export_stage_changed(evt)
        self._update_export_overall_progress_fn()

        handler_map = {
            "running": self.handle_export_progress,
            "done": self.handle_export_completed,
            "failed": self.handle_export_failed,
            "merge_done": self.handle_export_completed,
            "merge_failed": self.handle_export_failed,
            "merge_started": self.handle_export_status,
            "merge_warning": self.handle_export_status,
            "merge_cancelled": self.handle_export_status,
            "merge_progress": self.handle_export_status,
        }
        handler = handler_map.get(str(evt.get("status", "")).strip().lower())
        if handler:
            handler(evt)

    def find_batch_for_mp3(self, mp3_path: str) -> tuple[str | None, ExportBatch | None]:
        export_batches = self._export_batches_accessor()
        for bk, batch in export_batches.items():
            if mp3_path in batch.jobs or mp3_path in batch.job_state or mp3_path in batch.mp3s:
                return bk, batch
        return None, None

    def handle_export_started(self, evt: dict) -> None:
        export_batches = self._export_batches_accessor()
        mp3_path = str(evt.get("mp3Path", "") or "").strip()
        batch_key = str(evt.get("batchKey", "") or "").strip()
        st = str(evt.get("status", "")).strip().lower()
        prog = evt.get("progress", None)
        output_path = str(evt.get("outputPath", "") or "").strip()
        if output_path:
            self._set_last_export_path_fn(output_path)
            self._refresh_export_output_label_fn()
        frame = evt.get("frame", None)
        total_frames = evt.get("totalFrames", None)

        batch = export_batches.get(batch_key) if batch_key else None
        if not batch:
            _, batch = self.find_batch_for_mp3(mp3_path)
        if not batch or mp3_path not in batch.job_state:
            return

        if isinstance(frame, (int, float)):
            batch.job_state[mp3_path]["frame"] = max(0, int(frame))
        if isinstance(total_frames, (int, float)):
            batch.job_state[mp3_path]["totalFrames"] = max(0, int(total_frames))
        if output_path:
            batch.job_state[mp3_path]["outputPath"] = output_path

        next_ratio = None
        if isinstance(prog, (int, float)):
            next_ratio = float(prog)
        tf = int(batch.job_state[mp3_path].get("totalFrames", 0) or 0)
        fr = int(batch.job_state[mp3_path].get("frame", 0) or 0)
        if tf > 0 and fr > 0:
            frame_ratio = float(fr) / float(max(1, tf))
            next_ratio = frame_ratio if next_ratio is None else max(next_ratio, frame_ratio)
        if next_ratio is not None and st in {"running", "done"}:
            batch.job_state[mp3_path]["progress"] = max(
                float(batch.job_state[mp3_path].get("progress", 0.0) or 0.0),
                float(next_ratio),
            )
        self._current_export_mp3 = mp3_path
        self._current_export_frame = int(batch.job_state[mp3_path].get("frame", 0) or 0)
        self._current_export_total_frames = int(batch.job_state[mp3_path].get("totalFrames", 0) or 0)

    def handle_export_stage_changed(self, evt: dict) -> None:
        export_batches = self._export_batches_accessor()
        mp3_path = str(evt.get("mp3Path", "") or "").strip()
        batch_key = str(evt.get("batchKey", "") or "").strip()
        msg = str(evt.get("message", "")).strip()
        stage_msg = self._normalize_export_stage_message_fn(msg)

        batch = export_batches.get(batch_key) if batch_key else None
        if not batch:
            _, batch = self.find_batch_for_mp3(mp3_path)
        if not batch or mp3_path not in batch.job_state:
            return

        if stage_msg:
            batch.job_state[mp3_path]["stage"] = stage_msg
        self._current_export_stage = str(batch.job_state[mp3_path].get("stage", "") or "").strip()

    def handle_export_progress(self, evt: dict) -> None:
        export_batches = self._export_batches_accessor()
        mp3_path = str(evt.get("mp3Path", "") or "").strip()
        current_name = Path(mp3_path).name if mp3_path else "Unknown MP3"
        total_running = sum(len(b.jobs) for b in export_batches.values())
        total_completed = sum(b.completed_count for b in export_batches.values())
        total_count = sum(b.total_count for b in export_batches.values())
        self._set_export_status_fn(
            f"Exporting {total_completed}/{total_count} done · {total_running} running: {current_name}"
        )
        self._refresh_export_detail_fn()

    def handle_export_completed(self, evt: dict) -> None:
        st = str(evt.get("status", "")).strip().lower()
        mp3_path = str(evt.get("mp3Path", "") or "").strip()
        output_path = str(evt.get("outputPath", "") or "").strip()
        current_name = Path(mp3_path).name if mp3_path else "Unknown MP3"
        export_batches = self._export_batches_accessor()

        if st == "done":
            total_running = sum(len(b.jobs) for b in export_batches.values())
            total_completed = sum(b.completed_count for b in export_batches.values())
            total_count = sum(b.total_count for b in export_batches.values())
            self._set_export_status_fn(
                f"Exporting {total_completed}/{total_count} done · {total_running} running: {current_name}"
            )
            self._refresh_export_detail_fn()
            if output_path:
                self._current_export_stage = "Saved MP4"
                self._export_detail_label_set_fn(f"Saved: {output_path}")
        elif st == "merge_done":
            if output_path:
                self._set_last_export_path_fn(output_path)
                self._refresh_export_output_label_fn()
            if self._export_merge_progress_set_fn:
                self._export_merge_progress_set_fn(True, 1000, "Merging: 100%")
            if self._btn_export_merge_stop_set_fn:
                self._btn_export_merge_stop_set_fn(False)
            self._current_export_stage = "Merged MP4"
            self._set_export_status_fn(f"Merged MP4 created: {Path(output_path).name if output_path else 'OK'}")
            self._refresh_export_detail_fn()

    def handle_export_failed(self, evt: dict) -> None:
        st = str(evt.get("status", "")).strip().lower()
        mp3_path = str(evt.get("mp3Path", "") or "").strip()
        msg = str(evt.get("message", "")).strip()
        current_name = Path(mp3_path).name if mp3_path else "Unknown MP3"

        if st == "failed":
            self._current_export_stage = self._normalize_export_stage_message_fn(msg) or "Export failed"
            self._set_export_status_fn(f"Export failed for {current_name}")
            self._refresh_export_detail_fn()
        elif st == "merge_failed":
            self._current_export_stage = "Merge failed"
            self._set_export_status_fn(f"Merge failed: {msg or 'Unknown error'}")
            if self._export_merge_progress_set_fn:
                self._export_merge_progress_set_fn(False, 0, "")
            if self._btn_export_merge_stop_set_fn:
                self._btn_export_merge_stop_set_fn(False)
            self._refresh_export_detail_fn()

    def handle_export_status(self, evt: dict) -> None:
        st = str(evt.get("status", "")).strip().lower()
        msg = str(evt.get("message", "")).strip()
        prog = evt.get("progress", None)

        if st == "merge_started":
            if self._export_merge_progress_set_fn:
                self._export_merge_progress_set_fn(True, 0, "Merging: 0%")
            if self._btn_export_merge_stop_set_fn:
                self._btn_export_merge_stop_set_fn(True)
        elif st == "merge_warning":
            if msg:
                self._export_detail_label_set_fn(msg)
        elif st == "merge_cancelled":
            self._current_export_stage = "Merge stopping"
            self._set_export_status_fn(str(msg or "Stopping merge..."))
            if self._btn_export_merge_stop_set_fn:
                self._btn_export_merge_stop_set_fn(False)
        elif st == "merge_progress":
            if self._export_merge_progress_set_fn and isinstance(prog, (int, float)):
                ratio = max(0.0, min(1.0, float(prog)))
                self._export_merge_progress_set_fn(True, int(round(ratio * 1000.0)), f"Merging: {self._format_export_percent_fn(ratio)}")

    def on_export_done(self, payload: dict) -> None:
        if not isinstance(payload, dict):
            return
        mp3_path = str(payload.get("mp3Path", "") or "").strip()
        code = int(payload.get("code", 0) or 0)
        batch_key = str(payload.get("batchKey", "") or "").strip()
        export_batches = self._export_batches_accessor()

        batch = export_batches.get(batch_key) if batch_key else None
        if not batch:
            _, batch = self.find_batch_for_mp3(mp3_path)
        if not batch:
            return

        batch.jobs.pop(mp3_path, None)
        output_path = ""
        if mp3_path in batch.job_state:
            output_path = str(batch.job_state.get(mp3_path, {}).get("outputPath", "") or "").strip()

        if code != 0:
            batch.failed_count += 1
            failed_name = Path(mp3_path).name if mp3_path else "MP3"
            self._set_export_status_fn(f"Export failed: {failed_name} (code {code})")
        else:
            batch.completed_count += 1
            if output_path:
                batch.outputs_by_mp3[mp3_path] = output_path
                self._set_last_export_path_fn(output_path)
                self._refresh_export_output_label_fn()
            self._set_export_status_fn(
                f"Finished {batch.completed_count}/{batch.total_count}: {Path(output_path).name if output_path else Path(mp3_path).name}"
            )

        self._update_export_overall_progress_fn()
        if not batch.running:
            return
        if not batch.queue and not batch.jobs:
            batch.running = False
            export_batches.pop(batch_key, None)
            any_running = any(b.running for b in export_batches.values())
            if not any_running:
                summary = f"Batch complete: {batch.completed_count}/{batch.total_count} exported"
                if batch.failed_count:
                    summary += f" · {batch.failed_count} failed"
                self._set_export_status_fn(summary)
                self._export_detail_label_set_fn(f"Output folder: {batch.output_dir}")
                self._update_export_overall_progress_fn()
                if batch.completed_count == batch.total_count and batch.failed_count == 0 and batch.auto_merge_after:
                    self.start_auto_merge_export_for_outputs(list(batch.outputs_by_mp3.values()), batch.output_dir)
            return

        self.start_export_workers(batch)

    def start_auto_merge_export(self) -> None:
        from ..merge import MergeWorker

        merge_state = self._get_export_merge_state_fn()
        if merge_state.get("running", False):
            return
        auto_video = self._auto_video_coordinator_accessor() if self._auto_video_coordinator_accessor else None
        if auto_video is None:
            return
        settings = self._settings_accessor()
        plan = auto_video.resolve_auto_merge_plan(settings)
        if plan is None:
            return

        self._set_export_merge_state_fn({"cancel_requested": False, "proc": None, "running": True})
        self._set_export_status_fn("Merging exported MP4s in background...")
        self._export_detail_label_set_fn(f"Target: {plan.target_path}")
        self._bus.emit("export_event", {"status": "merge_started"})

        def run_merge():
            try:
                worker = MergeWorker(on_status=lambda msg: self._bus.emit("export_event", {"status": "merge_warning", "message": msg}))
                result = worker.merge_with_progress(
                    plan.ffmpeg_path,
                    plan.mp4_files,
                    plan.target_path,
                    on_progress=lambda ratio: self._bus.emit("export_event", {"status": "merge_progress", "progress": ratio}),
                    is_cancelled=lambda: bool(self._get_export_merge_state_fn().get("cancel_requested", False)),
                )
                if result.get("cancelled"):
                    self._bus.emit("export_event", {"status": "merge_cancelled", "message": "Merge cancelled"})
                    return
                if result.get("ok"):
                    self._bus.emit("export_event", {"status": "merge_done", "outputPath": result["output_path"]})
                else:
                    self._bus.emit("export_event", {"status": "merge_failed", "message": result.get("error", "Merge failed")})
            except Exception as exc:
                self._bus.emit("export_event", {"status": "merge_failed", "message": str(exc)})
            finally:
                self._set_export_merge_state_fn({"running": False})

        threading.Thread(target=run_merge, daemon=True).start()

    def start_auto_merge_export_for_outputs(self, mp4_paths: list[str], output_dir: str) -> None:
        from ..merge import MergeWorker

        merge_state = self._get_export_merge_state_fn()
        if merge_state.get("running", False):
            return
        if not mp4_paths:
            return

        ffmpeg_path = find_ffmpeg_from_path_hint(self._ffmpeg_path_accessor() or "")
        if not ffmpeg_path:
            return

        base_name = f"merged_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
        target_path = str(Path(output_dir) / base_name)

        self._set_export_merge_state_fn({"cancel_requested": False, "proc": None, "running": True})
        self._set_export_status_fn(f"Merging {len(mp4_paths)} MP4s...")
        self._export_detail_label_set_fn(f"Target: {target_path}")
        self._bus.emit("export_event", {"status": "merge_started"})

        def run_merge():
            try:
                worker = MergeWorker(on_status=lambda msg: self._bus.emit("export_event", {"status": "merge_warning", "message": msg}))
                result = worker.merge_with_progress(
                    ffmpeg_path,
                    mp4_paths,
                    target_path,
                    on_progress=lambda ratio: self._bus.emit("export_event", {"status": "merge_progress", "progress": ratio}),
                    is_cancelled=lambda: bool(self._get_export_merge_state_fn().get("cancel_requested", False)),
                )
                if result.get("cancelled"):
                    self._bus.emit("export_event", {"status": "merge_cancelled", "message": "Merge cancelled"})
                    return
                if result.get("ok"):
                    self._bus.emit("export_event", {"status": "merge_done", "outputPath": result["output_path"]})
                else:
                    self._bus.emit("export_event", {"status": "merge_failed", "message": result.get("error", "Merge failed")})
            except Exception as exc:
                self._bus.emit("export_event", {"status": "merge_failed", "message": str(exc)})
            finally:
                self._set_export_merge_state_fn({"running": False})

        threading.Thread(target=run_merge, daemon=True).start()


class ExportBatchCoordinator:
    """Owns ExportBatch creation, registry, and lifecycle events.

    Uses dependency injection: receives all paths and the UiBus via
    constructor parameters so the coordinator is instantiable and testable
    without a QApplication or MainWindow.
    """

    def __init__(
        self,
        ffmpeg_path: str,
        output_dir: str,
        bg_path: str,
        logo_path: str,
        bus: UiBus,
        db_cfg: DbCfg | None = None,
    ) -> None:
        self._ffmpeg_path = ffmpeg_path
        self._output_dir = output_dir
        self._bg_path = bg_path
        self._logo_path = logo_path
        self._bus = bus
        self._db_cfg: DbCfg | None = db_cfg
        self._export_batches: dict[str, ExportBatch] = {}

    def start_batch(self, mp3s: list[str], *, auto_merge_after: bool = False) -> str:
        """Create a new ExportBatch and register it.

        Raises ValueError (naming the offending parameter) if any required
        path is empty or whitespace-only before creating the batch.
        """
        if not self._ffmpeg_path or not self._ffmpeg_path.strip():
            raise ValueError("ffmpeg_path must not be empty")
        if not self._output_dir or not self._output_dir.strip():
            raise ValueError("output_dir must not be empty")
        if not self._bg_path or not self._bg_path.strip():
            raise ValueError("bg_path must not be empty")
        if not self._logo_path or not self._logo_path.strip():
            raise ValueError("logo_path must not be empty")

        batch_key = str(uuid.uuid4())
        batch = ExportBatch(
            batch_key=batch_key,
            output_dir=self._output_dir,
            ffmpeg_path=self._ffmpeg_path,
            bg_path=self._bg_path,
            logo_path=self._logo_path,
            queue=list(mp3s),
            mp3s=list(mp3s),
            total_count=len(mp3s),
            auto_merge_after=auto_merge_after,
        )
        self._export_batches[batch_key] = batch
        return batch_key

    def complete_batch(self, batch_key: str, *, ok: bool, error: str = "") -> None:
        """Emit bus.export_event signalling batch completion or failure."""
        payload: dict[str, object] = {
            "type": "export_done",
            "ok": ok,
            "batchKey": batch_key,
        }
        if not ok:
            payload["error"] = error
        self._bus.export_event.emit(payload)

    def get_batch(self, batch_key: str) -> ExportBatch | None:
        """Return the ExportBatch for the given key, or None if not found."""
        return self._export_batches.get(batch_key)

    def update_db_cfg(self, cfg: DbCfg | None) -> None:
        """Update the stored database configuration after a reconnection."""
        self._db_cfg = cfg
