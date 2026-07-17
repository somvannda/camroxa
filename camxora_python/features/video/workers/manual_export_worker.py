"""Background worker for manual GPU video export."""

from __future__ import annotations

import time
from dataclasses import dataclass

from PySide6.QtCore import QThread, Signal

from features.video.export_gate import export_gate
from features.video.lib.render_scene_request import (
    ManualRenderSceneRequest,
    build_manual_export_output_path,
    resolve_manual_export_output_dir,
)
from features.video.services.export_job import ExportJob, ExportSettings, find_ffmpeg_from_path_hint


@dataclass(frozen=True)
class ManualExportRequest:
    scene: ManualRenderSceneRequest
    settings: dict
    speed_mode: str = "balanced"
    # Batch exports share one user-picked output folder (python_app behavior).
    output_dir: str = ""


class VideoManualExportWorker(QThread):
    progressed = Signal(object)
    succeeded = Signal(str)
    failed = Signal(str)

    def __init__(self, request: ManualExportRequest, parent=None) -> None:
        super().__init__(parent)
        self._request = request
        self._job: ExportJob | None = None
        self._started_at = 0.0

    def cancel(self) -> None:
        if self._job is not None:
            self._job.cancel()

    def run(self) -> None:
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
        try:
            worker_limit = max(1, min(10, int(workers_raw)))
        except (TypeError, ValueError):
            worker_limit = 1
        export_gate.set_limit(worker_limit)

        export_gate.acquire()
        last_fail_message = ""
        try:
            export_gate.throttle_spawn()
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

            self._job = ExportJob(
                mp3_path=audio_path,
                template=scene.template,
                background_path=background_path,
                logo_path=logo_path,
                settings=export_settings,
                on_event=_on_event,
            )
            code = self._job.run_blocking()
            if code != 0:
                detail = last_fail_message.strip() or f"Export failed with exit code {code}."
                # Prefer the last traceback line when available.
                if "\n" in detail:
                    lines = [ln.strip() for ln in detail.splitlines() if ln.strip()]
                    # Keep a short readable summary for the status bar.
                    summary = lines[-1] if lines else detail
                    if len(summary) > 180:
                        summary = summary[:177] + "…"
                    self.failed.emit(summary)
                else:
                    self.failed.emit(detail)
                return
            self.succeeded.emit(output_path)
        except Exception as exc:
            self.failed.emit(str(exc) or "Unable to export video.")
        finally:
            export_gate.release()

    def _handle_event(self, event: dict) -> None:
        progress = event.get("progress")
        percent = None
        if isinstance(progress, (int, float)):
            percent = max(0, min(100, int(round(float(progress) * 100))))
        elapsed = max(0.0, time.time() - self._started_at) if self._started_at else 0.0
        self.progressed.emit(
            {
                "status": str(event.get("status") or ""),
                "message": str(event.get("message") or ""),
                "progressPercent": percent,
                "elapsedSec": elapsed,
                "outputPath": str(event.get("outputPath") or ""),
            }
        )
