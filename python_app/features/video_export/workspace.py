"""Video workspace state: resolution, FFmpeg, export batch, and template helpers."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable, Protocol

from ..ports import DirDialogFn, FileDialogFn, ListItemsFn, LoggerPort


class WorkspaceHostPort(Protocol):
    """Protocol interface for VideoWorkspaceStateCoordinator host dependencies."""

    db_cfg: Any
    e_settings: dict

    def _music_settings(self) -> dict: ...
    def _persist_setting_patch(self, patch: dict) -> None: ...
    def _refresh_footer(self) -> None: ...


class VideoWorkspaceStateCoordinator:
    """Owns video workspace state extracted from MainWindow.

    Covers:
    - Output resolution parsing & resolution cascade
    - Video template persistence helpers (save / get)
    - FFmpeg path resolution
    - Export batch state initialisation
    - Export utility methods (progress, stage formatting, output labels)

    Dependencies are injected via the host protocol interface.
    """

    def __init__(
        self,
        *,
        host: WorkspaceHostPort,
        settings_accessor: Callable[[], dict] | None = None,
        db_cfg_accessor: Callable[[], Any] | None = None,
        logger: LoggerPort | None = None,
        file_dialog_fn: FileDialogFn | None = None,
        dir_dialog_fn: DirDialogFn | None = None,
        list_items_fn: ListItemsFn | None = None,
    ) -> None:
        if host is None:
            raise ValueError("VideoWorkspaceStateCoordinator requires a non-None host")
        self.host = host
        self._settings_accessor = settings_accessor
        self._db_cfg_accessor = db_cfg_accessor
        self._logger = logger
        self._file_dialog_fn: FileDialogFn = file_dialog_fn or (lambda title, filter: "")
        self._dir_dialog_fn: DirDialogFn = dir_dialog_fn or (lambda title, default: "")
        self._list_items_fn: ListItemsFn = list_items_fn or (lambda: [])

    # ------------------------------------------------------------------
    # Resolution helpers
    # ------------------------------------------------------------------

    def parse_output_resolution(
        self, text: str, *, fallback: tuple[int, int] = (1920, 1080)
    ) -> tuple[int, int]:
        """Parse a 'WxH' resolution string, clamped to [240, 7680]."""

        s = str(text or "").strip().lower()
        m = re.match(r"^(\d{2,5})x(\d{2,5})$", s)
        if not m:
            return (int(fallback[0]), int(fallback[1]))
        try:
            w = int(m.group(1))
            h = int(m.group(2))
        except Exception:
            return (int(fallback[0]), int(fallback[1]))
        w = max(240, min(7680, w))
        h = max(240, min(7680, h))
        return (w, h)

    def resolved_output_resolution(self, *, profile: dict | None = None) -> tuple[int, int]:
        """Resolve output resolution from profile → global settings → default cascade."""

        host = self.host
        settings = host._music_settings() if hasattr(host, "_music_settings") else (host.e_settings or {})
        p = profile if isinstance(profile, dict) else {}
        res_text = (
            str(p.get("outputResolution", "")).strip()
            or str(settings.get("outputResolution", "")).strip()
            or str(settings.get("imageResolution", "1920x1080")).strip()
            or "1920x1080"
        )
        return self.parse_output_resolution(res_text)

    # ------------------------------------------------------------------
    # FFmpeg helpers
    # ------------------------------------------------------------------

    def pick_ffmpeg(self) -> None:
        """Open a file dialog for FFmpeg and persist the chosen path."""

        host = self.host
        f = self._file_dialog_fn("Select FFmpeg", "FFmpeg (ffmpeg.exe)")
        if f:
            host._ffmpeg_path = f
            host._persist_setting_patch({"ffmpegPath": f})

    def resolve_ffmpeg_for_export(self) -> str | None:
        """Return an FFmpeg path, triggering pick dialog if none configured."""

        host = self.host
        ffmpeg_path = self.find_ffmpeg_from_path_hint(getattr(host, "_ffmpeg_path", ""))
        if not ffmpeg_path:
            self.pick_ffmpeg()
            ffmpeg_path = self.find_ffmpeg_from_path_hint(getattr(host, "_ffmpeg_path", ""))
        return ffmpeg_path or None

    @staticmethod
    def find_ffmpeg_from_path_hint(hint: str) -> str | None:
        """Resolve FFmpeg from a saved hint or system PATH."""

        from ...services.video_export import find_ffmpeg_from_path_hint as _find

        return _find(hint)

    # ------------------------------------------------------------------
    # Export batch state
    # ------------------------------------------------------------------

    def worker_limit(self) -> int:
        """Return configured export worker count, clamped to [1, 10]."""

        host = self.host
        settings = host.e_settings or {}
        try:
            workers = int(settings.get("videoExportWorkers", 1) or 1)
        except Exception:
            workers = 1
        return max(1, min(10, workers))

    def iter_mp3_paths(self) -> list[str]:
        """Collect all MP3 paths from the export list widget."""

        items = self._list_items_fn()
        return [data for _text, data in items if data.strip()]

    def current_selected_mp3_path(self) -> str:
        """Return the MP3 path of the currently selected list item."""

        items = self._list_items_fn()
        if not items:
            return ""
        # Return the data (path) of the first item as the "current" selection
        # The adapter is expected to return only the selected/current item when appropriate
        return items[0][1].strip() if items else ""

    def prompt_output_dir_for_export(self) -> str:
        """Prompt user for an export output directory and persist it."""

        host = self.host
        d = self._dir_dialog_fn("Select Output Folder", self._get_export_browse_default_dir())
        d = str(d or "").strip()
        if not d:
            return ""
        host._output_dir = d
        host._last_export_path = ""
        self.refresh_export_output_label()
        host._persist_setting_patch({"videoRenderOutputDir": d})
        return d

    def _get_export_browse_default_dir(self) -> str:
        """Determine a sensible default directory for the export folder dialog."""

        host = self.host
        cur_mp3 = self.current_selected_mp3_path()
        if cur_mp3:
            try:
                p = Path(cur_mp3)
                if p.exists():
                    return str(p.parent)
            except Exception:
                pass
        mp3_dir = str((host.e_settings or {}).get("videoRenderMp3Dir", "")).strip()
        if mp3_dir and Path(mp3_dir).exists():
            return mp3_dir
        current_out = str(getattr(host, "_output_dir", "") or "").strip()
        if current_out and Path(current_out).exists():
            return current_out
        return str(Path.cwd())

    def export_auto_merge_enabled(self) -> bool:
        """Return whether auto-merge after export is enabled."""

        host = self.host
        settings = host.e_settings or {}
        return bool(settings.get("videoAutoMergeMp4", False))

    # ------------------------------------------------------------------
    # Export progress & status formatting
    # ------------------------------------------------------------------

    def format_export_percent(self, ratio: float) -> str:
        """Format a 0..1 progress ratio as a human-readable percentage."""

        clamped = max(0.0, min(1.0, float(ratio)))
        pct = clamped * 100.0
        if clamped > 0.0 and pct < 0.1:
            return "<0.1%"
        if pct < 10.0:
            return f"{pct:.1f}%"
        return f"{pct:.0f}%"

    def set_export_progress(self, ratio: float) -> None:
        """Update the export progress bar widget."""

        host = self.host
        host._current_export_progress_ratio = max(0.0, min(1.0, float(ratio)))
        host.export_progress.setValue(int(round(host._current_export_progress_ratio * 1000.0)))
        host.export_progress.setFormat(f"Overall: {self.format_export_percent(host._current_export_progress_ratio)}")

    def normalize_export_stage_message(self, msg: str) -> str:
        """Normalize raw stage messages, hiding noisy frame-0 / debug lines."""

        text = str(msg or "").strip()
        if not text:
            return ""
        if text.startswith("[DEBUG]"):
            return ""
        normalized = text.lower()
        if normalized in {
            "rendering frame 0...",
            "writing frame 0 to pipe...",
            "frame 0 written successfully!",
            "entering render loop...",
        }:
            return "Preparing first frame..."
        if normalized == "initializing gpu renderer...":
            return "Initializing GPU renderer..."
        if normalized == "starting encoder...":
            return "Starting encoder..."
        if normalized == "encoder started, setting up shaders...":
            return "Preparing shaders..."
        if normalized == "finalizing mp4...":
            return "Finalizing MP4..."
        return text

    def refresh_export_detail(self) -> None:
        """Update the export detail label with current stage / progress info."""

        host = self.host
        if not hasattr(host, "export_detail_label"):
            return
        batches = list(getattr(host, "_export_batches", {}).values())
        total_count = sum(int(getattr(batch, "total_count", 0) or 0) for batch in batches)
        completed_count = sum(int(getattr(batch, "completed_count", 0) or 0) for batch in batches)
        failed_count = sum(int(getattr(batch, "failed_count", 0) or 0) for batch in batches)
        running_count = sum(len(getattr(batch, "jobs", {}) or {}) for batch in batches if getattr(batch, "running", False))

        stage = host._current_export_stage or "Preparing export..."
        parts = [
            f"Stage: {stage}",
            f"Overall: {self.format_export_percent(host._current_export_progress_ratio)}",
        ]
        if host._current_export_total_frames > 0 and host._current_export_frame > 0:
            parts.append(f"Frames: {host._current_export_frame}/{host._current_export_total_frames}")
        parts.append(f"Exported: {completed_count}/{total_count}")
        if failed_count:
            parts.append(f"Failed: {failed_count}")
        if running_count:
            parts.append(f"Running: {running_count}/{host._export_workers}")
        host.export_detail_label.setText(" | ".join(parts))

    def update_export_overall_progress(self) -> None:
        """Recalculate and apply overall batch export progress."""

        host = self.host
        batches = list(getattr(host, "_export_batches", {}).values())
        total_count = sum(int(getattr(batch, "total_count", 0) or 0) for batch in batches)
        if total_count <= 0:
            self.set_export_progress(0.0)
            return

        completed_count = sum(int(getattr(batch, "completed_count", 0) or 0) for batch in batches)
        active_progress = 0.0
        for batch in batches:
            for state in (getattr(batch, "job_state", {}) or {}).values():
                try:
                    active_progress += float(state.get("progress", 0.0) or 0.0)
                except Exception:
                    continue
        ratio = float(completed_count + active_progress) / float(max(1, total_count))
        self.set_export_progress(ratio)

    def refresh_export_output_label(self) -> None:
        """Update the export output folder / last MP4 label."""

        host = self.host
        folder = str(getattr(host, "_output_dir", "") or "").strip()
        last_mp4 = str(getattr(host, "_last_export_path", "") or "").strip()
        if last_mp4:
            host.export_output_label.setText(f"Last MP4: {last_mp4}")
            host._refresh_footer()
            return
        if folder:
            host.export_output_label.setText(f"Output Folder: {folder}")
            host._refresh_footer()
            return
        host.export_output_label.setText("Output Folder: Not selected")
        host._refresh_footer()

    # ------------------------------------------------------------------
    # Video template persistence helpers
    # ------------------------------------------------------------------

    def get_saved_video_template(self, tpl_id: str):
        """Fetch a saved video template from DB or local cache."""

        from ...database.persistence import db_get_video_template, read_local_templates

        key = str(tpl_id or "").strip()
        if not key:
            return None
        host = self.host
        if host.db_cfg:
            try:
                row = db_get_video_template(host.db_cfg, key)
                if row is not None:
                    return row
            except Exception:
                pass
        for row in read_local_templates():
            if str(row.id) == key:
                return row
        return None
