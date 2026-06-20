"""YouTubeCoordinator — owns YouTube upload orchestration.

Uses dependency injection via a protocol interface to avoid direct
MainWindow type coupling while preserving existing behavior.
"""
from __future__ import annotations

import re
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional, Protocol

from ...services.video_export import find_ffmpeg_from_path_hint
from ...utils.subprocess_utils import no_window_kwargs
from ...database.persistence import DbCfg
from ..ports import ConfirmFn, EventBusPort, InputFn, LoggerPort, TimerFactory, TimerHandle


class YouTubeHostPort(Protocol):
    """Protocol interface capturing what YouTubeCoordinator needs from its host.

    This replaces the direct MainWindow reference with a narrow interface,
    enabling instantiation with mock objects for testing.
    """

    db_cfg: Any
    bus: Any

    def _music_settings(self) -> dict: ...
    def _log(self, msg: str) -> None: ...
    def _set_music_status(self, msg: str) -> None: ...
    def _set_global_status(self, msg: str, *, source: str = "") -> None: ...
    def _music_profile_by_id(self, profile_id: str) -> dict | None: ...
    def _selected_music_settings_profile(self) -> dict | None: ...
    def _refresh_youtube_jobs_table_impl(self) -> None: ...
    def _selected_youtube_job_uid_impl(self) -> str: ...
    def _youtube_upload_tick(self, *, force: bool = False) -> None: ...
    def _set_progress_row_status(self, job_uid: str, text: str) -> None: ...
    def _apply_youtube_job_rows(self, rows: list[dict]) -> None: ...
    def _defer_call(self, fn: Callable[[], None]) -> None: ...


