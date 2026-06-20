"""ProgressCoordinator — owns progress-page orchestration.

Uses dependency injection via a protocol interface to avoid direct
MainWindow type coupling while preserving existing behavior.
"""
from __future__ import annotations

import os
import threading
import time
import webbrowser
from pathlib import Path
from typing import Any, Callable, Protocol

from ..ports import (
    ConfirmQuestionFn,
    ClipboardFn,
    ContextMenuFn,
    DirDialogFn,
    InformationFn,
    LoggerPort,
    ProcessEventsFn,
    ProgressDialogHandle,
    ShowProgressDialogFn,
    TablePopulateFn,
    TimerFactory,
    WarningFn,
)
from ..merge import MergeWorker
from ...services.video_export import find_ffmpeg_from_path_hint
from ...views.helpers.widget_factory import calendar_picker_value as _calendar_picker_value


class ProgressHostPort(Protocol):
    """Protocol interface capturing what ProgressCoordinator needs from its host.

    This replaces the direct MainWindow reference with a narrow interface,
    enabling instantiation with mock objects for testing.
    """

    db_cfg: Any
    music_data: dict
    bus: Any
    progress_table: Any
    youtube_coordinator: Any

    def _music_settings(self) -> dict: ...
    def _log(self, msg: str) -> None: ...
    def _set_global_status(self, msg: str, *, source: str = "") -> None: ...
    def _set_music_status(self, msg: str) -> None: ...
    def _music_profile_by_id(self, profile_id: str) -> dict | None: ...
    def _get_saved_video_template(self, tpl_id: str) -> Any: ...
    def _resolved_output_resolution(self, *, profile: dict | None = None) -> tuple[int, int]: ...
    def _try_start_auto_video_channel(self, batch_id: str, profile_id: str, role: str, out_dir: str, *, done: set) -> bool: ...
    def _cancel_unfinished_background_jobs(self, *, reason: str, stop_youtube_runtime: bool) -> dict: ...
    def _safe_batch_suffix(self, s: str) -> str: ...
    def _enqueue_youtube_upload_for_merge(self, *, batch_id: str, profile_id: str, role: str, merged_mp4_path: str) -> None: ...
    def _youtube_upload_tick(self, *, force: bool = False) -> None: ...
    def _youtube_is_mp4_ready_for_upload(self, path: str, *, deep: bool = False) -> tuple[bool, str]: ...
    def _image_coordinator(self) -> Any: ...


