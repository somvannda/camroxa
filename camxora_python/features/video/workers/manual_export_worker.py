"""Background worker for manual GPU video export."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QThread, Signal

from features.video.export_gate import export_gate
from features.video.lib.render_scene_request import (
    ManualRenderSceneRequest,
    build_manual_export_output_path,
    resolve_manual_export_output_dir,
)
from features.video.services.export_coordinator import CoordinatorExportRequest, ExportCoordinator
from features.video.services.export_job import ExportSettings, find_ffmpeg_from_path_hint
from shared.lib.export_codec import format_export_status_message


@dataclass(frozen=True)
class ManualExportRequest:
    scene: ManualRenderSceneRequest
    settings: dict
    speed_mode: str = "fast"
    # Batch exports share one user-picked output folder (python_app behavior).
    output_dir: str = ""
    preview: Any | None = None


class VideoManualExportWorker(QThread):
    progressed = Signal(object)
    succeeded = Signal(str)
    failed = Signal(str)

    def __init__(self, request: ManualExportRequest, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("VideoManualExportWorker")
        self._request = request
        self._coordinator: ExportCoordinator | None = None
        self._started_at = 0.0
        self._cancel_requested = False

    def cancel(self) -> None:
        self._cancel_requested = True
        coordinator = self._coordinator
        if coordinator is None:
            return
        job_id = coordinator.running_job_id
        if job_id:
            coordinator.cancel_export(job_id)

    def run(self) -> None:
        if getattr(self, "_cancel_requested", False):
            self.failed.emit("Export cancelled.")
            return
        scene = self._request.scene
        settings = self._request.settings
        audio_path = str(scene.assets.audio_path or "").strip()
        background_path = str(scene.assets.background_path or "").strip()
        logo_path = str(scene.assets.logo_path or "").strip()
        if not audio_path:
            self.failed.emit("Select an MP3 track before exporting.")
            return
        if not background_path:
            self.failed.emit("Select a background image before exporting.")
            return

        output_dir = str(self._request.output_dir or "").strip() or resolve_manual_export_output_dir(
            settings=settings, audio_path=audio_path
        )
        output_path = build_manual_export_output_path(audio_path=audio_path, output_dir=output_dir)
        ffmpeg_path = find_ffmpeg_from_path_hint(str(settings.get("ffmpegPath") or "ffmpeg"))
        workers_raw = settings.get("videoExportWorkers", settings.get("perfExportWorkers", 1))
        from visualizer_video.export_gpu_tier import resolve_pipeline_export_workers

        worker_limit = resolve_pipeline_export_workers(workers_raw, default=1)
        export_gate.set_limit(worker_limit)

        last_fail_message = ""
        try:
            if self._cancel_requested:
                self.failed.emit("Export cancelled.")
                return
            self._started_at = time.time()
            export_settings = ExportSettings(
                ffmpeg_path=ffmpeg_path,
                output_dir=output_dir,
                output_path=output_path,
                fps=int(scene.output.fps),
                width=int(scene.output.width),
                height=int(scene.output.height),
                speed_mode=self._request.speed_mode,
            )

            def _on_event(event: dict) -> None:
                nonlocal last_fail_message
                if str(event.get("status") or "").lower() == "failed":
                    msg = str(event.get("message") or "").strip()
                    if msg:
                        last_fail_message = msg
                self._handle_event(event)

            coordinator = ExportCoordinator()
            self._coordinator = coordinator
            if self._cancel_requested:
                self.failed.emit("Export cancelled.")
                return
            coordinator.on_progress(_on_event)
            coordinator.start_export(
                CoordinatorExportRequest(
                    mp3_path=audio_path,
                    template=scene.template,
                    background_path=background_path,
                    logo_path=logo_path,
                    settings=export_settings,
                    scene=scene,
                    preview=self._request.preview,
                    speed_mode=self._request.speed_mode,
                )
            )
            code = coordinator.last_exit_code
            if self._cancel_requested or code != 0:
                from shared.services.app_logger import log_error

                detail = last_fail_message.strip() or (
                    "Export cancelled." if self._cancel_requested else f"Export failed with exit code {code}."
                )
                if not self._cancel_requested:
                    log_error(detail, category="export")
                self.failed.emit(self._short_fail_message(detail))
                return
            self.succeeded.emit(output_path)
        except Exception as exc:
            self.failed.emit(str(exc) or "Unable to export video.")
        finally:
            self._coordinator = None

    @staticmethod
    def _short_fail_message(detail: str) -> str:
        if "\n" in detail:
            lines = [ln.strip() for ln in detail.splitlines() if ln.strip()]
            summary = lines[-1] if lines else detail
            if len(summary) > 180:
                summary = summary[:177] + "…"
            return summary
        return detail

    def _handle_event(self, event: dict) -> None:
        progress = event.get("progress")
        percent = None
        if isinstance(progress, (int, float)):
            percent = max(0, min(100, int(round(float(progress) * 100))))
        elapsed = max(0.0, time.time() - self._started_at) if self._started_at else 0.0
        message = format_export_status_message(
            str(event.get("message") or ""),
            video_codec=event.get("videoCodec"),
        )
        payload: dict[str, object] = {
            "status": str(event.get("status") or ""),
            "message": message,
            "progressPercent": percent,
            "elapsedSec": elapsed,
            "outputPath": str(event.get("outputPath") or ""),
        }
        codec = str(event.get("videoCodec") or "").strip()
        if codec:
            payload["videoCodec"] = codec
        backend_used = str(event.get("backendUsed") or event.get("backend") or "").strip()
        if backend_used:
            payload["backendUsed"] = backend_used
            payload["backend"] = backend_used
        fallback_from = str(event.get("fallbackFrom") or "").strip()
        if fallback_from:
            payload["fallbackFrom"] = fallback_from
        self.progressed.emit(payload)