class YouTubeCoordinator:
    """Owns incremental YouTube workspace/profile orchestration extracted from MainWindow.

    This slice moves the UI-facing YouTube table refresh/selection actions,
    timer creation and auto-poll routing, profile connect/disconnect
    entrypoints, OAuth connect start/cancel worker lifecycle, connect-result
    bus-event handling, playlist fetch/cache result handling, upload status
    event handling, merged-output scan/enqueue routing, upload
    tick/queue-claim orchestration, the shared YouTube runtime helper
    cluster for worker-limit, short-job formatting, terminal progress
    rendering, MP4 readiness validation, and upload-progress callback
    creation behind a stable coordinator boundary while keeping the deeper
    per-job execution body and other tightly coupled upload execution seams
    host-owned for now.

    Dependencies are injected via the host protocol interface.
    """

    def __init__(
        self,
        *,
        host: YouTubeHostPort,
        db_cfg: DbCfg | None = None,
        bus: EventBusPort | None = None,
        settings_accessor: Callable[[], dict] | None = None,
        db_cfg_accessor: Callable[[], Any] | None = None,
        logger: LoggerPort | None = None,
        confirm_fn: ConfirmFn | None = None,
        input_fn: InputFn | None = None,
        timer_factory: TimerFactory | None = None,
    ) -> None:
        if host is None:
            raise ValueError("YouTubeCoordinator requires a non-None host")
        self.host = host
        self._db_cfg = db_cfg
        self._bus = bus
        self._settings_accessor = settings_accessor
        self._db_cfg_accessor = db_cfg_accessor
        self._logger = logger
        self._confirm = confirm_fn or self._noop_confirm
        self._input = input_fn or self._noop_input
        self._timer_factory = timer_factory or self._noop_timer_factory

    # -- No-op fallbacks for UI interaction callables --

    @staticmethod
    def _noop_confirm(title: str, message: str) -> None:
        """No-op fallback when no confirm_fn is provided."""

    @staticmethod
    def _noop_input(title: str, label: str, items: list[str], current: int) -> tuple[str, bool]:
        """No-op fallback when no input_fn is provided. Returns empty selection."""
        return ("", False)

    @staticmethod
    def _noop_timer_factory(interval_ms: int, callback: Callable[[], None]) -> TimerHandle:
        """No-op fallback when no timer_factory is provided. Returns an inert handle."""

        class _InertTimer:
            def start(self) -> None:
                pass

            def stop(self) -> None:
                pass

            def is_active(self) -> bool:
                return False

        return _InertTimer()

    def update_db_cfg(self, cfg: DbCfg | None) -> None:
        """Update the database configuration after a reconnection."""
        self._db_cfg = cfg

    def ensure_timers(self) -> None:
        host = self.host
        if not hasattr(host, "_youtube_auto_poll_timer"):
            host._youtube_auto_poll_timer = self._timer_factory(30000, host._youtube_upload_tick)
        if not hasattr(host, "_youtube_live_refresh_timer"):
            host._youtube_live_refresh_timer = self._timer_factory(
                1500,
                lambda: self.refresh_jobs_table() if getattr(host, "_current_primary_page", "") == "youtube" else None,
            )

    def sync_auto_poll_timer(self) -> None:
        host = self.host
        self.ensure_timers()
        settings = host._music_settings()
        enabled = bool(settings.get("autoUploadYouTube", False))
        db_ok = bool(host.db_cfg) and not bool(getattr(host, "_app_closing", False))
        timer = getattr(host, "_youtube_auto_poll_timer", None)
        if timer is None:
            return
        if enabled and db_ok:
            if not timer.is_active():
                timer.start()
        else:
            if timer.is_active():
                timer.stop()

    def refresh_jobs_table(self) -> None:
        return self.host._refresh_youtube_jobs_table_impl()

    def worker_limit(self) -> int:
        settings = self.host._music_settings()
        try:
            v = int(settings.get("perfYouTubeWorkers", 1) or 1)
        except Exception:
            v = 1
        return max(1, min(5, v))

    def short_job_uid(self, job_uid: str) -> str:
        s = str(job_uid or "").strip()
        if not s:
            return ""
        s = s.replace("yt-batch-", "")
        s = s.replace("-profile-", " p:")
        if len(s) > 44:
            s = s[:18] + "…" + s[-18:]
        return s

    def render_terminal_progress(self) -> None:
        host = self.host
        st = getattr(host, "_youtube_worker_state", None)
        jobs_map = st.get("jobs") if isinstance(st, dict) else None
        if not isinstance(jobs_map, dict) or not jobs_map:
            from ...utils.terminal import end_inline

            end_inline()
            return
        cache = getattr(host, "_youtube_progress_by_job_uid", None)
        parts: list[str] = []
        for uid in list(jobs_map.keys()):
            short = self.short_job_uid(uid)
            if not short:
                continue
            try:
                p = float(cache.get(uid, 0.0) if isinstance(cache, dict) else 0.0)
            except Exception:
                p = 0.0
            pct = int(max(0.0, min(1.0, p)) * 100.0)
            parts.append(f"{short} {pct}%")
        parts = parts[:6]
        if not parts:
            from ...utils.terminal import end_inline

            end_inline()
            return
        msg = f"[{time.strftime('%H:%M:%S')}] YouTube uploading: " + " | ".join(parts)
        from ...utils.terminal import print_inline

        print_inline(msg)

    def create_upload_progress_callback(self, job_uid: str) -> Callable[[float], None]:
        host = self.host
        uid = str(job_uid or "").strip()

        def on_progress(p: float):
            try:
                p2 = float(p)
            except Exception:
                p2 = 0.0
            p2 = max(0.0, min(100.0, p2))
            now = time.monotonic()
            last_ts = float(getattr(on_progress, "_last_ts", 0.0) or 0.0)
            last_pct = float(getattr(on_progress, "_last_pct", -1.0))
            emit = False
            if p2 >= 100.0:
                emit = True
            elif last_pct < 0.0:
                emit = True
            elif (now - last_ts) >= 0.25:
                emit = True
            elif int(p2) >= int(last_pct) + 1:
                emit = True
            if emit:
                setattr(on_progress, "_last_ts", now)
                setattr(on_progress, "_last_pct", p2)
                host.bus.music_event.emit({"type": "youtube_upload_progress", "jobUid": uid, "progress": float(p2)})
            return

        return on_progress

    def is_mp4_ready_for_upload(self, file_path: str, *, deep: bool = False) -> tuple[bool, str]:
        host = self.host
        fp = str(file_path or "").strip()
        if not fp:
            return False, "Missing file"
        p = Path(fp)
        if not p.exists() or not p.is_file():
            return False, "Missing file"
        try:
            st1 = p.stat()
        except Exception:
            return False, "Unreadable file"
        try:
            if int(st1.st_size) < 200_000:
                return False, "File too small"
        except Exception:
            return False, "File too small"
        try:
            age = float(time.time() - float(st1.st_mtime))
        except Exception:
            age = 0.0
        if age < 4.0:
            return False, "File is still being written"
        try:
            with open(str(p), "rb") as f:
                f.read(1)
        except Exception:
            return False, "File is locked"
        if not deep:
            return True, ""
        time.sleep(0.4)
        try:
            st2 = p.stat()
        except Exception:
            return False, "Unreadable file"
        try:
            if int(st1.st_size) != int(st2.st_size) or int(st1.st_mtime_ns) != int(st2.st_mtime_ns):
                return False, "File is still being written"
        except Exception:
            return False, "File is still being written"
        settings = host._music_settings()
        ffmpeg_path = find_ffmpeg_from_path_hint(
            str(settings.get("ffmpegPath", "")).strip() or str(getattr(host, "_ffmpeg_path", "")).strip()
        )
        ffprobe_path = ""
        try:
            ffmpeg_dir = str(Path(str(ffmpeg_path)).parent) if ffmpeg_path else ""
            candidate = Path(ffmpeg_dir) / "ffprobe.exe" if ffmpeg_dir else Path("ffprobe.exe")
            if candidate.exists():
                ffprobe_path = str(candidate)
            else:
                candidate2 = Path(str(ffmpeg_path)).with_name("ffprobe.exe")
                if candidate2.exists():
                    ffprobe_path = str(candidate2)
        except Exception:
            ffprobe_path = ""
        if not ffprobe_path or not Path(ffprobe_path).exists():
            return True, ""
        try:
            out = subprocess.check_output(
                [
                    ffprobe_path,
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=nw=1:nk=1",
                    str(fp),
                ],
                text=True,
                timeout=12,
                **no_window_kwargs(),
            )
            dur = max(0.0, float(str(out or "").strip() or "0"))
        except Exception:
            dur = 0.0
        if dur <= 0.2:
            return False, "Invalid MP4 (duration)"
        return True, ""

    def selected_job_uid(self) -> str:
        return self.host._selected_youtube_job_uid_impl()

    def retry_selected_job(self) -> None:
        host = self.host
        uid = self.selected_job_uid()
        if not uid:
            return
        if not host.db_cfg:
            return
        try:
            from .db import db_force_youtube_upload_job_pending

            n = int(db_force_youtube_upload_job_pending(host.db_cfg, uid, attempt_count=0, error="") or 0)
            try:
                host._log(f"[{time.strftime('%H:%M:%S')}] YouTube retry requested: uid={uid} rows={n}")
            except Exception:
                pass
        except Exception as exc:
            host._set_youtube_status(f"Retry failed: {exc}")
            return
        self.refresh_jobs_table()
        host._set_youtube_status("YouTube job queued for retry")

    def worker_jobs_map(self) -> dict:
        host = self.host
        state = getattr(host, "_youtube_worker_state", None)
        if not isinstance(state, dict):
            state = {"jobs": {}}
            host._youtube_worker_state = state
        jobs_map = state.get("jobs")
        if not isinstance(jobs_map, dict):
            jobs_map = {}
            state["jobs"] = jobs_map
        return jobs_map

    def cancel_runtime_jobs(self, *, stop_timer: bool = False, clear_running: bool = False) -> tuple[int, list[str]]:
        host = self.host
        errors: list[str] = []
        if stop_timer:
            timer = getattr(host, "_youtube_auto_poll_timer", None)
            if timer is not None:
                try:
                    if timer.is_active():
                        timer.stop()
                except Exception as exc:
                    errors.append(f"youtube timer: {exc}")
        count = 0
        jobs_map = self.worker_jobs_map()
        for meta in list(jobs_map.values()):
            if not isinstance(meta, dict):
                continue
            cancel_evt = meta.get("cancel")
            try:
                if cancel_evt is not None and hasattr(cancel_evt, "set"):
                    cancel_evt.set()
                    count += 1
            except Exception as exc:
                errors.append(f"youtube worker cancel: {exc}")
        if clear_running:
            host._youtube_upload_running = False
        return count, errors

    def cancel_active_upload(self) -> None:
        host = self.host
        jobs_map = self.worker_jobs_map()
        if jobs_map:
            self.cancel_runtime_jobs(stop_timer=False)
            return
        evt = getattr(host, "_youtube_cancel_event", None)
        if evt is not None:
            try:
                evt.set()
            except Exception:
                pass

    def complete_runtime_job(self, job_uid: str) -> None:
        host = self.host
        uid = str(job_uid or "").strip()
        jobs_map = self.worker_jobs_map()
        if uid:
            try:
                jobs_map.pop(uid, None)
            except Exception:
                pass
        host._youtube_upload_running = bool(jobs_map)

    def cancel_upload(self) -> None:
        return self.cancel_active_upload()

    def on_row_selected(self) -> None:
        host = self.host
        uid = self.selected_job_uid()
        has_sel = bool(uid)
        if hasattr(host, "youtube_retry_button"):
            host.youtube_retry_button.setEnabled(has_sel)
        if hasattr(host, "youtube_cancel_button"):
            host.youtube_cancel_button.setEnabled(bool(getattr(host, "_youtube_upload_running", False)))

    def connect_cancel_event_for(self, profile_id: str) -> Any:
        pid = str(profile_id or "").strip()
        events = getattr(self.host, "_youtube_connect_cancel_events", None)
        if not isinstance(events, dict):
            return None
        return events.get(pid)

    @staticmethod
    def compute_retry_action(attempt_no: int, is_transient: bool) -> dict:
        """Compute whether to retry or fail after an upload exception.

        Returns dict with keys: should_retry (bool), action ('retry' | 'fail').
        """
        should_retry = attempt_no < 5 and is_transient
        return {
            "should_retry": should_retry,
            "action": "retry" if should_retry else "fail",
        }

    def clear_connect_state(self, profile_id: str) -> None:
        host = self.host
        pid = str(profile_id or "").strip()
        events = getattr(host, "_youtube_connect_cancel_events", None)
        if isinstance(events, dict) and pid in events:
            try:
                events.pop(pid, None)
            except Exception:
                pass
        if hasattr(host, "music_settings_profile_youtube_disconnect_button"):
            host.music_settings_profile_youtube_disconnect_button.setText("Disconnect")

    def start_oauth_connect(self, profile_id: str, *, client_id: str, client_secret: str) -> None:
        host = self.host
        pid = str(profile_id or "").strip()
        if not pid:
            return
        if hasattr(host, "music_settings_profile_youtube_status"):
            host.music_settings_profile_youtube_status.setText("Connecting…")
        if hasattr(host, "music_settings_profile_youtube_connect_button"):
            host.music_settings_profile_youtube_connect_button.setEnabled(False)
        if hasattr(host, "music_settings_profile_youtube_disconnect_button"):
            host.music_settings_profile_youtube_disconnect_button.setEnabled(True)
            host.music_settings_profile_youtube_disconnect_button.setText("Cancel")

        cid = str(client_id or "").strip()
        sec = str(client_secret or "").strip()
        if not cid or not sec:
            host.bus.music_event.emit(
                {
                    "type": "youtube_connect_done",
                    "ok": False,
                    "profileId": pid,
                    "error": "YouTube OAuth client id/secret is missing",
                }
            )
            return
        cancel_events = getattr(host, "_youtube_connect_cancel_events", None)
        if not isinstance(cancel_events, dict):
            cancel_events = {}
            host._youtube_connect_cancel_events = cancel_events
        cancel_evt = threading.Event()
        cancel_events[pid] = cancel_evt

        def work() -> None:
            try:
                from .db import db_upsert_youtube_account
                from .oauth import oauth_connect
                from ...services.dpapi import dpapi_encrypt_to_base64

                res = oauth_connect(client_id=cid, client_secret=sec)
                if cancel_evt.is_set():
                    host.bus.music_event.emit(
                        {"type": "youtube_connect_done", "ok": False, "profileId": pid, "error": "Cancelled"}
                    )
                    return
                refresh_enc = dpapi_encrypt_to_base64(res.refresh_token)
                channels = res.channels if isinstance(getattr(res, "channels", None), list) else []
                if len(channels) > 1:
                    host.bus.music_event.emit(
                        {
                            "type": "youtube_connect_select_channel",
                            "ok": True,
                            "profileId": pid,
                            "refreshTokenEnc": refresh_enc,
                            "scopes": " ".join(res.scopes),
                            "channels": channels,
                        }
                    )
                    return
                if cancel_evt.is_set():
                    host.bus.music_event.emit(
                        {"type": "youtube_connect_done", "ok": False, "profileId": pid, "error": "Cancelled"}
                    )
                    return
                db_upsert_youtube_account(
                    host.db_cfg,
                    {
                        "profileId": pid,
                        "channelId": res.channel_id,
                        "channelTitle": res.channel_title,
                        "refreshTokenEnc": refresh_enc,
                        "scopes": " ".join(res.scopes),
                    },
                )
                host.bus.music_event.emit(
                    {
                        "type": "youtube_connect_done",
                        "ok": True,
                        "profileId": pid,
                        "channelId": res.channel_id,
                        "channelTitle": res.channel_title,
                    }
                )
            except Exception as exc:
                host.bus.music_event.emit({"type": "youtube_connect_done", "ok": False, "profileId": pid, "error": str(exc)})

        threading.Thread(target=work, daemon=True).start()

    def connect_profile(self) -> None:
        host = self.host
        profile = host._selected_music_settings_profile()
        if not profile:
            self._confirm("YouTube", "Select a profile first.")
            return
        if not host.db_cfg:
            self._confirm("YouTube", "Database is not configured. Run Settings → Database → Migrate first.")
            return
        pid = str(profile.get("id", "")).strip()
        try:
            client_id, client_secret = host._resolve_youtube_oauth_client(pid)
        except Exception as exc:
            self._confirm("YouTube", str(exc))
            return
        self.start_oauth_connect(pid, client_id=client_id, client_secret=client_secret)

    def disconnect_profile(self) -> None:
        host = self.host
        profile = host._selected_music_settings_profile()
        if not profile:
            self._confirm("YouTube", "Select a profile first.")
            return
        if not host.db_cfg:
            self._confirm("YouTube", "Database is not configured.")
            return
        pid = str(profile.get("id", "")).strip()
        evt = self.connect_cancel_event_for(pid)
        if evt is not None and not evt.is_set():
            try:
                evt.set()
            except Exception:
                pass
            self.clear_connect_state(pid)
            if hasattr(host, "music_settings_profile_youtube_status"):
                host.music_settings_profile_youtube_status.setText("Not connected")
            host._load_music_settings_profile_details()
            host._set_music_settings_status("YouTube connect cancelled")
            return
        try:
            from .db import db_delete_youtube_account

            db_delete_youtube_account(host.db_cfg, pid)
        except Exception as exc:
            self._confirm("YouTube", f"Disconnect failed:\n{exc}")
            return
        host._load_music_settings_profile_details()
        host._set_music_settings_status("YouTube disconnected")

    def handle_connect_select_channel(self, event: dict) -> bool:
        host = self.host
        pid = str(event.get("profileId", "")).strip()
        refresh_enc = str(event.get("refreshTokenEnc", "")).strip()
        scopes = str(event.get("scopes", "")).strip()
        channels = event.get("channels")
        if not pid or not refresh_enc or not isinstance(channels, list) or not channels:
            host.bus.music_event.emit(
                {"type": "youtube_connect_done", "ok": False, "profileId": pid, "error": "YouTube connect returned no channels"}
            )
            return True
        items: list[str] = []
        lookup: dict[str, tuple[str, str]] = {}
        for ch in channels:
            if not isinstance(ch, dict):
                continue
            cid = str(ch.get("id", "")).strip()
            title = str(ch.get("title", "")).strip() or "Channel"
            if not cid:
                continue
            label = f"{title} · {cid}"
            items.append(label)
            lookup[label] = (cid, title)
        if not items:
            host.bus.music_event.emit(
                {"type": "youtube_connect_done", "ok": False, "profileId": pid, "error": "YouTube connect returned no valid channels"}
            )
            return True
        choice, ok = QInputDialog.getItem(host, "YouTube", "Select channel for this profile:", items, 0, False)
        if not ok:
            try:
                self.clear_connect_state(pid)
            except Exception:
                pass
            host._set_music_status("YouTube connect cancelled")
            if str(getattr(host, "_music_settings_selected_profile_id", "") or "").strip() == pid:
                host._load_music_settings_profile_details()
            return True
        sel = lookup.get(str(choice or "").strip())
        if not sel:
            host.bus.music_event.emit(
                {"type": "youtube_connect_done", "ok": False, "profileId": pid, "error": "Selected channel is invalid"}
            )
            return True
        channel_id, channel_title = sel
        try:
            from .db import db_upsert_youtube_account

            db_upsert_youtube_account(
                host.db_cfg,
                {
                    "profileId": pid,
                    "channelId": channel_id,
                    "channelTitle": channel_title,
                    "refreshTokenEnc": refresh_enc,
                    "scopes": scopes,
                },
            )
        except Exception as exc:
            host.bus.music_event.emit({"type": "youtube_connect_done", "ok": False, "profileId": pid, "error": str(exc)})
            return True
        host.bus.music_event.emit(
            {"type": "youtube_connect_done", "ok": True, "profileId": pid, "channelId": channel_id, "channelTitle": channel_title}
        )
        return True

    def handle_connect_done(self, event: dict) -> bool:
        host = self.host
        ok = bool(event.get("ok", False))
        pid = str(event.get("profileId", "")).strip()
        try:
            self.clear_connect_state(pid)
        except Exception:
            pass
        if ok:
            title = str(event.get("channelTitle", "")).strip() or "Channel"
            host._set_music_status(f"YouTube connected: {title}")
            try:
                cache = getattr(host, "_youtube_playlists_cache", None)
                if isinstance(cache, dict):
                    cache.pop(pid, None)
            except Exception:
                pass
            try:
                host._youtube_scan_for_merged_outputs()
            except Exception:
                pass
            if str(getattr(host, "_music_settings_selected_profile_id", "") or "").strip() == pid:
                host._load_music_settings_profile_details()
        else:
            err = str(event.get("error", "")).strip() or "Unknown error"
            host._set_music_status(f"YouTube connect failed: {err}")
            if str(getattr(host, "_music_settings_selected_profile_id", "") or "").strip() == pid:
                host._load_music_settings_profile_details()
        return True

    def refresh_profile_playlists(self, profile_id: str, selected_id: str) -> None:
        host = self.host
        combo = getattr(host, "music_settings_profile_youtube_playlist", None)
        if combo is None:
            return
        pid = str(profile_id or "").strip()
        key = str(selected_id or "").strip()
        cache = getattr(host, "_youtube_playlists_cache", None)
        if not isinstance(cache, dict):
            cache = {}
            host._youtube_playlists_cache = cache
        rows = cache.get(pid)
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("No playlist", userData="")
        if isinstance(rows, list):
            for r in rows:
                if not isinstance(r, dict):
                    continue
                rid = str(r.get("id", "")).strip()
                title = str(r.get("title", "")).strip() or "Playlist"
                if rid:
                    combo.addItem(f"{title} · {rid}", userData=rid)
        if key and combo.findData(key) < 0:
            combo.addItem(f"Missing · {key}", userData=key)
        idx = combo.findData(key) if key else 0
        combo.setCurrentIndex(idx if idx >= 0 else 0)
        combo.blockSignals(False)

    def start_playlist_fetch(self, profile_id: str) -> None:
        host = self.host
        pid = str(profile_id or "").strip()
        if not pid or not host.db_cfg:
            return
        try:
            from .db import db_get_youtube_account
            from ...services.dpapi import dpapi_decrypt_from_base64
            from .uploader import list_playlists
        except Exception as exc:
            host.bus.music_event.emit({"type": "youtube_playlists_loaded", "ok": False, "profileId": pid, "error": str(exc)})
            return
        try:
            client_id, client_secret = host._resolve_youtube_oauth_client(pid)
        except Exception as exc:
            host.bus.music_event.emit({"type": "youtube_playlists_loaded", "ok": False, "profileId": pid, "error": str(exc)})
            return
        acc = None
        try:
            acc = db_get_youtube_account(host.db_cfg, pid)
        except Exception:
            acc = None
        if acc is None or not str(getattr(acc, "refresh_token_enc", "") or "").strip():
            host.bus.music_event.emit(
                {
                    "type": "youtube_playlists_loaded",
                    "ok": False,
                    "profileId": pid,
                    "error": "YouTube account is not connected for this profile",
                }
            )
            return
        refresh_token = dpapi_decrypt_from_base64(str(getattr(acc, "refresh_token_enc", "") or ""))
        scopes = (
            str(getattr(acc, "scopes", "") or "").split()
            if str(getattr(acc, "scopes", "") or "").strip()
            else ["https://www.googleapis.com/auth/youtube.readonly"]
        )

        def work() -> None:
            try:
                rows = list_playlists(
                    client_id=client_id,
                    client_secret=client_secret,
                    refresh_token=refresh_token,
                    scopes=scopes,
                )
                host.bus.music_event.emit(
                    {"type": "youtube_playlists_loaded", "ok": True, "profileId": pid, "playlists": rows}
                )
            except Exception as exc:
                host.bus.music_event.emit({"type": "youtube_playlists_loaded", "ok": False, "profileId": pid, "error": str(exc)})

        threading.Thread(target=work, daemon=True).start()

    def handle_playlists_loaded(self, event: dict) -> bool:
        host = self.host
        pid = str(event.get("profileId", "")).strip()
        ok = bool(event.get("ok", False))
        rows = event.get("playlists") if ok else None
        cache = getattr(host, "_youtube_playlists_cache", None)
        if not isinstance(cache, dict):
            cache = {}
            host._youtube_playlists_cache = cache
        cache[pid] = rows if isinstance(rows, list) else []
        if str(getattr(host, "_music_settings_selected_profile_id", "") or "").strip() == pid:
            host._load_music_settings_profile_details()
        return True

    def handle_upload_status(self, event: dict) -> bool:
        host = self.host
        msg = str(event.get("message", "")).strip()
        if msg:
            host._set_youtube_status(msg)
            host._set_music_status(msg)
        return True

    def handle_upload_progress(self, event: dict) -> bool:
        host = self.host
        job_uid = str(event.get("jobUid", "")).strip()
        prog = float(event.get("progress", 0.0) or 0.0)
        clamped = max(0.0, min(1.0, float(prog)))
        if job_uid:
            cache = getattr(host, "_youtube_progress_by_job_uid", None)
            if not isinstance(cache, dict):
                cache = {}
                host._youtube_progress_by_job_uid = cache
            cache[job_uid] = clamped
        host._set_youtube_status(f"YouTube: uploading… {int(prog * 100)}%")
        self.render_terminal_progress()
        self._set_progress_row_status(job_uid, f"Uploading {int(clamped * 100.0)}%")
        return True

    def handle_upload_done(self, event: dict) -> bool:
        host = self.host
        job_uid = str(event.get("jobUid", "")).strip()
        ok = bool(event.get("ok", False))
        url = str(event.get("url", "")).strip()
        if job_uid:
            try:
                cache = getattr(host, "_youtube_progress_by_job_uid", None)
                if isinstance(cache, dict):
                    cache.pop(job_uid, None)
            except Exception:
                pass
        if ok:
            msg = f"YouTube: uploaded · {url}" if url else "YouTube: uploaded"
            host._set_youtube_status(msg)
            host._set_music_status(msg)
        else:
            err = str(event.get("error", "")).strip() or "Upload failed"
            retry = bool(event.get("retry", False))
            host._set_youtube_status(f"YouTube: {err}{' (will retry)' if retry else ''}")
            host._set_music_status(f"YouTube upload failed: {err}")
        self.render_terminal_progress()
        self._set_progress_row_status(job_uid, "Done" if ok else ("Failed" if not bool(event.get("retry", False)) else "Queued"))
        return True

    def upload_tick(self, *, force: bool = False) -> None:
        host = self.host
        settings = host._music_settings()
        if bool(getattr(host, "_app_closing", False)):
            return
        if not bool(force) and not bool(settings.get("autoUploadYouTube", False)):
            return
        if not host.db_cfg:
            return
        try:
            self.scan_for_merged_outputs()
        except Exception:
            pass
        try:
            from .db import db_claim_pending_youtube_upload_jobs
        except Exception:
            return
        jobs_map = self.worker_jobs_map()
        dead: list[str] = []
        for uid, meta in list(jobs_map.items()):
            t = meta.get("thread") if isinstance(meta, dict) else None
            if t is None or not hasattr(t, "is_alive") or not bool(t.is_alive()):
                dead.append(uid)
        for uid in dead:
            try:
                jobs_map.pop(uid, None)
            except Exception:
                pass
        limit = self.worker_limit()
        running = len(jobs_map)
        if running >= limit:
            host._youtube_upload_running = True
            return
        need = max(1, int(limit - running))
        claimed = db_claim_pending_youtube_upload_jobs(host.db_cfg, max_jobs=need, max_running=limit)
        if not claimed:
            host._youtube_upload_running = bool(jobs_map)
            return
        for job in claimed:
            if not isinstance(job, dict):
                continue
            job_uid = str(job.get("jobUid", "")).strip()
            if not job_uid or job_uid in jobs_map:
                continue
            cancel_evt = threading.Event()
            t = threading.Thread(
                target=lambda j=dict(job), ev=cancel_evt: host._run_one_youtube_upload_job(j, ev),
                daemon=True,
            )
            jobs_map[job_uid] = {"thread": t, "cancel": cancel_evt}
            t.start()
        host._youtube_upload_running = bool(jobs_map)

    def _set_progress_row_status(self, job_uid: str, text: str) -> None:
        host = self.host
        if not job_uid:
            return
        if getattr(host, "_current_primary_page", "") != "progress" or not hasattr(host, "progress_table"):
            return
        try:
            for r in range(int(host.progress_table.rowCount())):
                meta = host._progress_row_meta_at(r)
                if str(meta.get("youtubeJobUid", "")).strip() != job_uid:
                    continue
                item = host.progress_table.item(r, 8)
                if item is None:
                    item = QTableWidgetItem("")
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    host.progress_table.setItem(r, 8, item)
                item.setText(text)
        except Exception:
            pass

    def apply_job_rows(self, rows: list[dict]) -> None:
        host = self.host
        if not hasattr(host, "youtube_jobs_table"):
            return
        table = host.youtube_jobs_table
        table.setRowCount(0)
        for row in rows:
            r = table.rowCount()
            table.insertRow(r)
            batch_id = str(row.get("batchId", "")).strip()
            profile_id = str(row.get("profileId", "")).strip()
            profile = host._music_profile_by_id(profile_id) or {}
            profile_name = str(profile.get("name", "")).strip()
            role = str(row.get("role", "")).strip()
            file_name = Path(str(row.get("filePath", "")).strip()).name
            status = str(row.get("status", "")).strip()
            attempts = str(int(row.get("attemptCount", 0) or 0))
            url = str(row.get("youtubeUrl", "")).strip()
            err = str(row.get("error", "")).strip()
            vals = [batch_id, profile_name or profile_id, role, file_name, status, attempts, url, err]
            for c, v in enumerate(vals):
                item = QTableWidgetItem(str(v))
                item.setData(Qt.ItemDataRole.UserRole, str(row.get("jobUid", "")).strip())
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                table.setItem(r, c, item)

    def load_job_rows(self, *, limit: int = 300) -> list[dict]:
        host = self.host
        if not host.db_cfg:
            return []
        from .db import db_list_youtube_upload_jobs

        return db_list_youtube_upload_jobs(host.db_cfg, limit=int(limit))

    def enqueue_upload_for_merge(self, *, batch_id: str, profile_id: str, role: str, merged_mp4_path: str) -> None:
        host = self.host
        bid = str(batch_id or "").strip()
        pid = str(profile_id or "").strip()
        r = str(role or "").strip().upper()
        fp = str(merged_mp4_path or "").strip()
        if not host.db_cfg or not bid or not pid or r not in {"OK", "ALT"} or not fp:
            return
        ok_mp4, _reason = self.is_mp4_ready_for_upload(fp, deep=False)
        if not ok_mp4:
            return
        try:
            from .db import db_enqueue_youtube_upload_job, db_get_youtube_account
        except Exception:
            return
        safe = re.sub(r"[^a-zA-Z0-9_.-]+", "-", f"{bid}-{pid}-{r}").strip("-")
        job_uid = f"yt-{safe}"[-180:]
        status = "PENDING"
        err = ""
        try:
            acc = db_get_youtube_account(host.db_cfg, pid)
            if acc is None or not str(acc.refresh_token_enc or "").strip():
                status = "BLOCKED"
                err = "YouTube not connected"
        except Exception:
            status = "BLOCKED"
            err = "YouTube status unavailable"
        db_enqueue_youtube_upload_job(
            host.db_cfg,
            {"jobUid": job_uid, "batchId": bid, "profileId": pid, "role": r, "filePath": fp, "status": status, "error": err},
        )
        if status == "PENDING" and bool(host._music_settings().get("autoUploadYouTube", False)) and not bool(getattr(host, "_app_closing", False)):
            QTimer.singleShot(0, host._youtube_upload_tick)
        if getattr(host, "_current_primary_page", "") == "youtube":
            QTimer.singleShot(0, host._refresh_youtube_jobs_table)

    def scan_for_merged_outputs(self) -> None:
        host = self.host
        if not bool(host._music_settings().get("autoUploadYouTube", False)):
            return
        if not host.db_cfg:
            return
        from ...database.music_db import get_batch_run_dirs_by_batch_id, get_latest_suno_output_dirs_by_batch_id

        batches = getattr(host, "_auto_video_batches", None)
        if not isinstance(batches, dict) or not batches:
            return
        for batch_id, meta in list(batches.items()):
            if not isinstance(meta, dict):
                continue
            ok_profile_id = str(meta.get("okProfileId", "")).strip()
            alt_profile_id = str(meta.get("altProfileId", "")).strip()
            if not ok_profile_id or not alt_profile_id:
                continue
            dirs = get_batch_run_dirs_by_batch_id(host.db_cfg, batch_id)
            if not str(dirs.get("okDir", "")).strip():
                dirs = get_latest_suno_output_dirs_by_batch_id(host.db_cfg, batch_id)
            for profile_id, role, out_dir in (
                (ok_profile_id, "OK", str(dirs.get("okDir", "")).strip()),
                (alt_profile_id, "ALT", str(dirs.get("altDir", "")).strip()),
            ):
                if not out_dir:
                    continue
                d = Path(out_dir)
                if not d.exists() or not d.is_dir():
                    continue
                merged = sorted([p for p in d.glob("MERGED_*.mp4") if p.is_file()], key=lambda p: int(p.stat().st_mtime), reverse=True)
                if not merged:
                    continue
                chosen = ""
                for cand in merged[:5]:
                    ok_mp4, _reason = self.is_mp4_ready_for_upload(str(cand), deep=False)
                    if ok_mp4:
                        chosen = str(cand)
                        break
                if chosen:
                    self.enqueue_upload_for_merge(batch_id=batch_id, profile_id=profile_id, role=role, merged_mp4_path=chosen)

    def get_upload_credentials(
        self,
        profile_id: str,
        profile: dict,
        settings: dict,
    ) -> tuple[str, str, str]:
        """Load and decrypt YouTube OAuth credentials for an upload job.

        Returns (refresh_token, client_id, client_secret) ready for use with the YouTube API.
        Raises RuntimeError if credentials are missing or account is not connected.
        """
        if not self.host.db_cfg:
            raise RuntimeError("Database is not configured")

        from .db import db_get_youtube_account, db_get_youtube_oauth_app
        from ...services.dpapi import dpapi_decrypt_from_base64

        acc = db_get_youtube_account(self.host.db_cfg, profile_id)
        if acc is None or not str(acc.refresh_token_enc or "").strip():
            raise RuntimeError("YouTube account is not connected for this profile")
        refresh_token = dpapi_decrypt_from_base64(acc.refresh_token_enc)

        oauth_app_id = str(profile.get("youtubeOauthAppId", "")).strip()
        client_id = ""
        client_secret = ""
        if oauth_app_id:
            app = db_get_youtube_oauth_app(self.host.db_cfg, oauth_app_id)
            if app is None:
                raise RuntimeError(f"Selected YouTube OAuth app is missing: {oauth_app_id}")
            client_id = str(app.client_id or "").strip()
            client_secret = dpapi_decrypt_from_base64(str(app.client_secret_enc or ""))
        else:
            client_id = str(settings.get("youtubeClientId", "")).strip()
            client_secret = str(settings.get("youtubeClientSecret", "")).strip()
        if not client_id or not client_secret:
            raise RuntimeError("YouTube OAuth client id/secret is missing for this profile")
        return refresh_token, client_id, client_secret

    def render_upload_metadata(
        self,
        profile: dict,
        batch_id: str,
        role: str,
    ) -> dict:
        """Render YouTube upload metadata from profile templates.

        Returns dict with: title, description, privacy, publish_at, tags,
        category_id, made_for_kids, contains_synth, playlist_id.
        """
        tpl_id = str(profile.get("videoTemplateId", "")).strip()
        title_t = str(profile.get("youtubeTitleTemplate", "")).strip() or "{profileName} {batchDate} {role}"
        desc_t = str(profile.get("youtubeDescriptionTemplate", "")).strip()

        batch_date = ""
        m = re.match(r"^batch-(\d{4}-\d{2}-\d{2})-", batch_id)
        if m:
            batch_date = m.group(1)

        repl = {
            "{profileName}": str(profile.get("name", "")).strip(),
            "{batchDate}": batch_date,
            "{templateId}": tpl_id,
            "{role}": role,
            "{batchId}": batch_id,
        }
        title = title_t
        description = desc_t
        for k, v in repl.items():
            title = title.replace(k, v)
            description = description.replace(k, v)

        mode = str(profile.get("youtubeVisibilityMode", "")).strip() or "unlisted"
        publish_at = ""
        privacy = mode if mode in {"private", "public", "unlisted"} else "unlisted"

        if mode == "scheduled":
            tval = str(profile.get("youtubePublishAt", "")).strip()
            hh = None
            mm = None
            if tval:
                m2 = re.match(r"^(\d{1,2}):(\d{2})$", tval)
                if m2:
                    hh = int(m2.group(1))
                    mm = int(m2.group(2))
                elif "T" in tval:
                    try:
                        safe = tval[:-1] + "+00:00" if tval.endswith("Z") else tval
                        dt0 = datetime.fromisoformat(safe)
                        try:
                            dt0 = dt0.astimezone()
                        except Exception:
                            pass
                        hh = int(dt0.hour)
                        mm = int(dt0.minute)
                    except Exception:
                        hh = None
                        mm = None
            if hh is None or mm is None:
                raise RuntimeError("Scheduled mode requires Publish time (HH:MM) in profile settings")
            if not batch_date:
                raise RuntimeError("Scheduled mode requires batch date in batchId")
            try:
                y, mo, d = [int(x) for x in batch_date.split("-")]
                dt = datetime(y, mo, d, max(0, min(23, int(hh))), max(0, min(59, int(mm)))).astimezone()
                publish_at = dt.isoformat(timespec="seconds")
            except Exception:
                raise RuntimeError("Unable to compute scheduled publish datetime from batch date and time")
            privacy = "private"

        tags = [t.strip() for t in str(profile.get("youtubeTags", "")).split(",") if t.strip()]
        category_id = str(profile.get("youtubeCategoryId", "")).strip()
        made_for_kids = bool(profile.get("youtubeMadeForKids", False))
        contains_synth = bool(profile.get("youtubeContainsSyntheticMedia", False))
        playlist_id = str(profile.get("youtubePlaylistId", "")).strip()

        return {
            "title": title,
            "description": description,
            "privacy": privacy,
            "publishAt": publish_at,
            "tags": tags,
            "categoryId": category_id,
            "madeForKids": made_for_kids,
            "containsSynth": contains_synth,
            "playlistId": playlist_id,
        }

    def resolve_thumbnail_path(
        self,
        batch_id: str,
        role: str,
        file_path: str,
    ) -> str:
        """Resolve the thumbnail file path for a YouTube upload job.

        Looks up the batch run directory from the database, falls back to
        inferring from the file path, then searches for thumbnails in
        priority order: thumbnail_{suffix}.png, thumbnail.png, most recent
        file in thumbnails/ subdirectory.

        Returns the resolved thumbnail path or raises RuntimeError.
        """
        if not self.host.db_cfg:
            raise RuntimeError("Database is not configured")

        from ...database.music_db import get_batch_run_dirs_by_batch_id, get_latest_suno_output_dirs_by_batch_id

        role_key = str(role or "").strip().upper() or "OK"
        dirs = get_batch_run_dirs_by_batch_id(self.host.db_cfg, batch_id)
        if not str(dirs.get("okDir", "")).strip():
            dirs = get_latest_suno_output_dirs_by_batch_id(self.host.db_cfg, batch_id)
        run_dir = str(dirs.get("okDir" if role_key == "OK" else "altDir", "")).strip()
        if not run_dir:
            p = Path(file_path)
            try:
                if p.parent.name.lower() == "merged" and p.parent.parent.name.lower() == "video":
                    run_dir = str(p.parent.parent.parent)
            except Exception:
                run_dir = ""
        if not run_dir:
            raise RuntimeError("Cannot determine batch run directory for thumbnail")

        suffix = self._safe_batch_suffix(batch_id)
        cand1 = Path(run_dir) / f"thumbnail_{suffix}.png"
        cand2 = Path(run_dir) / "thumbnail.png"
        if cand1.exists() and cand1.is_file():
            return str(cand1)
        if cand2.exists() and cand2.is_file():
            return str(cand2)
        tdir = Path(run_dir) / "thumbnails"
        if tdir.exists() and tdir.is_dir():
            files = [*tdir.glob("*.png"), *tdir.glob("*.jpg"), *tdir.glob("*.jpeg")]
            files = [f for f in files if f.exists() and f.is_file()]
            files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            if files:
                return str(files[0])
        raise RuntimeError("Thumbnail not found for this batch. Generate thumbnail first.")

    def _safe_batch_suffix(self, batch_id: str) -> str:
        text = str(batch_id or "").strip()
        m = re.match(r"^batch-(\d{4}-\d{2}-\d{2})-(\d+)-(\d+)$", text)
        if m:
            return f"{m.group(1)}_{m.group(2)}_{m.group(3)}"
        safe = re.sub(r"[^a-zA-Z0-9_.-]+", "_", text)
        if not safe:
            safe = "batch"
        return safe

    @staticmethod
    def build_upload_warnings(
        thumbnail_error: str,
        playlist_error: str,
        processing_status: str = "",
        upload_status: str = "",
    ) -> str:
        """Build a human-readable warning string from upload result fields.

        Joins non-empty error/warning components with ' · ' separator.
        """
        parts: list[str] = []
        thumb_err = str(thumbnail_error or "").strip()
        if thumb_err:
            parts.append(f"Thumbnail: {thumb_err}")
        pl_err = str(playlist_error or "").strip()
        if pl_err:
            parts.append(f"Playlist: {pl_err}")
        ps = str(processing_status or "").strip().lower()
        us = str(upload_status or "").strip().lower()
        if us and us not in {"processed", "uploaded"}:
            parts.append(f"Upload: {us}")
        if ps and ps not in {"succeeded"}:
            parts.append(f"Processing: {ps}")
        return " · ".join(parts).strip()

    @staticmethod
    def resolve_scopes(scopes_str: str) -> list[str]:
        """Resolve YouTube API scopes from the account's stored scopes string.

        Falls back to the default upload scope if none are stored.
        """
        text = str(scopes_str or "").strip()
        if text:
            return text.split()
        return ["https://www.googleapis.com/auth/youtube.upload"]

    @staticmethod
    def is_processing_failed(processing_status: str, upload_status: str) -> tuple[bool, str]:
        """Check whether a YouTube upload has failed post-upload processing.

        Returns (is_failed, failure_message).
        """
        ps = str(processing_status or "").strip().lower()
        us = str(upload_status or "").strip().lower()
        if ps == "failed" or us == "rejected":
            msg = f"YouTube processing failed: upload={us or 'unknown'} processing={ps or 'unknown'}"
            return True, msg
        return False, ""

    @staticmethod
    def classify_upload_exception(exc: Exception) -> tuple[int, bool]:
        """Classify whether a YouTube upload exception is transient (retryable).

        Returns (http_status_code_or_none, is_transient).
        """
        code = getattr(getattr(exc, "resp", None), "status", None)
        low = str(exc).lower()
        transient = False
        if isinstance(code, int) and code in (500, 502, 503, 504):
            transient = True
        if "timed out" in low or "timeout" in low or "eof occurred" in low or "temporarily unavailable" in low:
            transient = True
        if (
            "failed to resolve" in low
            or "name resolution" in low
            or "nameresolutionerror" in low
            or "getaddrinfo failed" in low
            or "temporary failure in name resolution" in low
            or "errno 1100" in low
        ):
            transient = True
        return code, transient

    def resolve_profile_for_upload(
        self,
        profile_id: str,
        db_cfg: Any,
    ) -> dict:
        """Resolve a profile dict for upload, trying DB first then host fallback."""
        pid = str(profile_id or "").strip()
        if not pid:
            return {}
        try:
            from ...database.persistence import db_list_profiles
            rows = db_list_profiles(db_cfg)
            for p in rows:
                if str((p or {}).get("id", "")).strip() == pid:
                    return dict(p)
        except Exception:
            pass
        host = self.host
        if hasattr(host, "_music_profile_by_id"):
            return host._music_profile_by_id(pid) or {}
        return {}

    def detect_same_day_collision(
        self,
        db_cfg: Any,
        batch_id: str,
        profile_id: str,
        current_job_uid: str,
    ) -> str:
        """Detect a same-profile, same-day already-published job.

        Returns its video ID if found, else empty string.
        """
        if not db_cfg:
            return ""
        batch_date = ""
        m = re.match(r"^batch-(\d{4}-\d{2}-\d{2})-", batch_id)
        if m:
            batch_date = m.group(1)
        if not batch_date:
            return ""
        try:
            from ...database.youtube_db import db_list_youtube_upload_jobs
            jobs = db_list_youtube_upload_jobs(db_cfg, limit=500)
        except Exception:
            return ""
        for j in jobs:
            if not isinstance(j, dict):
                continue
            if str(j.get("jobUid", "")).strip() == current_job_uid:
                continue
            if str(j.get("profileId", "")).strip() != profile_id:
                continue
            if str(j.get("status", "")).strip() != "ready":
                continue
            vid = str(j.get("youtubeVideoId", "")).strip()
            if not vid:
                continue
            jbid = str(j.get("batchId", "")).strip()
            jd = ""
            m2 = re.match(r"^batch-(\d{4}-\d{2}-\d{2})-", jbid)
            if m2:
                jd = m2.group(1)
            if jd == batch_date:
                return vid
        return ""

    def compute_scheduled_publish_time(
        self,
        profile: dict,
        batch_date: str,
    ) -> tuple[str, str]:
        """Compute (privacy, publish_at) for scheduled uploads.

        Returns privacy override and ISO publish datetime if scheduled mode.
        """
        mode = str(profile.get("youtubeVisibilityMode", "")).strip() or "unlisted"
        if mode != "scheduled":
            return mode, ""
        tval = str(profile.get("youtubePublishAt", "")).strip()
        hh = None
        mm = None
        if tval:
            m = re.match(r"^(\d{1,2}):(\d{2})$", tval)
            if m:
                hh = int(m.group(1))
                mm = int(m.group(2))
            elif "T" in tval:
                try:
                    safe = tval[:-1] + "+00:00" if tval.endswith("Z") else tval
                    dt0 = datetime.fromisoformat(safe)
                    try:
                        dt0 = dt0.astimezone()
                    except Exception:
                        pass
                    hh = int(dt0.hour)
                    mm = int(dt0.minute)
                except Exception:
                    hh = None
                    mm = None
        if hh is None or mm is None:
            raise RuntimeError("Scheduled mode requires Publish time (HH:MM) in profile settings")
        if not batch_date:
            raise RuntimeError("Scheduled mode requires batch date in batchId")
        try:
            y, mo, d = [int(x) for x in batch_date.split("-")]
            dt = datetime(y, mo, d, max(0, min(23, int(hh))), max(0, min(59, int(mm)))).astimezone()
            return "private", dt.isoformat(timespec="seconds")
        except Exception:
            raise RuntimeError("Unable to compute scheduled publish datetime from batch date and time")

    def retry_existing_video_upload(
        self,
        video_id: str,
        thumb_path: str,
        playlist_id: str,
        prev_err: str,
        existing_url: str,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        scopes: list[str],
        cancel_event: Any,
    ) -> dict:
        """Re-upload thumbnail and playlist for an existing YouTube video.

        Returns dict: {video_id, url, warnings, thumb_err, playlist_err}.
        """
        from .uploader import add_to_playlist, set_thumbnail

        thumb_err = str(
            set_thumbnail(
                video_id=video_id,
                thumbnail_path=thumb_path,
                client_id=client_id,
                client_secret=client_secret,
                refresh_token=refresh_token,
                scopes=scopes,
                cancel_event=cancel_event,
            )
            or ""
        ).strip()

        pl_err = ""
        if playlist_id and ("Playlist:" in prev_err or "playlist" in prev_err.lower()):
            pl_err = str(
                add_to_playlist(
                    video_id=video_id,
                    playlist_id=playlist_id,
                    client_id=client_id,
                    client_secret=client_secret,
                    refresh_token=refresh_token,
                    scopes=scopes,
                    cancel_event=cancel_event,
                )
                or ""
            ).strip()

        warn = self.build_upload_warnings(thumb_err, pl_err)
        url = existing_url or f"https://www.youtube.com/watch?v={video_id}"
        return {
            "video_id": video_id,
            "url": url,
            "warnings": warn,
            "thumb_err": thumb_err,
            "playlist_err": pl_err,
        }

    def validate_upload_prerequisites(
        self,
        mp4_path: str,
        credentials: dict,
    ) -> tuple[bool, str]:
        """Validate that an MP4 file and credentials are ready for upload.

        Args:
            mp4_path: Path to the MP4 file to upload.
            credentials: Dict with keys: client_id, client_secret, refresh_token, scopes.

        Returns:
            (is_valid, error_message). error_message is empty when valid.
        """
        fp = str(mp4_path or "").strip()
        if not fp:
            return False, "Missing MP4 file path"
        p = Path(fp)
        if not p.exists() or not p.is_file():
            return False, f"MP4 file not found: {p.name}"
        try:
            st = p.stat()
            if int(st.st_size) < 200_000:
                return False, "MP4 file too small"
        except Exception as exc:
            return False, f"Cannot read MP4 file: {exc}"

        cid = str(credentials.get("client_id", "")).strip()
        sec = str(credentials.get("client_secret", "")).strip()
        rt = str(credentials.get("refresh_token", "")).strip()
        if not cid:
            return False, "YouTube OAuth client_id is missing"
        if not sec:
            return False, "YouTube OAuth client_secret is missing"
        if not rt:
            return False, "YouTube OAuth refresh_token is missing (reconnect profile)"

        scopes = credentials.get("scopes")
        if not scopes or not isinstance(scopes, list) or not scopes:
            return False, "YouTube OAuth scopes are missing"

        return True, ""

    def build_upload_request(
        self,
        title: str,
        description: str,
        tags: list[str],
        privacy_status: str,
        category_id: str = "",
        made_for_kids: bool = False,
        contains_synthetic_media: bool = False,
        publish_at: str = "",
    ) -> dict:
        """Build the YouTube API request body for a video insert.

        Returns dict with keys: body (API request body), privacy_status (effective).
        """
        snippet: dict = {
            "title": str(title or "").strip(),
            "description": str(description or ""),
        }
        tag_list = [str(t).strip() for t in (tags or []) if str(t).strip()]
        if tag_list:
            snippet["tags"] = tag_list
        cat = str(category_id or "").strip()
        if cat:
            snippet["categoryId"] = cat

        effective_privacy = str(privacy_status or "unlisted").strip() or "unlisted"
        status: dict = {
            "privacyStatus": effective_privacy,
            "selfDeclaredMadeForKids": bool(made_for_kids),
            "containsSyntheticMedia": bool(contains_synthetic_media),
        }
        pa = str(publish_at or "").strip()
        if pa:
            status["privacyStatus"] = "private"
            status["publishAt"] = pa

        body = {"snippet": snippet, "status": status}
        return {"body": body, "privacy_status": effective_privacy}

    def execute_upload(
        self,
        mp4_path: str,
        title: str,
        description: str,
        tags: list[str],
        privacy_status: str,
        thumbnail_path: str = "",
        playlist_id: str = "",
        client_id: str = "",
        client_secret: str = "",
        refresh_token: str = "",
        scopes: list[str] | None = None,
        category_id: str = "",
        made_for_kids: bool = False,
        contains_synthetic_media: bool = False,
        publish_at: str = "",
        on_progress: Optional[Callable[[float], None]] = None,
        cancel_event: Any = None,
        chunk_size_mb: int = 256,
    ) -> tuple[str, object]:
        """Execute a YouTube video upload via the API.

        Args:
            mp4_path: Path to the MP4 file.
            title: Video title.
            description: Video description.
            tags: List of tag strings.
            privacy_status: One of 'private', 'public', 'unlisted'.
            thumbnail_path: Optional path to thumbnail image.
            playlist_id: Optional playlist ID to add the video to.
            client_id: OAuth client ID.
            client_secret: OAuth client secret.
            refresh_token: OAuth refresh token.
            scopes: OAuth scopes list.
            category_id: YouTube video category ID.
            made_for_kids: COPPA declaration.
            contains_synthetic_media: Synthetic media declaration.
            publish_at: ISO datetime for scheduled publish.
            on_progress: Optional progress callback.
            cancel_event: Optional threading.Event for cancellation.
            chunk_size_mb: Resumable upload chunk size in MB.

        Returns:
            (video_id, UploadResult) tuple.

        Raises:
            ValueError on missing parameters.
            RuntimeError on API errors.
        """
        from ...services.youtube_uploader import (
            UploadResult,
            upload_video,
        )

        result = upload_video(
            file_path=mp4_path,
            thumbnail_path=thumbnail_path,
            playlist_id=playlist_id,
            client_id=client_id,
            client_secret=client_secret,
            refresh_token=refresh_token,
            scopes=scopes or [],
            title=title,
            description=description,
            tags=tags,
            category_id=category_id,
            made_for_kids=made_for_kids,
            contains_synthetic_media=contains_synthetic_media,
            privacy_status=privacy_status,
            publish_at=publish_at,
            on_progress=on_progress,
            cancel_event=cancel_event,
            chunk_size_mb=chunk_size_mb,
        )
        vid = str(getattr(result, "video_id", "") or "").strip()
        if not vid:
            raise RuntimeError("Upload succeeded but video id is missing in response")
        return vid, result

    def get_processing_status(
        self,
        video_id: str,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        scopes: list[str],
    ) -> Optional[object]:
        """Fetch post-upload processing status from YouTube.

        Returns VideoProcessingStatus or None on failure.
        """
        from ...services.youtube_uploader import get_video_processing_status

        try:
            return get_video_processing_status(
                video_id=video_id,
                client_id=client_id,
                client_secret=client_secret,
                refresh_token=refresh_token,
                scopes=scopes,
            )
        except Exception:
            return None

    @staticmethod
    def build_upload_start_status_message(
        profile_name: str,
        role: str,
        visibility_mode: str,
        publish_at: str,
    ) -> str:
        """Build the upload-start status message string."""
        prof_label = profile_name or "Profile"
        mode_label = visibility_mode
        if visibility_mode == "scheduled":
            mode_label = f"scheduled · {publish_at}"
        return f"YouTube: {prof_label} · {role.upper() if role else 'OK'} · {mode_label}"

    @staticmethod
    def build_post_upload_notification_messages(
        thumb_err: str,
        pl_err: str,
        has_playlist_id: bool,
    ) -> list[dict]:
        """Build post-upload status notification events.

        Returns a list of event dicts to emit.
        """
        events: list[dict] = []
        if thumb_err:
            events.append({
                "type": "youtube_upload_status",
                "message": f"YouTube: uploaded, but thumbnail failed · {thumb_err}",
            })
        if has_playlist_id:
            if pl_err:
                events.append({
                    "type": "youtube_upload_status",
                    "message": f"YouTube: uploaded, but failed to add to playlist · {pl_err}. Disconnect and reconnect this profile to grant playlist permissions.",
                })
            else:
                events.append({
                    "type": "youtube_upload_status",
                    "message": "YouTube: added video to playlist",
                })
        return events

    # -- Cross-feature DB facades (used by progress coordinator) --

    def list_upload_jobs_for_batches(self, db_cfg: Any, batch_ids: list[str], profile_ids: list[str]) -> list[dict]:
        """List YouTube upload jobs for given batch IDs. Returns list of job dicts."""
        from ...database.youtube_db import list_youtube_upload_jobs_for_batches
        return list_youtube_upload_jobs_for_batches(db_cfg, batch_ids=batch_ids, profile_ids=profile_ids)

    def cancel_jobs_for_row(self, db_cfg: Any, batch_id: str, profile_id: str, role: str, reason: str) -> int:
        """Cancel YouTube jobs for a batch row. Returns count cancelled."""
        from ...database.youtube_db import db_cancel_youtube_jobs_for_row
        return int(db_cancel_youtube_jobs_for_row(db_cfg, batch_id=batch_id, profile_id=profile_id, role=role, reason=reason) or 0)

    def force_job_pending(self, db_cfg: Any, job_uid: str, attempt_count: int = 0, error: str = "") -> int:
        """Force a YouTube upload job back to PENDING. Returns rows affected."""
        from ...database.youtube_db import db_force_youtube_upload_job_pending
        return int(db_force_youtube_upload_job_pending(db_cfg, job_uid, attempt_count=attempt_count, error=error) or 0)

    def get_account(self, db_cfg: Any, account_id: str) -> Any:
        """Get YouTube account record."""
        from ...database.youtube_db import db_get_youtube_account
        return db_get_youtube_account(db_cfg, account_id)

    # -- Upload core logic extracted from MainWindow._run_one_youtube_upload_job --

    def prepare_upload_context(
        self,
        job: dict,
        settings: dict,
    ) -> dict:
        """Prepare all context needed for a YouTube upload job.

        This bundles: MP4 validation, profile resolution, credential loading,
        metadata rendering, thumbnail resolution, collision detection, scope
        resolution, and upload-credentials extraction.

        Returns a dict with all prepared values needed for execution.

        Raises RuntimeError on missing prerequisites (MP4 not ready, no
        credentials, etc.) so the caller can catch and handle.
        """
        job_uid = str((job or {}).get("jobUid", "")).strip()
        existing_vid = str(job.get("youtubeVideoId", "")).strip()
        file_path0 = str(job.get("filePath", "")).strip()

        if not existing_vid:
            ok_mp4, reason = self.is_mp4_ready_for_upload(file_path0, deep=True)
            if not ok_mp4:
                raise _Mp4NotReadyError(str(reason or "MP4 is not ready yet"))

        attempt_no = int(job.get("attemptCount", 0) or 0) + 1
        pid = str(job.get("profileId", "")).strip()
        role = str(job.get("role", "")).strip()
        batch_id = str(job.get("batchId", "")).strip()
        file_path = str(job.get("filePath", "")).strip()
        existing_video_id = str(job.get("youtubeVideoId", "")).strip()
        existing_url = str(job.get("youtubeUrl", "")).strip()
        prev_err = str(job.get("error", "")).strip()

        profile = self.resolve_profile_for_upload(pid, self.host.db_cfg)
        refresh_token, client_id, client_secret = self.get_upload_credentials(pid, profile, settings)
        meta = self.render_upload_metadata(profile, batch_id, role)
        thumb_path = self.resolve_thumbnail_path(batch_id, role, file_path)
        scopes = self.resolve_scopes(settings.get("scopes", "") or (str(getattr(profile.get("scopes", "") if isinstance(profile, dict) else "", "")).strip()))

        collision = ""
        if not existing_video_id:
            collision = self.detect_same_day_collision(self.host.db_cfg, batch_id, pid, job_uid)

        acc = None
        try:
            from .db import db_get_youtube_account
            acc = db_get_youtube_account(self.host.db_cfg, pid)
        except Exception:
            acc = None
        scopes = self.resolve_scopes(str(getattr(acc, "scopes", "") or "").strip() if acc else "")

        return {
            "job_uid": job_uid,
            "attempt_no": attempt_no,
            "pid": pid,
            "role": role,
            "batch_id": batch_id,
            "file_path": file_path,
            "existing_video_id": existing_video_id,
            "existing_url": existing_url,
            "prev_err": prev_err,
            "profile": profile,
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
            "meta": meta,
            "thumb_path": thumb_path,
            "scopes": scopes,
            "collision": collision,
        }

    def execute_job_upload(
        self,
        ctx: dict,
        on_progress: Callable[[float], None] | None,
        cancel_event: Any,
        chunk_size_mb: int = 256,
    ) -> dict:
        """Execute the actual YouTube upload (new or existing-video retry).

        Args:
            ctx: Context dict from prepare_upload_context().
            on_progress: Progress callback.
            cancel_event: threading.Event for cancellation.
            chunk_size_mb: Resumable upload chunk size in MB.

        Returns dict with keys:
            video_id, url, warnings, thumb_err, playlist_err, processing_status
        """
        meta = ctx["meta"]
        if ctx["existing_video_id"]:
            result = self.retry_existing_video_upload(
                video_id=ctx["existing_video_id"],
                thumb_path=ctx["thumb_path"],
                playlist_id=meta.get("playlistId", ""),
                prev_err=ctx["prev_err"],
                existing_url=ctx["existing_url"],
                client_id=ctx["client_id"],
                client_secret=ctx["client_secret"],
                refresh_token=ctx["refresh_token"],
                scopes=ctx["scopes"],
                cancel_event=cancel_event,
            )
            return {
                "video_id": result["video_id"],
                "url": result["url"],
                "warnings": result["warnings"],
                "thumb_err": result["thumb_err"],
                "playlist_err": result["playlist_err"],
                "processing_status": None,
            }

        uploaded_video_id, res = self.execute_upload(
            mp4_path=ctx["file_path"],
            title=meta["title"],
            description=meta["description"],
            tags=meta["tags"],
            privacy_status=meta["privacy"],
            thumbnail_path=ctx["thumb_path"],
            playlist_id=meta.get("playlistId", ""),
            client_id=ctx["client_id"],
            client_secret=ctx["client_secret"],
            refresh_token=ctx["refresh_token"],
            scopes=ctx["scopes"],
            category_id=meta.get("categoryId", ""),
            made_for_kids=meta.get("madeForKids", False),
            contains_synthetic_media=meta.get("containsSynth", False),
            publish_at=meta.get("publishAt", ""),
            on_progress=on_progress,
            cancel_event=cancel_event,
            chunk_size_mb=chunk_size_mb,
        )

        proc = self.get_processing_status(
            video_id=res.video_id,
            client_id=ctx["client_id"],
            client_secret=ctx["client_secret"],
            refresh_token=ctx["refresh_token"],
            scopes=ctx["scopes"],
        )

        thumb_err = str(getattr(res, "thumbnail_error", "") or "").strip()
        pl_err = str(getattr(res, "playlist_error", "") or "").strip()
        warn = self.build_upload_warnings(
            thumbnail_error=thumb_err,
            playlist_error=pl_err,
            processing_status=getattr(proc, "processing_status", "") or "" if proc is not None else "",
            upload_status=getattr(proc, "upload_status", "") or "" if proc is not None else "",
        )

        return {
            "video_id": str(getattr(res, "video_id", "") or "").strip(),
            "url": str(getattr(res, "url", "") or "").strip(),
            "warnings": warn,
            "thumb_err": thumb_err,
            "playlist_err": pl_err,
            "processing_status": proc,
        }


class _Mp4NotReadyError(Exception):
    """Raised when the MP4 file is not ready for upload (non-transient)."""
    pass