class ProgressCoordinator:
    """Owns incremental progress-page orchestration extracted from MainWindow.

    Current slices move refresh/model logic, context-menu dispatch, row-scoped
    progress actions, converter/merge restart routing, and safe YouTube row
    actions behind a stable coordinator boundary while keeping deeper auto-video,
    merge-worker, and YouTube runtime helpers on the host seam.

    Dependencies are injected via the host protocol interface.
    """

    def __init__(
        self,
        *,
        host: ProgressHostPort,
        settings_accessor: Callable[[], dict] | None = None,
        db_cfg_accessor: Callable[[], Any] | None = None,
        logger: LoggerPort | None = None,
        confirm_question_fn: ConfirmQuestionFn | None = None,
        warning_fn: WarningFn | None = None,
        information_fn: InformationFn | None = None,
        table_populate_fn: TablePopulateFn | None = None,
        process_events_fn: ProcessEventsFn | None = None,
        dir_dialog_fn: DirDialogFn | None = None,
        clipboard_fn: ClipboardFn | None = None,
        context_menu_fn: ContextMenuFn | None = None,
        show_progress_dialog_fn: ShowProgressDialogFn | None = None,
        timer_factory: TimerFactory | None = None,
    ) -> None:
        if host is None:
            raise ValueError("ProgressCoordinator requires a non-None host")
        self.host = host
        self._settings_accessor = settings_accessor
        self._db_cfg_accessor = db_cfg_accessor
        self._logger = logger
        self._confirm_question_fn = confirm_question_fn
        self._warning_fn = warning_fn
        self._information_fn = information_fn
        self._table_populate_fn = table_populate_fn
        self._process_events_fn = process_events_fn
        self._dir_dialog_fn = dir_dialog_fn
        self._clipboard_fn = clipboard_fn
        self._context_menu_fn = context_menu_fn
        self._show_progress_dialog_fn = show_progress_dialog_fn
        self._timer_factory = timer_factory

    # -- No-op fallback helpers --

    def _confirm(self, title: str, message: str) -> bool:
        """Ask user a yes/no question. Returns False if no callable set."""
        if self._confirm_question_fn is None:
            return False
        return self._confirm_question_fn(title, message)

    def _warn(self, title: str, message: str) -> None:
        """Show a warning dialog. No-op if no callable set."""
        if self._warning_fn is not None:
            self._warning_fn(title, message)

    def _info(self, title: str, message: str) -> None:
        """Show an informational dialog. No-op if no callable set."""
        if self._information_fn is not None:
            self._information_fn(title, message)

    def _process_events(self) -> None:
        """Process pending UI events. No-op if no callable set."""
        if self._process_events_fn is not None:
            self._process_events_fn()

    def refresh_table(self) -> None:
        host = self.host
        if not hasattr(host, "progress_table"):
            return
        self.refresh_table_async(force=True)

    def refresh_table_async(self, *, force: bool = False) -> None:
        host = self.host
        if not hasattr(host, "progress_table"):
            return
        if bool(getattr(host, "_app_closing", False)):
            return
        inflight = bool(getattr(host, "_progress_refresh_inflight", False))
        if inflight and not bool(force):
            started_at = float(getattr(host, "_progress_refresh_started_at", 0.0) or 0.0)
            if started_at > 0.0 and (time.time() - started_at) > 12.0:
                host._progress_refresh_inflight = False
                inflight = False
                if hasattr(host, "progress_status_label"):
                    host.progress_status_label.setText("Previous refresh was slow. Retrying…")
            else:
                return
        if not host.db_cfg:
            host.progress_table.setRowCount(0)
            if hasattr(host, "progress_summary_label"):
                host.progress_summary_label.setText("Database is not configured")
            if hasattr(host, "progress_status_label"):
                msg = "Configure Postgres in Settings → Database"
                host.progress_status_label.setText(msg)
                host._set_global_status(msg, source="Progress")
            return

        from_ymd = _calendar_picker_value(getattr(host, "progress_from_date", None))
        to_ymd = _calendar_picker_value(getattr(host, "progress_to_date", None))

        limit = 25
        try:
            if hasattr(host, "progress_limit_combo"):
                limit = int(str(host.progress_limit_combo.currentText() or "25").strip() or "25")
        except Exception:
            limit = 25
        limit = max(1, min(200, limit))
        active_only = bool(getattr(host, "progress_active_only", None).isChecked()) if hasattr(host, "progress_active_only") else False

        token = int(getattr(host, "_progress_refresh_token", 0) or 0) + 1
        host._progress_refresh_token = token
        host._progress_refresh_inflight = True
        host._progress_refresh_started_at = time.time()

        if hasattr(host, "progress_status_label"):
            host.progress_status_label.setText("Refreshing…")

        started = time.time()

        def work():
            def safe_ui_invoke(fn):
                try:
                    if bool(getattr(host, "_app_closing", False)):
                        return
                    bus = getattr(host, "bus", None)
                    if bus is None:
                        return
                    bus.ui_invoke.emit(fn)
                except Exception:
                    return

            try:
                t0 = time.time()
                try:
                    rows = self.collect_rows(limit=limit, active_only=active_only, from_ymd=from_ymd, to_ymd=to_ymd)
                except RuntimeError as exc:
                    if "has been deleted" in str(exc).lower() or bool(getattr(host, "_app_closing", False)):
                        return
                    raise
                t1 = time.time()
                elapsed = time.time() - started

                def apply():
                    try:
                        if bool(getattr(host, "_app_closing", False)):
                            return
                        if int(getattr(host, "_progress_refresh_token", 0) or 0) != token:
                            return
                        self.apply_rows(rows)
                        if hasattr(host, "progress_status_label"):
                            msg = f"Refreshed at {time.strftime('%H:%M:%S')} · total {elapsed:.2f}s · compute {(t1 - t0):.2f}s"
                            host.progress_status_label.setText(msg)
                        if hasattr(host, "progress_summary_label"):
                            host.progress_summary_label.setText(f"Pipeline: {host._footer._music_status_message} · Images: {host._image_status_message}")
                        host._progress_refresh_inflight = False
                        host._progress_refresh_started_at = 0.0
                    except Exception:
                        return

                safe_ui_invoke(apply)
            except Exception as exc:
                def apply_err():
                    try:
                        if bool(getattr(host, "_app_closing", False)):
                            return
                        if hasattr(host, "progress_status_label"):
                            msg = f"Progress refresh failed: {exc}"
                            host.progress_status_label.setText(msg)
                            host._set_global_status(msg, source="Progress")
                        host._progress_refresh_inflight = False
                        host._progress_refresh_started_at = 0.0
                    except Exception:
                        return

                safe_ui_invoke(apply_err)

        threading.Thread(target=work, daemon=True).start()

    def apply_rows(self, rows: list[dict]) -> None:
        """Populate progress table with row data.

        Delegates to table_populate_fn if provided; otherwise operates directly
        on host.progress_table (backwards-compatible path for un-wired hosts).
        """
        host = self.host
        table = host.progress_table

        if self._table_populate_fn is not None:
            # Build structured data for the populate callback
            columns = ["batch", "runDate", "channel", "status", "music", "image", "converter", "merge", "youtube", "stage", "notes", "updated"]
            center_cols = {"status", "music", "converter", "youtube", "stage"}
            structured_rows: list[list[tuple[int, str, str]]] = []
            for row in rows:
                cells: list[tuple[int, str, str]] = []
                for c, key in enumerate(columns):
                    text = str(row.get(key, "")).strip()
                    # Encode meta as string in the first column's data role
                    if c == 0:
                        import json
                        data = json.dumps(row.get("_meta") or {})
                    else:
                        data = ""
                    cells.append((c, text, data))
                structured_rows.append(cells)
            table.setUpdatesEnabled(False)
            try:
                self._table_populate_fn(structured_rows)
            finally:
                table.setUpdatesEnabled(True)
            return

        # Fallback: direct table manipulation (host must provide table widget)
        table.setUpdatesEnabled(False)
        try:
            table.setRowCount(len(rows))
            for r, row in enumerate(rows):
                for c, key in enumerate(["batch", "runDate", "channel", "status", "music", "image", "converter", "merge", "youtube", "stage", "notes", "updated"]):
                    text = str(row.get(key, "")).strip()
                    table.setItem(r, c, text)
                    if c == 0:
                        table.setItemData(r, c, dict(row.get("_meta") or {}))
                    if key in {"status", "music", "converter", "youtube", "stage"}:
                        table.setItemAlignment(r, c, "center")
                    # Tooltip
                    if key == "notes":
                        tip = str(row.get("notesFull", "")).strip()
                    else:
                        tip = text
                    if tip and tip != text:
                        table.setItemToolTip(r, c, tip)
                    elif tip and len(tip) > 80:
                        table.setItemToolTip(r, c, tip)
        finally:
            table.setUpdatesEnabled(True)

