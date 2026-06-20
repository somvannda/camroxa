"""YouTube upload job runner extracted from MainWindow.

Handles the actual execution of a single YouTube upload job including:
- MP4 validation and retry logic
- Upload context preparation
- Upload execution with progress tracking
- Post-upload processing (thumbnail, playlist)
- Error handling with retry classification
"""
from __future__ import annotations

import re
import threading
import time
from pathlib import Path

from ..database.youtube_db import (
    db_mark_youtube_upload_job_cancelled,
    db_mark_youtube_upload_job_failed,
    db_mark_youtube_upload_job_pending,
    db_mark_youtube_upload_job_ready,
)
from ..features.youtube.coordinator import _Mp4NotReadyError
from ..features.youtube.debug_probe import _probe


from PyQt6.QtCore import Qt, QDate, QEvent, QObject, QPoint, QSize, QTimer

class YouTubeUploadHandlersMixin:
    """Mixin providing YouTube upload job execution for MainWindow."""

    def _run_one_youtube_upload_job(self, job: dict, cancel_evt: threading.Event):
        job_uid = str((job or {}).get("jobUid", "")).strip()
        if not job_uid or not self.db_cfg:
            return
        settings = self._music_settings()
        existing_vid = str(job.get("youtubeVideoId", "")).strip()
        file_path0 = str(job.get("filePath", "")).strip()

        _probe.emit(
            hypothesis="A",
            location="_run_one_youtube_upload_job:job-picked",
            msg="yt job picked",
            data={"job_uid": job_uid, "file_path": file_path0, "existing_vid": existing_vid},
        )

        # Phase 1: Prepare upload context (MP4 validation, credentials, metadata, thumbnail)
        try:
            ctx = self.youtube_coordinator.prepare_upload_context(job, settings)
        except _Mp4NotReadyError as _mp4_exc:
            _reason = str(_mp4_exc)
            _probe.emit(
                hypothesis="B",
                location="_run_one_youtube_upload_job:mp4-not-ready",
                msg="mp4 not ready",
                data={"job_uid": job_uid, "reason": _reason, "file_path": file_path0},
            )
            try:
                reason = str(_reason or "MP4 is not ready yet").strip() or "MP4 is not ready yet"
                attempt0 = int(job.get("attemptCount", 0) or 0)
                attempt1 = attempt0 + 1
                low_r = reason.lower()
                max_attempts = 60
                if "invalid mp4" in low_r or "ffprobe" in low_r:
                    max_attempts = 10
                if attempt1 >= max_attempts:
                    db_mark_youtube_upload_job_failed(self.db_cfg, job_uid, f"Upload aborted: {reason}", attempt1)
                else:
                    db_mark_youtube_upload_job_pending(self.db_cfg, job_uid, attempt_count=attempt1, error=f"MP4 not ready (attempt {attempt1}/{max_attempts}): {reason}")
            except Exception:
                pass
            return
        except Exception:
            raise

        # Phase 2: UI notifications and upload execution
        try:
            self._log(
                f"[{time.strftime('%H:%M:%S')}] YouTube worker picked job: uid={job_uid} batch={str(job.get('batchId', '')).strip()} profile={str(job.get('profileId', '')).strip()} role={str(job.get('role', '')).strip()} file={Path(str(job.get('filePath', '')).strip()).name}"
            )
        except Exception:
            pass
        if ctx["existing_video_id"]:
            self.bus.music_event.emit({"type": "youtube_upload_status", "message": "YouTube: updating existing upload"})
        else:
            self.bus.music_event.emit({"type": "youtube_upload_status", "message": f"YouTube: uploading {Path(ctx['file_path']).name}"})

        try:
            meta = ctx["meta"]
            if ctx["collision"]:
                batch_date = ""
                m = re.match(r"^batch-(\d{4}-\d{2}-\d{2})-", ctx["batch_id"])
                if m:
                    batch_date = m.group(1)
                self.bus.music_event.emit(
                    {
                        "type": "youtube_upload_status",
                        "message": f"YouTube: multiple batches share {batch_date}. Change Publish time in the profile before the next upload.",
                    }
                )

            try:
                msg = self.youtube_coordinator.build_upload_start_status_message(
                    str(ctx["profile"].get("name", "")).strip(),
                    ctx["role"],
                    meta["privacy"] if meta.get("publishAt") else "unlisted",
                    str(ctx["profile"].get("youtubePublishAt", "")).strip(),
                )
                self.bus.music_event.emit({"type": "youtube_upload_status", "message": msg})
            except Exception:
                pass

            on_progress = None if ctx["existing_video_id"] else self.youtube_coordinator.create_upload_progress_callback(job_uid)

            _probe.emit(
                hypothesis="C",
                location="_run_one_youtube_upload_job:pre-upload",
                msg="pre-upload check",
                data={"job_uid": job_uid, "file_path": ctx["file_path"], "existing_video_id": ctx["existing_video_id"]},
            )

            result = self.youtube_coordinator.execute_job_upload(
                ctx=ctx,
                on_progress=on_progress,
                cancel_event=cancel_evt,
                chunk_size_mb=int(settings.get("youtubeUploadChunkSizeMb", 256) or 256),
            )

            uploaded_video_id = result["video_id"]
            uploaded_url = result["url"]
            warn = result["warnings"]

            if getattr(cancel_evt, "is_set", lambda: False)() and uploaded_video_id:
                db_mark_youtube_upload_job_cancelled(self.db_cfg, job_uid, reason="Cancelled by user", youtube_video_id=uploaded_video_id, youtube_url=uploaded_url)
                self.bus.music_event.emit({"type": "youtube_upload_done", "jobUid": job_uid, "ok": False, "retry": False, "error": "Cancelled by user"})
                return

            db_mark_youtube_upload_job_ready(self.db_cfg, job_uid, uploaded_video_id, uploaded_url, warn[:400] if warn else "")
            try:
                self._log(f"[{time.strftime('%H:%M:%S')}] YouTube upload done: uid={job_uid} videoId={uploaded_video_id} url={uploaded_url}")
                if warn:
                    self._log(f"[{time.strftime('%H:%M:%S')}] YouTube upload warnings: uid={job_uid} {warn}")
            except Exception:
                pass

            proc = result.get("processing_status")
            if proc is not None:
                is_failed, fail_msg = self.youtube_coordinator.is_processing_failed(
                    getattr(proc, "processing_status", "") or "",
                    getattr(proc, "upload_status", "") or "",
                )
                if is_failed:
                    reason = str(getattr(proc, "rejection_reason", "") or getattr(proc, "failure_reason", "") or "").strip()
                    msg_fail = f"{fail_msg} reason={reason}" if reason else fail_msg
                    db_mark_youtube_upload_job_failed(self.db_cfg, job_uid, msg_fail[:400], ctx["attempt_no"])
                    self.bus.music_event.emit({"type": "youtube_upload_done", "jobUid": job_uid, "ok": False, "retry": False, "error": msg_fail})
                    return

            for evt in self.youtube_coordinator.build_post_upload_notification_messages(result.get("thumb_err", ""), result.get("playlist_err", ""), bool(meta.get("playlistId", ""))):
                self.bus.music_event.emit(evt)
            self.bus.music_event.emit({"type": "youtube_upload_done", "jobUid": job_uid, "ok": True, "url": uploaded_url})
        except Exception as exc:
            msg = str(exc).strip() or "Unknown error"
            _probe.emit(
                hypothesis="D",
                location="_run_one_youtube_upload_job:upload-exception",
                msg="upload exception",
                data={"job_uid": job_uid, "error": msg},
            )
            low = msg.lower()
            if getattr(cancel_evt, "is_set", lambda: False)() or "upload cancelled" in low or "cancelled by user" in low:
                try:
                    vid = str(locals().get("uploaded_video_id", "") or "").strip()
                    url = str(locals().get("uploaded_url", "") or "").strip()
                    if vid and not url:
                        url = f"https://www.youtube.com/watch?v={vid}"
                    db_mark_youtube_upload_job_cancelled(self.db_cfg, job_uid, reason="Cancelled by user", youtube_video_id=vid, youtube_url=url)
                except Exception:
                    try:
                        db_mark_youtube_upload_job_cancelled(self.db_cfg, job_uid, reason="Cancelled by user")
                    except Exception:
                        pass
                self.bus.music_event.emit({"type": "youtube_upload_done", "jobUid": job_uid, "ok": False, "retry": False, "error": "Cancelled by user"})
                return
            attempt_no = int(job.get("attemptCount", 0) or 0) + 1
            _, transient = self.youtube_coordinator.classify_upload_exception(exc)
            retry_action = self.youtube_coordinator.compute_retry_action(attempt_no, transient)
            if retry_action["should_retry"]:
                try:
                    db_mark_youtube_upload_job_pending(self.db_cfg, job_uid, attempt_count=attempt_no, error=msg)
                except Exception:
                    pass
                try:
                    self._log(f"[{time.strftime('%H:%M:%S')}] YouTube upload failed (will retry): uid={job_uid} attempt={attempt_no} error={msg}")
                except Exception:
                    pass
                self.bus.music_event.emit({"type": "youtube_upload_done", "jobUid": job_uid, "ok": False, "retry": True, "error": msg})
            else:
                try:
                    db_mark_youtube_upload_job_failed(self.db_cfg, job_uid, msg, attempt_no)
                except Exception:
                    pass
                try:
                    self._log(f"[{time.strftime('%H:%M:%S')}] YouTube upload failed: uid={job_uid} attempt={attempt_no} error={msg}")
                except Exception:
                    pass
                self.bus.music_event.emit({"type": "youtube_upload_done", "jobUid": job_uid, "ok": False, "retry": False, "error": msg})
        finally:
            self.youtube_coordinator.complete_runtime_job(job_uid)

    def _sanitize_startup_youtube_auto_upload(self) -> None:
        settings = self._music_settings()
        if not bool(settings.get("autoUploadYouTube", False)):
            return
        try:
            self._apply_settings_patch_to_database({"autoUploadYouTube": False})
            self._log(f"[{time.strftime('%H:%M:%S')}] Startup: reset persisted YouTube auto-upload to OFF until manually resumed")
        except Exception as exc:
            self._log(f"[{time.strftime('%H:%M:%S')}] Startup: failed to reset YouTube auto-upload state: {exc}")

    def _sync_youtube_auto_poll_timer(self) -> None:
        """Sync YouTube auto-poll timer via TimerRegistry."""
        if not hasattr(self, '_timer_registry'):
            return
        settings = self._music_settings()
        enabled = (
            bool(settings.get("autoUploadYouTube", False))
            and bool(self.db_cfg)
            and not bool(getattr(self, "_app_closing", False))
        )
        self._timer_registry.sync("youtube_auto_poll", enabled=enabled)

    def _youtube_worker_limit(self) -> int:
        return self.youtube_coordinator.worker_limit()

    def _short_youtube_job_uid(self, job_uid: str) -> str:
        return self.youtube_coordinator.short_job_uid(job_uid)

    def _youtube_render_terminal_progress(self) -> None:
        return self.youtube_coordinator.render_terminal_progress()

    def _youtube_upload_tick(self, *, force: bool = False) -> None:
        return self.youtube_coordinator.upload_tick(force=force)

    def _set_youtube_status(self, text: str) -> None:
        msg = str(text or "").strip() or "Ready"
        if hasattr(self, "youtube_status_label"):
            self.youtube_status_label.setText(msg)
        self._set_global_status(msg, source="YouTube")

    def _refresh_youtube_jobs_table(self) -> None:
        return self.youtube_coordinator.refresh_jobs_table()

    def _refresh_youtube_jobs_table_impl(self) -> None:
        if not hasattr(self, "youtube_jobs_table"):
            return
        if not self.db_cfg:
            self.youtube_jobs_table.setRowCount(0)
            self._set_youtube_status("Database not configured")
            return
        try:
            rows = self.youtube_coordinator.load_job_rows(limit=300)
        except Exception as exc:
            self._set_youtube_status(f"YouTube load failed: {exc}")
            return
        self.youtube_coordinator.apply_job_rows(rows)
        self._set_youtube_status(f"YouTube jobs: {len(rows)}")

    def _selected_youtube_job_uid(self) -> str:
        return self.youtube_coordinator.selected_job_uid()

    def _selected_youtube_job_uid_impl(self) -> str:
        if not hasattr(self, "youtube_jobs_table"):
            return ""
        table = self.youtube_jobs_table
        idx = int(table.currentRow())
        if idx < 0:
            return ""
        item = table.item(idx, 0)
        return str(item.data(Qt.ItemDataRole.UserRole) or "").strip() if item is not None else ""

    def _retry_selected_youtube_job(self) -> None:
        return self.youtube_coordinator.retry_selected_job()

    def _cancel_youtube_upload(self) -> None:
        return self.youtube_coordinator.cancel_upload()

    def _cancel_youtube_upload_impl(self) -> None:
        return self.youtube_coordinator.cancel_active_upload()

    def _on_youtube_row_selected(self) -> None:
        return self.youtube_coordinator.on_row_selected()

    def _handle_youtube_connect_select_channel(self, event: dict) -> None:
        self.youtube_coordinator.handle_connect_select_channel(event)

    def _handle_youtube_connect_done(self, event: dict) -> None:
        self.youtube_coordinator.handle_connect_done(event)

    def _handle_youtube_playlists_loaded(self, event: dict) -> None:
        self.youtube_coordinator.handle_playlists_loaded(event)

    def _handle_youtube_upload_status(self, event: dict) -> None:
        self.youtube_coordinator.handle_upload_status(event)

    def _handle_youtube_upload_progress(self, event: dict) -> None:
        self.youtube_coordinator.handle_upload_progress(event)

    def _handle_youtube_upload_done(self, event: dict) -> None:
        self.youtube_coordinator.handle_upload_done(event)

    def _start_youtube_playlist_fetch(self, profile_id: str) -> None:
        self.youtube_coordinator.start_playlist_fetch(profile_id)

    def _youtube_is_mp4_ready_for_upload(self, file_path: str, *, deep: bool = False) -> tuple[bool, str]:
        return self.youtube_coordinator.is_mp4_ready_for_upload(file_path, deep=deep)

    def _on_perf_youtube_workers_changed(self, value: int) -> None:
        workers = max(1, min(5, int(value or 1)))
        self._persist_setting_patch({"perfYouTubeWorkers": workers})

    def _on_youtube_upload_chunk_size_changed(self, value: int) -> None:
        mb = max(8, min(512, int(value or 256)))
        mb = int(round(float(mb) / 8.0) * 8)
        self._persist_setting_patch({"youtubeUploadChunkSizeMb": mb})
