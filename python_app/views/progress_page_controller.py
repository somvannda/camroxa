"""ProgressPageController — owns progress-page orchestration.

Extracted from ``MainWindow`` as part of the *main-window-decomposition* spec
(Requirement 6). The controller owns the progress-table refresh pipeline (with a
cancellation-token pattern), row context-menu dispatch, row-scoped progress
actions, converter/merge restart routing, and merge-only queue orchestration.

The controller does **not** hold a reference to ``MainWindow``. Instead it
receives a small, typed set of dependencies:

* ``db_cfg_accessor`` — returns the active :class:`DbCfg` or ``None`` when the
  database is not configured. Every database operation is guarded by this
  accessor so the controller degrades gracefully (Requirement 12.4).
* ``bus`` — the :class:`UiBus` used to marshal background results back onto the
  UI thread via ``bus.ui_invoke`` and to emit ``music_event`` notifications.
* ``settings_accessor`` — returns the current music-settings dict.
* ``merge_worker`` — the shared :class:`MergeWorker` used for merge-only jobs.
* ``widget_accessors`` — a ``dict[str, Callable[[], object]]`` registry that
  resolves widgets (e.g. ``"progress_table"``) and host-provided collaborators
  / callbacks (e.g. ``"youtube_coordinator"``, ``"log"``). The
  :meth:`_widget` helper returns ``None`` when a key is missing, keeping the
  controller constructable — and unit-testable — without a ``QApplication``.

Recognised ``widget_accessors`` keys (all optional):

    Widgets:        ``window``, ``progress_table``, ``progress_status_label``,
                    ``progress_summary_label``, ``progress_from_date``,
                    ``progress_to_date``, ``progress_limit_combo``,
                    ``progress_active_only``
    Collaborators:  ``music_data``, ``youtube_coordinator``,
                    ``image_coordinator``, ``footer``
    Shared state:   ``app_closing``, ``ffmpeg_path``, ``image_status_message``,
                    ``auto_video_batches``, ``auto_video_done``,
                    ``auto_video_merging_dirs``, ``auto_video_active_channels``,
                    ``auto_video_running``, ``export_batches``,
                    ``export_merge_running``, ``youtube_progress_by_job_uid``
    Host callbacks: ``log``, ``set_global_status``, ``set_music_status``,
                    ``music_profile_by_id``, ``get_saved_video_template``,
                    ``try_start_auto_video_channel``,
                    ``cancel_unfinished_background_jobs``, ``safe_batch_suffix``,
                    ``enqueue_youtube_upload_for_merge``, ``youtube_upload_tick``,
                    ``youtube_is_mp4_ready_for_upload``, ``refresh_history_rows``

The cancellation token (``self._refresh_token``) is incremented at the start of
each refresh; background results capture the token at spawn time and discard
themselves when a newer refresh has superseded them (Requirement 6.3).
"""

from __future__ import annotations

import os
import threading
import time
import webbrowser
from collections.abc import Callable
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QMenu,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
)

from ..app.ui_bus import UiBus
from ..database.persistence import DbCfg
from ..services.video_export import find_ffmpeg_from_path_hint
from .helpers.widget_factory import calendar_picker_value as _calendar_picker_value
from ..features.merge import MergeWorker


class ProgressPageController:
    """Owns progress-page refresh, row actions, and merge orchestration."""

    def __init__(
        self,
        *,
        db_cfg_accessor: Callable[[], DbCfg | None],
        bus: UiBus,
        settings_accessor: Callable[[], dict],
        merge_worker: MergeWorker,
        widget_accessors: dict[str, Callable[[], object]],
    ) -> None:
        self._db_cfg_accessor = db_cfg_accessor
        self._bus = bus
        self._settings_accessor = settings_accessor
        self._merge_worker = merge_worker
        self._widget_accessors: dict[str, Callable[[], object]] = dict(widget_accessors or {})

        # Cancellation token — incremented on each refresh; stale background
        # results compare their captured token and discard themselves.
        self._refresh_token: int = 0
        self._refresh_inflight: bool = False
        self._refresh_started_at: float = 0.0

        # Controller-owned caches and merge-only queue state.
        self._dir_cache: dict[str, dict] = {}
        self._merge_only_queue: list[dict] = []
        self._merge_only_running: int = 0
        self._cancel_all_inflight: bool = False
        self._cancel_all_dialog: Any = None
        self._hide_worker: Any = None

    # ------------------------------------------------------------------
    # Dependency accessors (safe — return None / defaults when missing)
    # ------------------------------------------------------------------
    def _db_cfg(self) -> DbCfg | None:
        try:
            return self._db_cfg_accessor()
        except Exception:
            return None

    def _settings(self) -> dict:
        try:
            return self._settings_accessor() or {}
        except Exception:
            return {}

    def _widget(self, name: str) -> Any:
        """Resolve a widget / collaborator by name, or ``None`` when missing."""
        fn = self._widget_accessors.get(name)
        if fn is None:
            return None
        try:
            return fn()
        except Exception:
            return None

    def _call(self, name: str, *args: Any, **kwargs: Any) -> Any:
        """Invoke a host-provided callback by name; no-op when not registered."""
        fn = self._widget(name)
        if not callable(fn):
            return None
        try:
            return fn(*args, **kwargs)
        except Exception:
            return None

    def _window(self) -> Any:
        return self._widget("window")

    def _is_app_closing(self) -> bool:
        return bool(self._widget("app_closing"))

    def _log(self, msg: str) -> None:
        self._call("log", msg)

    def _set_global_status(self, msg: str, *, source: str = "") -> None:
        self._call("set_global_status", msg, source=source)

    def _set_music_status(self, msg: str) -> None:
        self._call("set_music_status", msg)

    def _ui_invoke(self, fn: Callable[[], None]) -> None:
        """Marshal *fn* onto the UI thread, honouring the app-closing flag."""
        try:
            if self._is_app_closing():
                return
            bus = self._bus
            if bus is None:
                return
            bus.ui_invoke.emit(fn)
        except Exception:
            return

    # ------------------------------------------------------------------
    # Refresh pipeline
    # ------------------------------------------------------------------
    def _refresh_progress_table(self) -> None:
        """Force a synchronous-style refresh (delegates to the async path)."""
        if self._widget("progress_table") is None:
            return
        self._refresh_progress_table_async(force=True)

    def _refresh_progress_table_async(self, *, force: bool = False) -> None:
        """Refresh the progress table on a background thread.

        Increments :attr:`_refresh_token` and captures it for the spawned
        worker; when the result arrives it is discarded if a newer refresh has
        since been requested (Requirement 6.3 / Property 8).
        """
        table = self._widget("progress_table")
        if table is None:
            return
        if self._is_app_closing():
            return

        inflight = bool(self._refresh_inflight)
        if inflight and not bool(force):
            started_at = float(self._refresh_started_at or 0.0)
            if started_at > 0.0 and (time.time() - started_at) > 12.0:
                self._refresh_inflight = False
                inflight = False
                status_label = self._widget("progress_status_label")
                if status_label is not None:
                    status_label.setText("Previous refresh was slow. Retrying…")
            else:
                return

        db_cfg = self._db_cfg()
        if not db_cfg:
            table.setRowCount(0)
            summary_label = self._widget("progress_summary_label")
            if summary_label is not None:
                summary_label.setText("Database is not configured")
            status_label = self._widget("progress_status_label")
            if status_label is not None:
                msg = "Configure Postgres in Settings → Database"
                status_label.setText(msg)
                self._set_global_status(msg, source="Progress")
            return

        from_ymd = _calendar_picker_value(self._widget("progress_from_date"))
        to_ymd = _calendar_picker_value(self._widget("progress_to_date"))

        limit = 25
        limit_combo = self._widget("progress_limit_combo")
        if limit_combo is not None:
            try:
                limit = int(str(limit_combo.currentText() or "25").strip() or "25")
            except Exception:
                limit = 25
        limit = max(1, min(200, limit))

        active_toggle = self._widget("progress_active_only")
        active_only = bool(active_toggle.isChecked()) if active_toggle is not None else False

        token = int(self._refresh_token or 0) + 1
        self._refresh_token = token
        self._refresh_inflight = True
        self._refresh_started_at = time.time()

        status_label = self._widget("progress_status_label")
        if status_label is not None:
            status_label.setText("Refreshing…")

        started = time.time()

        def work() -> None:
            try:
                t0 = time.time()
                try:
                    rows = self._collect_progress_rows(
                        limit=limit, active_only=active_only, from_ymd=from_ymd, to_ymd=to_ymd
                    )
                except RuntimeError as exc:
                    if "has been deleted" in str(exc).lower() or self._is_app_closing():
                        return
                    raise
                t1 = time.time()
                elapsed = time.time() - started

                def apply() -> None:
                    try:
                        if self._is_app_closing():
                            return
                        if int(self._refresh_token or 0) != token:
                            return
                        self._apply_progress_rows(rows)
                        label = self._widget("progress_status_label")
                        if label is not None:
                            msg = (
                                f"Refreshed at {time.strftime('%H:%M:%S')} · "
                                f"total {elapsed:.2f}s · compute {(t1 - t0):.2f}s"
                            )
                            label.setText(msg)
                        summary = self._widget("progress_summary_label")
                        if summary is not None:
                            footer = self._widget("footer")
                            music_msg = str(getattr(footer, "_music_status_message", "") or "")
                            image_msg = str(self._widget("image_status_message") or "")
                            summary.setText(f"Pipeline: {music_msg} · Images: {image_msg}")
                        self._refresh_inflight = False
                        self._refresh_started_at = 0.0
                    except Exception:
                        return

                self._ui_invoke(apply)
            except Exception as exc:
                def apply_err() -> None:
                    try:
                        if self._is_app_closing():
                            return
                        label = self._widget("progress_status_label")
                        if label is not None:
                            msg = f"Progress refresh failed: {exc}"
                            label.setText(msg)
                            self._set_global_status(msg, source="Progress")
                        self._refresh_inflight = False
                        self._refresh_started_at = 0.0
                    except Exception:
                        return

                self._ui_invoke(apply_err)

        threading.Thread(target=work, daemon=True).start()

    def _apply_progress_rows(self, rows: list[dict]) -> None:
        """Populate the progress table from collected *rows*."""
        table = self._widget("progress_table")
        if table is None:
            return
        table.setUpdatesEnabled(False)
        try:
            table.setRowCount(len(rows))
            for r, row in enumerate(rows):
                for c, key in enumerate(
                    [
                        "batch", "runDate", "channel", "status", "music", "image",
                        "converter", "merge", "youtube", "stage", "notes", "updated",
                    ]
                ):
                    item = QTableWidgetItem(str(row.get(key, "")).strip())
                    if key == "notes":
                        tip = str(row.get("notesFull", "")).strip()
                    else:
                        tip = str(row.get(key, "")).strip()
                    if tip and tip != str(row.get(key, "")).strip():
                        item.setToolTip(tip)
                    elif tip and len(tip) > 80:
                        item.setToolTip(tip)
                    if c == 0:
                        item.setData(Qt.ItemDataRole.UserRole, dict(row.get("_meta") or {}))
                    if key in {"status", "music", "converter", "youtube", "stage"}:
                        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    table.setItem(r, c, item)
        finally:
            table.setUpdatesEnabled(True)

    def _collect_progress_rows(
        self, *, limit: int, active_only: bool, from_ymd: str = "", to_ymd: str = ""
    ) -> list[dict]:
        """Collect progress rows from the database (runs on a worker thread)."""
        from ..database.image_db import list_image_jobs_for_batches
        from ..database.music_db import (
            count_songs_by_batch_ids,
            get_batch_run_dirs_by_batch_ids,
            get_latest_suno_output_dirs_by_batch_ids,
            list_batches_for_history,
            song_time_ranges_by_batch_ids,
        )

        db_cfg = self._db_cfg()
        if not db_cfg:
            return []

        music_data = self._widget("music_data")
        music_data = music_data if isinstance(music_data, dict) else {}
        youtube_coordinator = self._widget("youtube_coordinator")

        profiles = {
            str((p or {}).get("uid", "")).strip(): dict(p)
            for p in (music_data.get("profiles") or [])
            if isinstance(p, dict)
        }
        batches = list_batches_for_history(
            db_cfg,
            from_ymd=str(from_ymd or "").strip(),
            to_ymd=str(to_ymd or "").strip(),
            limit=int(limit),
        )
        auto_meta = self._widget("auto_video_batches")
        auto_meta = auto_meta if isinstance(auto_meta, dict) else {}
        out: list[dict] = []

        batch_ids = [
            str((b or {}).get("batchId", "")).strip()
            for b in batches
            if str((b or {}).get("batchId", "")).strip()
        ]
        song_counts = count_songs_by_batch_ids(db_cfg, batch_ids)
        song_times = song_time_ranges_by_batch_ids(db_cfg, batch_ids)
        run_dirs_map = get_batch_run_dirs_by_batch_ids(db_cfg, batch_ids)
        suno_dirs_map = get_latest_suno_output_dirs_by_batch_ids(db_cfg, batch_ids)

        profile_ids_all: list[str] = []
        for b in batches:
            ok_profile_id = str((b or {}).get("profileOkId", "")).strip()
            alt_profile_id = str((b or {}).get("profileAltId", "")).strip()
            if ok_profile_id:
                profile_ids_all.append(ok_profile_id)
            if alt_profile_id:
                profile_ids_all.append(alt_profile_id)
        profile_ids_all = list({x for x in profile_ids_all if x})
        jobs_all = list_image_jobs_for_batches(db_cfg, batch_ids=batch_ids, profile_ids=profile_ids_all)
        jobs_by_key: dict[tuple[str, str, str], dict] = {}
        for j in jobs_all:
            bid = str(j.get("batchId", "")).strip()
            pid = str(j.get("profileId", "")).strip()
            kind = str(j.get("kind", "")).strip().lower()
            if bid and pid and kind:
                jobs_by_key[(bid, pid, kind)] = j

        yt_jobs_all = []
        if youtube_coordinator is not None:
            try:
                yt_jobs_all = youtube_coordinator.list_upload_jobs_for_batches(
                    db_cfg, batch_ids=batch_ids, profile_ids=profile_ids_all
                )
            except Exception:
                yt_jobs_all = []
        yt_jobs_by_key: dict[tuple[str, str, str], dict] = {}
        for j in yt_jobs_all:
            bid = str(j.get("batchId", "")).strip()
            pid = str(j.get("profileId", "")).strip()
            role = str(j.get("role", "")).strip().upper()
            if bid and pid and role:
                k = (bid, pid, role)
                if k not in yt_jobs_by_key:
                    yt_jobs_by_key[k] = j

        prog_cache = self._widget("youtube_progress_by_job_uid")
        merging_dirs = self._widget("auto_video_merging_dirs")

        for b in batches:
            batch_id = str((b or {}).get("batchId", "")).strip()
            if not batch_id:
                continue
            ok_profile_id = str((b or {}).get("profileOkId", "")).strip()
            alt_profile_id = str((b or {}).get("profileAltId", "")).strip()
            run_date = str((b or {}).get("runDate", "")).strip()
            meta = auto_meta.get(batch_id, {}) if isinstance(auto_meta.get(batch_id), dict) else {}
            expected = int(meta.get("songsPerBatch", 0) or 0)
            saved = int(song_counts.get(batch_id, 0) or 0)
            if expected <= 0:
                expected = max(1, saved)

            dirs = run_dirs_map.get(batch_id) or {"okDir": "", "altDir": ""}
            if not str(dirs.get("okDir", "")).strip():
                dirs = suno_dirs_map.get(batch_id) or {"okDir": "", "altDir": ""}
            ok_dir = str(dirs.get("okDir", "") or "").strip()
            alt_dir = str(dirs.get("altDir", "") or "").strip()

            for role, pid, out_dir in (("OK", ok_profile_id, ok_dir), ("ALT", alt_profile_id, alt_dir)):
                prof_name = str((b or {}).get("profileOkName" if role == "OK" else "profileAltName", "")).strip()
                if not prof_name:
                    prof_name = str((profiles.get(pid, {}) or {}).get("name", "")).strip()
                channel_label = f"{prof_name} · {role}" if prof_name else role

                bg_job = jobs_by_key.get((batch_id, pid, "background")) or {}
                th_job = jobs_by_key.get((batch_id, pid, "thumbnail")) or {}
                bg_status = str(bg_job.get("status", "")).strip() or "—"
                th_status = str(th_job.get("status", "")).strip() or "—"
                img_text = f"BG {bg_status} · TH {th_status}"

                mp3_count = 0
                mp4_count = 0
                merged_name = ""
                scan: dict[str, object] = {}
                if out_dir:
                    scan = self._scan_progress_output_dir(out_dir)
                    mp3_count = int(scan.get("mp3Count", 0) or 0)
                    mp4_count = int(scan.get("mp4Count", 0) or 0)
                    merged_name = str(scan.get("mergedName", "")).strip()
                _s = self._settings() or {}
                auto_reel = bool(_s.get("autoReelAfterVideo", False))
                auto_merge = bool(_s.get("autoMergeAfterVideo", False))
                reel_mp4_count = int(scan.get("reelMp4Count", 0) or 0)
                if auto_reel:
                    converter_text = f"MP4 {mp4_count}/{expected} · Reel {reel_mp4_count}/{expected}"
                else:
                    converter_text = f"MP3 {mp3_count}/{expected} · MP4 {mp4_count}/{expected}"
                reel_merged_name = str(scan.get("reelMergedName", "")).strip()
                if reel_merged_name:
                    merge_text = f"{merged_name} · {reel_merged_name}" if merged_name else reel_merged_name
                else:
                    merge_text = merged_name or "—"
                youtube_text = "—"
                yt = yt_jobs_by_key.get((batch_id, pid, str(role).upper())) or {}
                yt_status = str(yt.get("status", "")).strip().upper()
                yt_uid = str(yt.get("jobUid", "")).strip()
                yt_url = str(yt.get("youtubeUrl", "")).strip()
                yt_err = str(yt.get("error", "")).strip()
                pct = None
                if isinstance(prog_cache, dict) and yt_uid:
                    try:
                        pct = float(prog_cache.get(yt_uid))
                    except Exception:
                        pct = None
                if yt_status == "READY":
                    youtube_text = "Done"
                elif yt_status == "RUNNING":
                    if isinstance(pct, (int, float)):
                        youtube_text = f"Uploading {int(max(0.0, min(1.0, float(pct))) * 100.0)}%"
                    else:
                        youtube_text = "Uploading…"
                elif yt_status == "PENDING":
                    youtube_text = "Queued"
                elif yt_status in {"FAILED", "BLOCKED"}:
                    youtube_text = "Failed"
                elif yt_status == "CANCELLED":
                    youtube_text = "Cancelled"
                elif yt_status:
                    youtube_text = yt_status.title()

                stage = "Done"
                notes = ""
                if str(bg_status).upper() == "CANCELLED" or str(th_status).upper() == "CANCELLED":
                    stage = "Cancelled"
                    notes = "Cancelled by user"
                if saved < expected:
                    stage = "Music"
                elif bg_status != "READY" or th_status != "READY":
                    stage = "Image"
                    if bg_status == "FAILED":
                        notes = str(bg_job.get("error", "")).strip()
                    elif th_status == "FAILED":
                        notes = str(th_job.get("error", "")).strip()
                elif mp4_count < expected:
                    stage = "Converter"
                elif auto_reel and reel_mp4_count < expected:
                    stage = "Converter"
                elif not merged_name:
                    if auto_merge and auto_reel and not reel_merged_name:
                        # Both merges needed, neither complete yet
                        if isinstance(merging_dirs, set) and out_dir and str(out_dir) in merging_dirs:
                            stage = "Merge"
                            notes = "Merging in progress..."
                        else:
                            stage = "Merge"
                    elif isinstance(merging_dirs, set) and out_dir and str(out_dir) in merging_dirs:
                        stage = "Merge"
                        notes = "Merging in progress..."
                    else:
                        stage = "Merge"
                elif auto_merge and auto_reel and not reel_merged_name:
                    # Standard merge done but reel merge still pending
                    if isinstance(merging_dirs, set) and out_dir and str(out_dir) in merging_dirs:
                        stage = "Merge"
                        notes = "Merging in progress..."
                    else:
                        stage = "Merge"
                elif yt_status in {"PENDING", "RUNNING", "FAILED", "BLOCKED"}:
                    stage = "YouTube"

                if stage == "Done" and (bg_status == "FAILED" or th_status == "FAILED"):
                    stage = "Error"
                if not notes:
                    if stage in {"Converter", "Merge"} and out_dir and not Path(out_dir).exists():
                        notes = "Output folder missing"
                    elif stage == "Merge" and mp4_count == expected and expected >= 2:
                        notes = "Waiting to merge"
                if not notes and yt_status in {"FAILED", "BLOCKED"} and yt_err:
                    notes = yt_err
                if not notes and yt_status == "READY" and yt_err:
                    notes = yt_err

                if not notes and stage == "Done":
                    _settings = self._settings()
                    auto_upload = bool((_settings or {}).get("autoUploadYouTube", False))
                    if not auto_upload:
                        if merged_name:
                            notes = "Completed"
                    else:
                        if yt_status == "READY":
                            notes = "Completed"

                status = "Done"
                if stage == "Error":
                    status = "Failed"
                elif stage == "Cancelled":
                    status = "Cancelled"
                elif stage == "Music":
                    status = "Generating" if saved > 0 else "Waiting"
                elif stage == "Image":
                    if bg_status == "RUNNING" or th_status == "RUNNING":
                        status = "Rendering"
                    elif bg_status == "PENDING" or th_status == "PENDING":
                        status = "Queued"
                    else:
                        status = "Waiting"
                elif stage == "Converter":
                    status = "Converting" if mp4_count > 0 else "Queued"
                elif stage == "Merge":
                    if isinstance(merging_dirs, set) and out_dir and str(out_dir) in merging_dirs:
                        status = "Merging"
                    else:
                        status = "Queued"
                elif stage == "YouTube":
                    if yt_status == "RUNNING":
                        status = "Uploading"
                    elif yt_status == "PENDING":
                        status = "Queued"
                    else:
                        status = "Failed"

                if active_only and stage in {"Done", "Cancelled"}:
                    continue

                out.append(
                    {
                        "batch": batch_id[-24:] if len(batch_id) > 24 else batch_id,
                        "runDate": run_date,
                        "channel": channel_label,
                        "status": status,
                        "music": f"{saved}/{expected}",
                        "image": img_text,
                        "converter": converter_text,
                        "merge": merge_text,
                        "youtube": youtube_text,
                        "stage": stage,
                        "notes": (notes[:120] + "…") if notes and len(notes) > 120 else notes,
                        "notesFull": notes,
                        "updated": time.strftime("%H:%M:%S"),
                        "_meta": {
                            "batchId": batch_id,
                            "runDate": run_date,
                            "role": role,
                            "profileId": pid,
                            "okProfileId": ok_profile_id,
                            "altProfileId": alt_profile_id,
                            "profileOk": str((b or {}).get("profileOkName", "")).strip(),
                            "profileAlt": str((b or {}).get("profileAltName", "")).strip(),
                            "outDir": out_dir,
                            "expected": int(expected),
                            "saved": int(saved),
                            "musicMinCreatedAt": str((song_times.get(batch_id, {}) or {}).get("minCreatedAt", "") or ""),
                            "musicMaxCreatedAt": str((song_times.get(batch_id, {}) or {}).get("maxCreatedAt", "") or ""),
                            "bgJobUid": str(bg_job.get("jobUid", "")).strip(),
                            "thJobUid": str(th_job.get("jobUid", "")).strip(),
                            "bgCreatedAt": str(bg_job.get("createdAt", "")).strip(),
                            "bgUpdatedAt": str(bg_job.get("updatedAt", "")).strip(),
                            "thCreatedAt": str(th_job.get("createdAt", "")).strip(),
                            "thUpdatedAt": str(th_job.get("updatedAt", "")).strip(),
                            "youtubeJobUid": yt_uid,
                            "youtubeStatus": yt_status,
                            "youtubeUrl": yt_url,
                            "youtubeCreatedAt": str(yt.get("createdAt", "")).strip(),
                            "youtubeUpdatedAt": str(yt.get("updatedAt", "")).strip(),
                            "mp4MinMTime": float(scan.get("mp4MinMTime", 0.0) or 0.0) if out_dir else 0.0,
                            "mp4MaxMTime": float(scan.get("mp4MaxMTime", 0.0) or 0.0) if out_dir else 0.0,
                            "mergedMTime": float(scan.get("mergedMTime", 0.0) or 0.0) if out_dir else 0.0,
                        },
                    }
                )

        out.sort(key=lambda r: (0 if r.get("stage") != "Done" else 1, str(r.get("channel", "")).strip()))
        out.sort(key=lambda r: (str(r.get("runDate", "")).strip(), str(r.get("batch", "")).strip()), reverse=True)
        return out[: int(limit) * 2]

    def _scan_progress_output_dir(self, out_dir: str) -> dict:
        """Scan *out_dir* for MP3/MP4/merged outputs, with mtime-based caching."""
        key = str(out_dir or "").strip()
        empty = {
            "mp3Count": 0, "mp4Count": 0, "mergedName": "",
            "mp4MinMTime": 0.0, "mp4MaxMTime": 0.0, "mergedMTime": 0.0,
            "reelMp4Count": 0, "reelMergedName": "", "reelMergedMTime": 0.0,
        }
        if not key:
            return empty
        cache = self._dir_cache
        p = Path(key)
        if not p.exists() or not p.is_dir():
            cache.pop(key, None)
            return empty
        try:
            dir_mtime = float(p.stat().st_mtime)
        except Exception:
            dir_mtime = 0.0
        cached = cache.get(key)
        cache_valid = (
            isinstance(cached, dict)
            and float(cached.get("dirMTime", -1.0) or -1.0) == dir_mtime
            and str((cached.get("data") or {}).get("mergedName", "")).strip()
        )
        if cache_valid:
            return cached.get("data") or empty

        mp3_count = 0
        mp4_count = 0
        merged_name = ""
        mp4_min_mt = 0.0
        mp4_max_mt = 0.0
        merged_mt = 0.0
        reel_mp4_count = 0
        reel_merged_name = ""
        reel_merged_mt = 0.0
        try:
            merged_best_mtime = -1.0
            reel_merged_best_mtime = -1.0
            with os.scandir(p) as it:
                for entry in it:
                    if not entry.is_file():
                        continue
                    name = str(entry.name or "")
                    low = name.lower()
                    if low.endswith(".mp3"):
                        mp3_count += 1
                        continue
                    if low.endswith(".mp4"):
                        upper_name = name.upper()
                        if upper_name.startswith("MERGED_REEL_"):
                            # Reel merged file
                            try:
                                mt = float(entry.stat().st_mtime)
                            except Exception:
                                mt = -1.0
                            if mt >= reel_merged_best_mtime:
                                reel_merged_best_mtime = mt
                                reel_merged_name = name
                                reel_merged_mt = float(mt if mt > 0 else 0.0)
                        elif upper_name.startswith("MERGED_"):
                            # Standard merged file
                            try:
                                mt = float(entry.stat().st_mtime)
                            except Exception:
                                mt = -1.0
                            if mt >= merged_best_mtime:
                                merged_best_mtime = mt
                                merged_name = name
                                merged_mt = float(mt if mt > 0 else 0.0)
                        elif low.endswith("_reel.mp4"):
                            # Reel MP4 (individual)
                            reel_mp4_count += 1
                        else:
                            # Standard MP4 (individual)
                            mp4_count += 1
                            try:
                                mt = float(entry.stat().st_mtime)
                            except Exception:
                                mt = 0.0
                            if mt > 0:
                                if mp4_min_mt <= 0 or mt < mp4_min_mt:
                                    mp4_min_mt = mt
                                if mt > mp4_max_mt:
                                    mp4_max_mt = mt
        except Exception:
            mp3_count = 0
            mp4_count = 0
            merged_name = ""
            mp4_min_mt = 0.0
            mp4_max_mt = 0.0
            merged_mt = 0.0
            reel_mp4_count = 0
            reel_merged_name = ""
            reel_merged_mt = 0.0
        data = {
            "mp3Count": mp3_count, "mp4Count": mp4_count, "mergedName": merged_name,
            "mp4MinMTime": mp4_min_mt, "mp4MaxMTime": mp4_max_mt, "mergedMTime": merged_mt,
            "reelMp4Count": reel_mp4_count, "reelMergedName": reel_merged_name,
            "reelMergedMTime": reel_merged_mt,
        }
        cache[key] = {"dirMTime": dir_mtime, "data": data}
        return data

    def _progress_row_meta_at(self, row_index: int) -> dict:
        """Return the ``_meta`` dict stored on the batch cell of *row_index*."""
        table = self._widget("progress_table")
        if table is None:
            return {}
        if row_index < 0 or row_index >= int(table.rowCount()):
            return {}
        item = table.item(row_index, 0)
        if item is None:
            return {}
        meta = item.data(Qt.ItemDataRole.UserRole)
        return dict(meta) if isinstance(meta, dict) else {}

    def _progress_mark_visible_rows_cancelling(self) -> int:
        """Mark visible cancellable rows as 'Cancelling…'; return count marked."""
        table = self._widget("progress_table")
        if table is None:
            return 0
        count = 0
        try:
            for r in range(int(table.rowCount())):
                stage_item = table.item(r, 9)
                stage = str(stage_item.text() if stage_item else "").strip()

                should_mark = False
                if stage == "Image":
                    img_item = table.item(r, 5)
                    img_text = str(img_item.text() if img_item else "").upper()
                    should_mark = "PENDING" in img_text or "RUNNING" in img_text
                elif stage == "YouTube":
                    yt_item = table.item(r, 8)
                    yt_text = str(yt_item.text() if yt_item else "").strip().upper()
                    should_mark = yt_text.startswith("UPLOADING") or yt_text == "QUEUED"

                if not should_mark:
                    continue

                status_item = table.item(r, 3)
                notes_item = table.item(r, 10)

                if status_item is None:
                    status_item = QTableWidgetItem("")
                    status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    table.setItem(r, 3, status_item)
                if stage_item is None:
                    stage_item = QTableWidgetItem("")
                    stage_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    table.setItem(r, 9, stage_item)
                if notes_item is None:
                    notes_item = QTableWidgetItem("")
                    table.setItem(r, 10, notes_item)

                status_item.setText("Cancelling…")
                stage_item.setText("Cancelling")
                notes_item.setText("Cancelling…")
                count += 1
        except Exception:
            return 0
        return count

    # ------------------------------------------------------------------
    # Row interactions
    # ------------------------------------------------------------------
    def _on_progress_cell_double_clicked(self, row: int, col: int) -> None:
        """Double-click on the Notes column shows the full note text."""
        table = self._widget("progress_table")
        if table is None:
            return
        if col != 10:
            return
        if row < 0 or row >= int(table.rowCount()):
            return
        item = table.item(row, 10)
        if item is None:
            return
        full_text = str(item.toolTip() or item.text() or "").strip()
        if not full_text:
            return
        parent = self._window()
        dlg = QDialog(parent)
        dlg.setWindowTitle("Full Notes")
        dlg.setModal(True)
        dlg.resize(600, 300)
        layout = QVBoxLayout(dlg)
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setPlainText(full_text)
        layout.addWidget(text_edit)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dlg.close)
        layout.addWidget(close_btn)
        dlg.setLayout(layout)
        dlg.exec()

    def _progress_cancel_row(self, meta: dict) -> None:
        """Cancel image + converter/merge + YouTube jobs for one batch/channel."""
        parent = self._window()
        db_cfg = self._db_cfg()
        if not db_cfg:
            QMessageBox.warning(parent, "Progress", "Postgres database is not configured. Set Database settings and run Migrate.")
            return
        batch_id = str(meta.get("batchId", "")).strip()
        profile_id = str(meta.get("profileId", "")).strip()
        role = str(meta.get("role", "")).strip().upper()
        if not batch_id or not profile_id or not role:
            return
        confirm = QMessageBox.question(
            parent,
            "Progress",
            "Cancel this row?\n\nThis will stop Image + Converter/Merge + YouTube for this batch/channel.\nExisting files will be kept.",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        reason = "Cancelled by user"
        cancelled_img = 0
        cancelled_yt = 0
        try:
            from ..database.image_db import cancel_image_jobs_for_row

            cancelled_img = int(cancel_image_jobs_for_row(db_cfg, batch_id=batch_id, profile_id=profile_id, reason=reason) or 0)
        except Exception as exc:
            self._log(f"[{time.strftime('%H:%M:%S')}] Cancel image jobs failed: {exc}")
        youtube_coordinator = self._widget("youtube_coordinator")
        if youtube_coordinator is not None:
            try:
                cancelled_yt = youtube_coordinator.cancel_jobs_for_row(db_cfg, batch_id=batch_id, profile_id=profile_id, role=role, reason=reason)
            except Exception:
                cancelled_yt = 0
        self._set_music_status(f"Cancelled row jobs: images={cancelled_img}, youtube={cancelled_yt}")
        self._refresh_progress_table_async(force=True)

    def _progress_cancel_all_pending_jobs(self) -> None:
        """Cancel all pending/running image + YouTube jobs in the database."""
        parent = self._window()
        db_cfg = self._db_cfg()
        if not db_cfg:
            QMessageBox.warning(parent, "Progress", "Postgres database is not configured. Set Database settings and run Migrate.")
            return
        confirm = QMessageBox.question(
            parent,
            "Progress",
            "Cancel ALL pending jobs in database?\n\nThis will cancel all pending/running Image jobs and YouTube upload jobs.\nExisting files will be kept.",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        if bool(self._cancel_all_inflight):
            QMessageBox.information(parent, "Progress", "Cancel-all is already running.")
            return

        self._cancel_all_inflight = True
        reason = "Cancelled by user"
        started = time.time()
        self._log(f"[{time.strftime('%H:%M:%S')}] Progress: cancel ALL pending jobs started")

        status_label = self._widget("progress_status_label")
        if status_label is not None:
            msg = "Cancelling all jobs…"
            status_label.setText(msg)
            self._set_global_status(msg, source="Progress")
        self._set_music_status("Cancelling all pending jobs…")
        changed = self._progress_mark_visible_rows_cancelling()
        if changed:
            self._log(f"[{time.strftime('%H:%M:%S')}] Progress: marked {changed} visible rows as Cancelling…")

        dlg = QProgressDialog("Cancelling jobs…", "", 0, 0, parent)
        dlg.setWindowTitle("Progress")
        dlg.setCancelButton(None)
        dlg.setWindowModality(Qt.WindowModality.ApplicationModal)
        dlg.show()
        self._cancel_all_dialog = dlg

        def ui_step(text: str) -> None:
            msg = str(text or "").strip()
            label = self._widget("progress_status_label")
            if label is not None:
                label.setText(msg)
                self._set_global_status(msg, source="Progress")
            d = self._cancel_all_dialog
            if d is not None:
                try:
                    d.setLabelText(msg)
                except Exception:
                    pass

        self._spawn_cancel_all_worker(reason=reason, started=started, ui_step=ui_step)

    def _spawn_cancel_all_worker(
        self, *, reason: str, started: float, ui_step: Callable[[str], None]
    ) -> None:
        def work() -> None:
            cancelled_img = 0
            cancelled_yt = 0
            had_error = False
            try:
                self._bus.ui_invoke.emit(lambda: ui_step("Cancelling Image and YouTube jobs…"))
                self._log(f"[{time.strftime('%H:%M:%S')}] Progress: cancelling Image and YouTube jobs…")
                summary = self._call("cancel_unfinished_background_jobs", reason=reason, stop_youtube_runtime=True)
                summary = summary if isinstance(summary, dict) else {}
                cancelled_img = int(summary.get("image", 0) or 0)
                cancelled_yt = int(summary.get("youtube", 0) or 0)
                errors = summary.get("errors") if isinstance(summary, dict) else []
                if errors:
                    raise RuntimeError("; ".join(str(x) for x in errors if str(x).strip()))
            except Exception as exc:
                had_error = True
                self._log(f"[{time.strftime('%H:%M:%S')}] Cancel pending jobs failed: {str(exc).strip()}")

            def apply_done() -> None:
                self._cancel_all_inflight = False
                d = self._cancel_all_dialog
                if d is not None:
                    try:
                        d.close()
                    except Exception:
                        pass
                self._cancel_all_dialog = None

                elapsed = time.time() - started
                msg = f"Cancelled pending jobs: images={cancelled_img}, youtube={cancelled_yt}"
                if had_error:
                    msg += " (with errors)"
                self._set_music_status(msg)
                self._log(
                    f"[{time.strftime('%H:%M:%S')}] Progress: cancel ALL done in {elapsed:.2f}s · "
                    f"images={cancelled_img} · youtube={cancelled_yt}"
                )
                label = self._widget("progress_status_label")
                if label is not None:
                    label.setText(f"{msg} · {elapsed:.2f}s")
                    self._set_global_status(f"{msg} · {elapsed:.2f}s", source="Progress")
                self._refresh_progress_table_async(force=True)

            self._bus.ui_invoke.emit(apply_done)

        threading.Thread(target=work, daemon=True).start()

    def _progress_restart_images(self, meta: dict, *, background: bool, thumbnail: bool) -> None:
        """Reset background and/or thumbnail image jobs for retry."""
        parent = self._window()
        db_cfg = self._db_cfg()
        if not db_cfg:
            return
        from ..database.image_db import reset_image_job_for_retry

        bg_uid = str(meta.get("bgJobUid", "")).strip()
        th_uid = str(meta.get("thJobUid", "")).strip()

        if background and bg_uid:
            try:
                reset_image_job_for_retry(db_cfg, bg_uid)
            except Exception as exc:
                QMessageBox.warning(parent, "Progress", f"Cannot restart background job:\n{exc}")
                return
        if thumbnail and th_uid:
            try:
                reset_image_job_for_retry(db_cfg, th_uid)
            except Exception as exc:
                QMessageBox.warning(parent, "Progress", f"Cannot restart thumbnail job:\n{exc}")
                return
        self._refresh_progress_table_async(force=True)
        image_coordinator = self._widget("image_coordinator")
        if image_coordinator is not None:
            try:
                image_coordinator.trigger_image_poll(manual=True, max_jobs=8)
            except Exception:
                pass

    def _progress_download_mp3_for_batch(self, meta: dict) -> None:
        """Re-download MP3 files from Suno for a batch/channel."""
        parent = self._window()
        db_cfg = self._db_cfg()
        if not db_cfg:
            QMessageBox.warning(parent, "Progress", "Postgres database is not configured.")
            return
        batch_id = str(meta.get("batchId", "")).strip()
        role = str(meta.get("role", "")).strip().upper()
        out_dir = str(meta.get("outDir", "")).strip()
        if not batch_id or not out_dir:
            QMessageBox.warning(parent, "Download MP3", "No batch ID or output directory for this row.")
            return

        from ..database.music_db import list_suno_tasks_by_batch
        from ..services.music_suno import (
            build_suno_output_paths,
            download_to_file,
            suno_api_try_get_tracks,
        )

        def work() -> None:
            try:
                tasks = list_suno_tasks_by_batch(db_cfg, batch_id)
                if not tasks:
                    self._set_global_status(f"Download MP3: no Suno tasks found for {batch_id}")
                    return
                generation_proxy = self._widget("generation_proxy")
                if not generation_proxy:
                    self._set_global_status("Download MP3 failed: not connected to Platform API")
                    return
                downloaded = 0
                skipped = 0
                failed = 0
                for task in tasks:
                    try:
                        task_id = str(task.get("taskId", "")).strip()
                        title = str(task.get("title", "")).strip()
                        track_no = task.get("trackNo")
                        if not task_id or not title:
                            skipped += 1
                            continue
                        result = suno_api_try_get_tracks(generation_proxy, task_id)
                        audio_urls = list(result.get("audioUrls") or [])
                        ok_url = str(audio_urls[0] or "").strip() if len(audio_urls) >= 1 else ""
                        alt_url = str(audio_urls[1] or "").strip() if len(audio_urls) >= 2 else ""
                        paths = build_suno_output_paths(output_dir=out_dir, title=title, track_no=track_no)
                        if role == "OK":
                            downloaded_ok = task.get("downloadedOk", False)
                            if ok_url and not downloaded_ok:
                                try:
                                    download_to_file(ok_url, paths["ok"])
                                    downloaded += 1
                                except Exception:
                                    failed += 1
                            elif downloaded_ok:
                                skipped += 1
                            else:
                                skipped += 1
                        elif role == "ALT":
                            downloaded_alt = task.get("downloadedAlt", False)
                            if alt_url and not downloaded_alt:
                                alt_path = paths["alt"]
                                try:
                                    download_to_file(alt_url, alt_path)
                                    downloaded += 1
                                except Exception:
                                    failed += 1
                            elif downloaded_alt:
                                skipped += 1
                            else:
                                skipped += 1
                    except Exception:
                        failed += 1
                self._set_global_status(f"Download MP3: {downloaded} downloaded, {skipped} skipped, {failed} failed")
            except Exception as exc:
                self._set_global_status(f"Download MP3 failed: {exc}")

        threading.Thread(target=work, daemon=True).start()
        self._set_global_status(f"Downloading MP3 for {batch_id} ({role})...")

    # ------------------------------------------------------------------
    # Output-folder helpers
    # ------------------------------------------------------------------
    def _progress_open_output_folder(self, out_dir: str) -> None:
        """Open *out_dir* in the system file explorer."""
        parent = self._window()
        path = str(out_dir or "").strip()
        if not path or not Path(path).exists():
            return
        try:
            os.startfile(path)  # type: ignore[attr-defined]
        except Exception as exc:
            QMessageBox.warning(parent, "Progress", f"Cannot open folder:\n{exc}")

    def _progress_copy_batch_id(self, batch_id: str) -> None:
        """Copy *batch_id* to the system clipboard."""
        try:
            QApplication.clipboard().setText(str(batch_id or "").strip())
        except Exception:
            return

    def _progress_move_output_folder(self, meta: dict) -> None:
        """Move a batch's output folder and update DB path references."""
        from PyQt6.QtWidgets import QFileDialog

        parent = self._window()
        out_dir = str(meta.get("outDir", "")).strip()
        batch_id = str(meta.get("batchId", "")).strip()
        if not out_dir or not Path(out_dir).exists():
            QMessageBox.information(parent, "Move Folder", "Output folder not found on disk.")
            return
        db_cfg = self._db_cfg()
        if not db_cfg:
            QMessageBox.information(parent, "Move Folder", "Database is not configured.")
            return

        active_channels = self._widget("auto_video_active_channels") or set()
        merging_dirs = self._widget("auto_video_merging_dirs") or set()
        batch_busy = any(str(k[0]) == batch_id for k in active_channels if isinstance(k, tuple) and k)
        if (
            batch_busy
            or str(out_dir) in {str(d) for d in merging_dirs}
            or bool(self._widget("export_batches"))
            or bool(self._widget("export_merge_running"))
            or int(self._merge_only_running or 0) > 0
        ):
            QMessageBox.information(
                parent,
                "Move Folder",
                "This batch (or an export/merge) is currently running. "
                "Wait for it to finish before moving the folder.",
            )
            return

        src = Path(out_dir)
        dest_parent = QFileDialog.getExistingDirectory(
            parent, "Choose destination drive/folder (e.g. your SSD)", str(src.parent)
        )
        if not dest_parent:
            return
        dest = Path(dest_parent) / src.name

        try:
            same = src.resolve() == dest.resolve()
        except Exception:
            same = str(src) == str(dest)
        if same:
            QMessageBox.information(parent, "Move Folder", "Source and destination are the same.")
            return
        if dest.exists():
            QMessageBox.warning(parent, "Move Folder", f"A folder named '{src.name}' already exists at the destination.")
            return

        confirm = QMessageBox.question(
            parent,
            "Move Output Folder",
            f"Move this batch's output folder?\n\nFrom:\n{src}\n\nTo:\n{dest}\n\n"
            "The database will be updated so workers use the new location.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        status_label = self._widget("progress_status_label")
        if status_label is not None:
            status_label.setText(f"Moving folder to {dest.parent}…")

        self._spawn_move_folder_worker(src=src, dest=dest, batch_id=batch_id, db_cfg=db_cfg)

    def _spawn_move_folder_worker(self, *, src: Path, dest: Path, batch_id: str, db_cfg: DbCfg) -> None:
        from ..database.music_db import relocate_batch_output_dir

        parent = self._window()

        def work() -> None:
            import shutil

            def ui(fn: Callable[[], None]) -> None:
                self._ui_invoke(fn)

            moved = False
            try:
                shutil.move(str(src), str(dest))
                moved = True
                result = relocate_batch_output_dir(db_cfg, batch_id=batch_id, old_dir=str(src), new_dir=str(dest))
                if not result.get("ok", False):
                    try:
                        if Path(dest).exists() and not Path(src).exists():
                            shutil.move(str(dest), str(src))
                    except Exception:
                        pass
                    msg = f"Move failed (database not updated): {result.get('message', '')}"
                    ui(lambda: QMessageBox.warning(parent, "Move Folder", msg))
                    return

                rows = int(result.get("updated", 0) or 0)

                def done_ok() -> None:
                    label = self._widget("progress_status_label")
                    if label is not None:
                        label.setText(f"Moved folder to {dest} · updated {rows} DB record(s)")
                    self._refresh_progress_table_async(force=True)

                ui(done_ok)
            except Exception as exc:
                if moved:
                    try:
                        if Path(dest).exists() and not Path(src).exists():
                            shutil.move(str(dest), str(src))
                    except Exception:
                        pass
                ui(lambda: QMessageBox.warning(parent, "Move Folder", f"Could not move folder:\n{exc}"))

        threading.Thread(target=work, daemon=True).start()

    # ------------------------------------------------------------------
    # Context menu
    # ------------------------------------------------------------------
    def _resolve_merge_path(self, *, row: int, out_dir: str) -> str:
        """Return the merged MP4 path for *row*, or "" when none exists."""
        table = self._widget("progress_table")
        if table is None:
            return ""
        merge_name = ""
        try:
            item_merge = table.item(row, 7)
            merge_name = str(item_merge.text() if item_merge else "").strip()
        except Exception:
            merge_name = ""
        try:
            if out_dir and merge_name and merge_name != "—":
                p = Path(out_dir) / merge_name
                if p.exists() and p.is_file():
                    return str(p)
        except Exception:
            return ""
        return ""

    def _on_progress_table_context_menu(self, pos: Any) -> None:
        """Show the right-click context menu for a progress-table row."""
        table = self._widget("progress_table")
        if table is None:
            return
        row = int(table.rowAt(pos.y()))
        meta = self._progress_row_meta_at(row)
        if not meta:
            return

        parent = self._window()
        db_cfg = self._db_cfg()
        menu = QMenu(parent)
        out_dir = str(meta.get("outDir", "")).strip()
        batch_id = str(meta.get("batchId", "")).strip()
        role = str(meta.get("role", "")).strip().upper()

        act_open = menu.addAction("Open Output Folder")
        act_move = menu.addAction("Move Output Folder (HDD → SSD)…")
        act_copy = menu.addAction("Copy Batch ID")
        menu.addSeparator()
        act_cancel_row = menu.addAction("Cancel Row (Stop All Jobs)")
        act_cancel_all = menu.addAction("Cancel ALL Pending Jobs (DB)")
        menu.addSeparator()
        act_img_all = menu.addAction("Restart Image (BG + TH)")
        act_img_bg = menu.addAction("Restart Background Only")
        act_img_th = menu.addAction("Restart Thumbnail Only")
        menu.addSeparator()
        act_conv = menu.addAction("Restart Converter (Generate Missing MP4)")
        act_conv_force = menu.addAction("Force Converter (Rebuild MP4)")
        act_merge = menu.addAction("Restart Merge Only")
        menu.addSeparator()
        act_yt_start = menu.addAction("Start YouTube Upload")
        act_yt_retry = menu.addAction("Retry YouTube Upload")
        act_yt_cancel = menu.addAction("Cancel YouTube Upload")
        act_yt_open = menu.addAction("Open YouTube URL")
        menu.addSeparator()
        act_download_mp3 = menu.addAction("Download MP3 (Retry from Suno)")
        menu.addSeparator()
        act_all = menu.addAction("Restart From Image (Image → Converter → Merge)")
        menu.addSeparator()
        act_hide = menu.addAction("Hide Batch (Delete Files + DB Records)")

        yt_uid = str(meta.get("youtubeJobUid", "")).strip()
        yt_url = str(meta.get("youtubeUrl", "")).strip()
        yt_status = str(meta.get("youtubeStatus", "")).strip().upper()
        merge_path = self._resolve_merge_path(row=row, out_dir=out_dir)
        if not out_dir:
            act_open.setEnabled(False)
            act_move.setEnabled(False)
            act_conv.setEnabled(False)
            act_conv_force.setEnabled(False)
            act_merge.setEnabled(False)
        if not db_cfg:
            act_move.setEnabled(False)
            act_img_all.setEnabled(False)
            act_img_bg.setEnabled(False)
            act_img_th.setEnabled(False)
            act_all.setEnabled(False)
            act_yt_start.setEnabled(False)
            act_yt_retry.setEnabled(False)
            act_yt_cancel.setEnabled(False)
            act_yt_open.setEnabled(False)
        if yt_uid and yt_status in {"PENDING", "RUNNING"}:
            act_yt_start.setEnabled(False)
        if not merge_path:
            act_yt_start.setEnabled(False)
        if not yt_uid:
            act_yt_retry.setEnabled(False)
            act_yt_cancel.setEnabled(False)
            act_yt_open.setEnabled(False)
        if yt_uid and not yt_url:
            act_yt_open.setEnabled(False)
        if role not in {"OK", "ALT"}:
            act_yt_start.setEnabled(False)
            act_yt_retry.setEnabled(False)
            act_yt_cancel.setEnabled(False)
            act_yt_open.setEnabled(False)

        chosen = menu.exec(table.viewport().mapToGlobal(pos))
        if chosen is None:
            return
        if chosen == act_open:
            self._progress_open_output_folder(out_dir)
        elif chosen == act_move:
            self._progress_move_output_folder(meta)
        elif chosen == act_copy:
            self._progress_copy_batch_id(batch_id)
        elif chosen == act_cancel_row:
            self._progress_cancel_row(meta)
        elif chosen == act_cancel_all:
            self._progress_cancel_all_pending_jobs()
        elif chosen == act_img_all:
            self._progress_restart_images(meta, background=True, thumbnail=True)
        elif chosen == act_img_bg:
            self._progress_restart_images(meta, background=True, thumbnail=False)
        elif chosen == act_img_th:
            self._progress_restart_images(meta, background=False, thumbnail=True)
        elif chosen == act_conv:
            self._progress_restart_converter(meta, force_rebuild=False)
        elif chosen == act_conv_force:
            self._progress_restart_converter(meta, force_rebuild=True)
        elif chosen == act_merge:
            self._progress_restart_merge_only(meta)
        elif chosen == act_yt_start:
            self._progress_start_youtube_upload(meta, merge_path=merge_path, yt_uid=yt_uid, yt_status=yt_status)
        elif chosen == act_yt_retry:
            self._progress_retry_youtube_upload(meta, yt_uid=yt_uid)
        elif chosen == act_yt_cancel:
            self._progress_cancel_youtube_upload(meta)
        elif chosen == act_yt_open:
            self._progress_open_youtube_url(yt_url)
        elif chosen == act_all:
            self._progress_restart_from_image(meta)
        elif chosen == act_download_mp3:
            self._progress_download_mp3_for_batch(meta)
        elif chosen == act_hide:
            self._progress_hide_batch_confirm(meta)

    # ------------------------------------------------------------------
    # Converter restart
    # ------------------------------------------------------------------
    def _progress_restart_converter(self, meta: dict, *, force_rebuild: bool) -> None:
        """Public entry point for restarting the converter for a row."""
        self._progress_restart_converter_impl(meta, force_rebuild=force_rebuild)

    def _progress_restart_converter_impl(self, meta: dict, *, force_rebuild: bool) -> None:
        """Re-queue the auto-video converter for a batch/channel."""
        parent = self._window()
        if (
            bool(self._widget("auto_video_running"))
            or bool(self._widget("export_batches"))
            or bool(self._widget("export_merge_running"))
        ):
            QMessageBox.information(parent, "Progress", "Auto-Video is busy. Try again after current export/merge finishes.")
            return
        batch_id = str(meta.get("batchId", "")).strip()
        ok_id = str(meta.get("okProfileId", "")).strip()
        alt_id = str(meta.get("altProfileId", "")).strip()
        profile_id = str(meta.get("profileId", "")).strip()
        role = str(meta.get("role", "")).strip().upper()
        out_dir = str(meta.get("outDir", "")).strip()
        expected = int(meta.get("expected", 0) or 0)
        if not batch_id or not profile_id or not role or not out_dir:
            return
        if not ok_id or not alt_id:
            ok_id = profile_id if role == "OK" else ok_id
            alt_id = profile_id if role == "ALT" else alt_id
        batches = self._widget("auto_video_batches")
        if not isinstance(batches, dict):
            batches = {}
        existing = batches.get(batch_id) if isinstance(batches.get(batch_id), dict) else {}
        batches[batch_id] = {
            "okProfileId": str(existing.get("okProfileId") or ok_id).strip(),
            "altProfileId": str(existing.get("altProfileId") or alt_id).strip(),
            "songsPerBatch": int(existing.get("songsPerBatch", 0) or expected or 0),
        }
        done = self._widget("auto_video_done")
        if isinstance(done, set):
            done.discard((batch_id, profile_id, role))
        if force_rebuild and out_dir and Path(out_dir).exists():
            try:
                for p in Path(out_dir).glob("*.mp4"):
                    if p.is_file() and not p.name.upper().startswith("MERGED_"):
                        try:
                            p.unlink()
                        except Exception:
                            pass
            except Exception:
                pass
        reasons = self._progress_auto_video_prereq_reasons(
            batch_id=batch_id, profile_id=profile_id, role=role, out_dir=out_dir, expected=expected
        )
        if reasons:
            detail = "\n".join([f"- {r}" for r in reasons][:10])
            if len(reasons) > 10:
                detail = f"{detail}\n- (+{len(reasons) - 10} more)"
            QMessageBox.information(parent, "Progress", f"Converter cannot start yet:\n{detail}")
            return
        started = self._call("try_start_auto_video_channel", batch_id, profile_id, role, out_dir, done=set())
        if not started:
            QMessageBox.information(parent, "Progress", "Converter cannot start yet. Open the row Notes/Stage for more context, then try again.")

    def _progress_auto_video_prereq_reasons(
        self, *, batch_id: str, profile_id: str, role: str, out_dir: str, expected: int
    ) -> list[str]:
        """Return reasons (if any) why auto-video cannot start for a row."""
        reasons: list[str] = []
        settings = self._settings()
        ffmpeg_path = find_ffmpeg_from_path_hint(
            str(settings.get("ffmpegPath", "")).strip() or str(self._widget("ffmpeg_path") or "").strip()
        )
        if not ffmpeg_path:
            reasons.append("FFmpeg is not configured (Settings → Music → FFmpeg Path).")
        elif not Path(str(ffmpeg_path)).exists():
            reasons.append("FFmpeg path does not exist.")
        d = Path(str(out_dir)).resolve()
        if not d.exists() or not d.is_dir():
            reasons.append("Output folder is missing.")
        else:
            mp3_count = 0
            try:
                mp3_count = len([p for p in d.glob("*.mp3") if p.is_file()])
            except Exception:
                mp3_count = 0
            if expected > 0 and mp3_count < expected:
                reasons.append(f"Not enough MP3 files yet ({mp3_count}/{expected}).")
        db_cfg = self._db_cfg()
        if db_cfg:
            try:
                from ..database.image_db import get_ready_background_output

                bg_path = get_ready_background_output(db_cfg, batch_id=batch_id, profile_id=profile_id)
                if not bg_path or not Path(str(bg_path)).exists():
                    reasons.append("Background image is not READY for this batch/channel.")
            except Exception:
                reasons.append("Cannot check background image readiness (DB error).")
        else:
            reasons.append("Database is not configured.")
        profile = self._call("music_profile_by_id", profile_id) or {}
        tpl_id = str(profile.get("videoTemplateId", "")).strip()
        if not tpl_id:
            reasons.append("Profile is missing video template mapping (Settings → Profiles → Video Template).")
        else:
            try:
                row = self._call("get_saved_video_template", tpl_id)
                if row is None:
                    reasons.append("Mapped video template is missing (template was deleted or DB not synced).")
            except Exception:
                reasons.append("Cannot load mapped video template.")
        return reasons

    # ------------------------------------------------------------------
    # Merge-only orchestration
    # ------------------------------------------------------------------
    def _merge_worker_limit(self) -> int:
        """Return the configured merge-worker concurrency limit (1..2)."""
        settings = self._settings()
        try:
            v = int(settings.get("perfMergeWorkers", 1) or 1)
        except Exception:
            v = 1
        return max(1, min(2, v))

    def _merge_running_count(self) -> int:
        """Return the number of merges currently running (export + merge-only)."""
        running = 1 if bool(self._widget("export_merge_running")) else 0
        running += int(self._merge_only_running or 0)
        return max(0, int(running))

    def _enqueue_merge_only_task(self, task: dict) -> None:
        """Append a merge-only *task* to the queue and try to drain it."""
        self._merge_only_queue.append(dict(task))
        self._drain_merge_only_queue()

    def _drain_merge_only_queue(self) -> None:
        """Start queued merge-only jobs up to the worker limit."""
        q = self._merge_only_queue
        if not q:
            return
        limit = self._merge_worker_limit()
        while q and self._merge_running_count() < limit:
            task = q.pop(0) if q else None
            if not isinstance(task, dict):
                continue
            ffmpeg_path = str(task.get("ffmpegPath", "")).strip()
            mp4s = [str(x).strip() for x in list(task.get("mp4s") or []) if str(x).strip()]
            target = str(task.get("targetPath", "")).strip()
            if not ffmpeg_path or not mp4s or not target:
                continue
            self._start_merge_only_thread(ffmpeg_path=ffmpeg_path, mp4s=mp4s, target_path=target)

    def _start_merge_only_thread(self, *, ffmpeg_path: str, mp4s: list[str], target_path: str) -> None:
        """Run a merge-only job on a background thread using the shared worker."""
        parent = self._window()
        self._merge_only_running = int(self._merge_only_running or 0) + 1

        def work() -> None:
            try:
                worker = self._merge_worker
                worker.on_status = lambda msg: self._bus.music_event.emit(
                    {"type": "auto_video_status", "message": msg}
                )
                worker.merge(ffmpeg_path, mp4s, str(target_path))
            except Exception as exc:
                self._bus.ui_invoke.emit(lambda: QMessageBox.warning(parent, "Progress", f"Merge failed:\n{exc}"))
            finally:
                try:
                    self._merge_only_running = max(0, int(self._merge_only_running or 0) - 1)
                except Exception:
                    self._merge_only_running = 0
                self._bus.ui_invoke.emit(lambda: self._refresh_progress_table_async(force=True))
                self._bus.ui_invoke.emit(self._drain_merge_only_queue)

        threading.Thread(target=work, daemon=True).start()

    def _progress_restart_merge_only(self, meta: dict) -> None:
        """Public entry point for restarting a merge-only job for a row."""
        self._progress_restart_merge_only_impl(meta)

    def _progress_restart_merge_only_impl(self, meta: dict) -> None:
        """Merge the row's MP4 outputs into a new MERGED_* file."""
        parent = self._window()
        settings = self._settings()
        ffmpeg_path = find_ffmpeg_from_path_hint(
            str(settings.get("ffmpegPath", "")).strip() or str(self._widget("ffmpeg_path") or "").strip()
        )
        if not ffmpeg_path:
            QMessageBox.warning(parent, "Progress", "FFmpeg is not configured.")
            return
        batch_id = str(meta.get("batchId", "")).strip()
        out_dir = str(meta.get("outDir", "")).strip()
        if not out_dir or not Path(out_dir).exists():
            return
        d = Path(out_dir)
        mp4s = [str(p) for p in d.glob("*.mp4") if p.is_file() and not p.name.upper().startswith("MERGED_")]
        mp4s = [p for p in mp4s if p]
        if len(mp4s) < 2:
            QMessageBox.information(parent, "Progress", "Not enough MP4 files to merge.")
            return
        suffix = self._call("safe_batch_suffix", batch_id) if batch_id else self._call("safe_batch_suffix", d.name)
        suffix = str(suffix or "").strip() or d.name
        target = d / f"MERGED_{suffix}.mp4"
        idx = 2
        while target.exists():
            target = d / f"MERGED_{suffix}-{idx}.mp4"
            idx += 1
        limit = self._merge_worker_limit()
        if self._merge_running_count() >= limit:
            self._enqueue_merge_only_task({"ffmpegPath": ffmpeg_path, "mp4s": mp4s, "targetPath": str(target)})
            QMessageBox.information(parent, "Progress", "Merge queued. Workers are busy.")
            return
        self._start_merge_only_thread(ffmpeg_path=ffmpeg_path, mp4s=mp4s, target_path=str(target))

    # ------------------------------------------------------------------
    # YouTube row actions
    # ------------------------------------------------------------------
    def _progress_start_youtube_upload(
        self, meta: dict, *, merge_path: str, yt_uid: str, yt_status: str
    ) -> None:
        """Queue (or restart) a YouTube upload for the row's merged MP4."""
        parent = self._window()
        db_cfg = self._db_cfg()
        youtube_coordinator = self._widget("youtube_coordinator")
        try:
            if not db_cfg:
                QMessageBox.warning(parent, "Progress", "Postgres database is not configured. Set Database settings and run Migrate.")
                return
            pid = str(meta.get("profileId", "")).strip()
            role = str(meta.get("role", "")).strip().upper()
            batch_id = str(meta.get("batchId", "")).strip()
            if not pid or not role or not batch_id:
                QMessageBox.warning(parent, "Progress", "Missing batch/profile metadata for this row.")
                return
            if role not in {"OK", "ALT"}:
                QMessageBox.warning(parent, "Progress", "YouTube upload only supports OK/ALT roles.")
                return
            if not merge_path:
                QMessageBox.warning(parent, "Progress", "Merged MP4 is missing for this row.")
                return
            ok_mp4, reason = self._call("youtube_is_mp4_ready_for_upload", merge_path, deep=False) or (False, "")
            if not ok_mp4:
                QMessageBox.warning(parent, "Progress", f"Cannot queue upload:\n{reason}")
                return
            if yt_uid and yt_status not in {"PENDING", "RUNNING"}:
                try:
                    rows = youtube_coordinator.force_job_pending(db_cfg, yt_uid, attempt_count=0, error="")
                except Exception as exc:
                    QMessageBox.warning(parent, "Progress", f"Start upload failed:\n{exc}")
                    return
                if rows <= 0:
                    QMessageBox.warning(parent, "Progress", "No matching YouTube job was found to restart.")
                    return
                self._set_music_status("YouTube job queued")
                QTimer.singleShot(0, lambda: self._call("youtube_upload_tick", force=True))
                self._refresh_progress_table_async(force=True)
                return
            try:
                account = youtube_coordinator.get_account(db_cfg, pid)
            except Exception:
                account = None
            if account is None or not str(getattr(account, "refresh_token_enc", "") or "").strip():
                QMessageBox.warning(parent, "Progress", "YouTube account is not connected for this profile. Connect first, then try again.")
                return
            self._call("enqueue_youtube_upload_for_merge", batch_id=batch_id, profile_id=pid, role=role, merged_mp4_path=merge_path)
            try:
                self._log(
                    f"[{time.strftime('%H:%M:%S')}] Progress: YouTube start requested: "
                    f"batch={batch_id} profile={pid} role={role} file={Path(merge_path).name}"
                )
            except Exception:
                pass
            self._set_music_status("YouTube job queued")
            QTimer.singleShot(0, lambda: self._call("youtube_upload_tick", force=True))
        except Exception as exc:
            QMessageBox.warning(parent, "Progress", f"Start upload failed:\n{exc}")
        self._refresh_progress_table_async(force=True)

    def _progress_retry_youtube_upload(self, meta: dict, *, yt_uid: str) -> None:
        """Force a previously failed YouTube job back to PENDING and retry."""
        parent = self._window()
        db_cfg = self._db_cfg()
        youtube_coordinator = self._widget("youtube_coordinator")
        try:
            rows = youtube_coordinator.force_job_pending(db_cfg, yt_uid, attempt_count=0, error="")
            try:
                self._log(
                    f"[{time.strftime('%H:%M:%S')}] Progress: YouTube retry requested: uid={yt_uid} rows={rows} "
                    f"batch={str(meta.get('batchId', '')).strip()} profile={str(meta.get('profileId', '')).strip()} "
                    f"role={str(meta.get('role', '')).strip()}"
                )
            except Exception:
                pass
            self._set_music_status("YouTube job queued for retry")
            if rows > 0:
                QTimer.singleShot(0, lambda: self._call("youtube_upload_tick", force=True))
        except Exception as exc:
            QMessageBox.warning(parent, "Progress", f"Retry failed:\n{exc}")
        self._refresh_progress_table_async(force=True)

    def _progress_cancel_youtube_upload(self, meta: dict) -> None:
        """Cancel the YouTube upload job for the row."""
        parent = self._window()
        db_cfg = self._db_cfg()
        youtube_coordinator = self._widget("youtube_coordinator")
        try:
            youtube_coordinator.cancel_jobs_for_row(
                db_cfg,
                batch_id=str(meta.get("batchId", "")).strip(),
                profile_id=str(meta.get("profileId", "")).strip(),
                role=str(meta.get("role", "")).strip().upper(),
                reason="Cancelled by user",
            )
            self._set_music_status("YouTube job cancelled")
        except Exception as exc:
            QMessageBox.warning(parent, "Progress", f"Cancel failed:\n{exc}")
        self._refresh_progress_table_async(force=True)

    def _progress_open_youtube_url(self, yt_url: str) -> None:
        """Open the YouTube URL in the default browser."""
        parent = self._window()
        try:
            webbrowser.open(str(yt_url or "").strip())
        except Exception as exc:
            QMessageBox.warning(parent, "Progress", f"Cannot open URL:\n{exc}")

    def _progress_restart_from_image(self, meta: dict) -> None:
        """Restart the full pipeline from the image stage onward."""
        self._progress_restart_images(meta, background=True, thumbnail=True)
        self._progress_restart_converter(meta, force_rebuild=False)

    # ------------------------------------------------------------------
    # Hide batch (destructive)
    # ------------------------------------------------------------------
    def _progress_hide_batch_confirm(self, meta: dict) -> None:
        """Confirm and execute hiding a batch (deletes files + DB records)."""
        parent = self._window()
        db_cfg = self._db_cfg()
        if not db_cfg:
            QMessageBox.warning(parent, "Hide Batch", "Postgres database is not configured.")
            return
        batch_id = str(meta.get("batchId", "")).strip()
        profile_ok = str(meta.get("profileOk", "")).strip()
        profile_alt = str(meta.get("profileAlt", "")).strip()
        if not batch_id:
            QMessageBox.warning(parent, "Hide Batch", "No batch ID for this row.")
            return

        profile_label = profile_ok if profile_ok else ""
        if profile_alt:
            profile_label = f"{profile_label} + {profile_alt}" if profile_label else profile_alt

        reply = QMessageBox.question(
            parent,
            "Hide Batch",
            f"Hide batch <b>{batch_id}</b>?\n\n"
            f"Profile: {profile_label}\n\n"
            "This will permanently delete:\n"
            "• All output files in the batch directory\n"
            "• All song records from the database\n"
            "• All image jobs and history entries\n"
            "• All Suno task records\n\n"
            "This action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        from PyQt6.QtCore import QThread, pyqtSignal

        from ..database.music_db import hide_batch

        class HideWorker(QThread):
            done_signal = pyqtSignal(dict)

            def __init__(self, db_cfg: Any, batch_id: str) -> None:
                super().__init__()
                self.db_cfg = db_cfg
                self.batch_id = batch_id

            def run(self) -> None:
                result = hide_batch(self.db_cfg, self.batch_id)
                self.done_signal.emit(result)

        def on_done(result: dict) -> None:
            if result.get("ok"):
                QMessageBox.information(
                    parent,
                    "Hide Batch",
                    f"Batch hidden successfully.\n"
                    f"Deleted {result.get('deleted_files', 0)} files and "
                    f"{result.get('deleted_db_records', 0)} database records.",
                )
                self._refresh_progress_table_async(force=True)
                self._call("refresh_history_rows")
            else:
                QMessageBox.warning(parent, "Hide Batch", f"Failed to hide batch:\n{result.get('message', 'Unknown error')}")

        worker = HideWorker(db_cfg, batch_id)
        worker.done_signal.connect(on_done)
        worker.start()
        self._hide_worker = worker  # Keep reference to prevent GC
