"""MusicGenerationCoordinator — orchestrates music generation domain logic.

This coordinator absorbs responsibilities from controllers/music_controller.py
and MainWindow music-domain methods, providing a single orchestration home for
all music generation workflows with constructor-injected dependencies.
"""

from __future__ import annotations

import re
import time
import threading
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Protocol

from ..ports import DeferCallFn, EventBusPort, LoggerPort, WarningFn
from ...services.api_errors import InsufficientCreditsError, LicenseExpiredError

if TYPE_CHECKING:
    from python_app.services.generation_proxy import GenerationProxy

from ...database.persistence import DbCfg, db_delete_profile, db_delete_saved_text, db_upsert_profile, db_upsert_saved_text
from ...models.music_model import create_id, now_iso
from ...services.music_generation import (
    generate_song_draft,
    generate_title_album_with_deepseek,
    generate_title_album_with_slai,
    inject_opening,
)
from ...database.music_db import (
    upsert_song,
    insert_history as music_insert_history,
    get_avoid_lists,
    get_pooled,
    get_suno_task_by_request_hash,
    get_batch_run_dirs_by_batch_id,
    get_latest_suno_output_dirs_by_batch_id,
    upsert_batch_run_dirs,
)
from ...services.music_suno import (
    build_suno_output_paths,
    download_to_file,
    hash_suno_generate_request,
    plan_next_paired_run_dirs_by_label,
    plan_next_run_dir,
    suno_api_generate,
    suno_api_try_get_tracks,
)


# ---------------------------------------------------------------------------
# Port protocols specific to the music domain
# ---------------------------------------------------------------------------


class MusicDbPort(Protocol):
    """Database interface for music domain operations."""

    def list_songs(self, db_cfg: Any, **filters: Any) -> list[dict]: ...

    def save_generation_batch(self, db_cfg: Any, batch: dict) -> dict: ...

    def update_song_status(self, db_cfg: Any, song_id: str, status: str) -> None: ...


class MusicServicePort(Protocol):
    """External music service interface (Suno API)."""

    def submit_to_suno(self, payload: dict) -> dict: ...

    def check_credits(self, api_key: str) -> dict: ...


class MusicHostPort(Protocol):
    """Protocol interface capturing what MusicGenerationCoordinator needs from its host.

    This replaces the direct MainWindow reference with a narrow interface,
    enabling instantiation with mock objects for testing.
    """

    music_data: dict
    bus: Any

    def _music_settings(self) -> dict: ...
    def _music_collection(self, kind: str) -> list[dict]: ...
    def _music_active_ids(self, kind: str) -> list[str]: ...
    def _music_profiles(self) -> list[dict]: ...
    def _music_db_cfg_from_forms(self) -> Any: ...
    def _music_profile_by_id(self, profile_id: str) -> dict | None: ...
    def _apply_settings_patch_to_database(self, patch: dict) -> dict: ...
    def _reload_music_db_collections(self) -> None: ...
    def _set_music_status(self, msg: str) -> None: ...
    def _set_music_suno_status(self, msg: str) -> None: ...
    def _set_music_settings_status(self, msg: str) -> None: ...
    def _resolve_music_suno_dirs(self, song: dict, *, create_missing: bool = False) -> dict: ...
    def _get_suno_remaining_credits_fresh(self, *, max_age_sec: float = 30.0) -> int: ...
    def _refresh_music_runtime_controls(self, settings: dict) -> None: ...
    def _refresh_music_editor_state(self, settings: dict) -> None: ...
    def _persist_music_runtime_state(self) -> None: ...
    def _refresh_music_history_table(self) -> None: ...


# ---------------------------------------------------------------------------
# Coordinator
# ---------------------------------------------------------------------------


class MusicGenerationCoordinator:
    """Coordinates music generation workflows via injected dependencies.

    All dependencies are validated at construction time; passing None for any
    required dependency raises ValueError.
    """

    def __init__(
        self,
        db: MusicDbPort,
        service: MusicServicePort,
        bus: EventBusPort,
        settings_accessor: Callable[[], dict],
        db_cfg_accessor: Callable[[], Any],
        logger: LoggerPort | None = None,
        *,
        db_cfg: DbCfg | None = None,
        generation_proxy: GenerationProxy | None = None,
        poll_pending_suno: Any = None,
        list_pending_suno_tasks: Any = None,
        upsert_suno_task: Any = None,
        list_songs_by_batch_id: Any = None,
        ui_delegate: MusicHostPort | None = None,
        warning_fn: WarningFn | None = None,
        defer_call_fn: DeferCallFn | None = None,
    ) -> None:
        if db is None:
            raise ValueError("MusicGenerationCoordinator requires a non-None db dependency")
        if service is None:
            raise ValueError("MusicGenerationCoordinator requires a non-None service dependency")
        if bus is None:
            raise ValueError("MusicGenerationCoordinator requires a non-None bus dependency")
        if settings_accessor is None:
            raise ValueError("MusicGenerationCoordinator requires a non-None settings_accessor dependency")
        if db_cfg_accessor is None:
            raise ValueError("MusicGenerationCoordinator requires a non-None db_cfg_accessor dependency")

        self._db = db
        self._service = service
        self._bus = bus
        self._settings_accessor = settings_accessor
        self._db_cfg_accessor = db_cfg_accessor
        self._db_cfg = db_cfg
        self._logger = logger
        self._generation_proxy = generation_proxy

        # Carried-over collaborators from old MusicController
        self._poll_pending_suno = poll_pending_suno
        self._list_pending_suno_tasks = list_pending_suno_tasks
        self._upsert_suno_task = upsert_suno_task
        self._list_songs_by_batch_id = list_songs_by_batch_id

        # UI delegate — typed protocol interface (replaces old host: MainWindow)
        self._host = ui_delegate

        # UI interaction callables (PyQt6-free)
        self._warning_fn: WarningFn = warning_fn or (lambda _title, _msg: None)
        self._defer_call_fn: DeferCallFn = defer_call_fn or (lambda _ms, _cb: None)

        # Coordinator-owned state — delegates to host.music_data during migration
        # (Phase 5+ will fully own this data; for now reads from host)

    def update_db_cfg(self, cfg: DbCfg | None) -> None:
        """Update the database configuration after a reconnection."""
        self._db_cfg = cfg

    @property
    def _music_data(self) -> dict:
        """Proxy to the host's music_data until full migration is done."""
        if self._host is not None and hasattr(self._host, "music_data"):
            return self._host.music_data
        return {}

    # ------------------------------------------------------------------
    # Methods absorbed from controllers/music_controller.py
    # ------------------------------------------------------------------

    def prepare_suno_submission(self, song: dict, settings: dict, *, auto: bool, resolve_dirs: Any, get_remaining_credits: Any) -> dict:
        """Prepare all data needed for a Suno submission.

        Returns a dict with:
          - 'ok': whether submission can proceed
          - 'skip_message': if skipped (auto mode)
          - 'warning_message': if skipped (manual mode)
          - 'request_hash', 'cached', 'dirs', 'model', 'prompt', 'title',
            'style', 'track_no', 'output_dir_ok', 'output_dir_alt', 'song_id'
        """
        host = self._host
        song_id = str((song or {}).get("id", "")).strip()
        if not song_id:
            if not auto:
                return {"ok": False, "warning_message": "Select a generated song first."}
            return {"ok": False, "skip_message": "Auto-GSuno skipped: no song selected"}
        if not self._db_cfg_accessor():
            if auto:
                return {"ok": False, "skip_message": "Auto-GSuno skipped: Postgres database is not configured"}
            return {"ok": False, "warning_message": "Postgres database is not configured. Set Database settings and run Migrate."}

        try:
            remaining = int(get_remaining_credits(max_age_sec=30.0))
        except Exception as exc:
            if auto:
                return {"ok": False, "skip_message": f"Auto-GSuno skipped: Suno credits check failed: {exc}"}
            return {"ok": False, "warning_message": f"Cannot check Suno credits:\n{exc}"}

        reserve = max(0, int(settings.get("sunoCreditsReserve", 10) or 0))
        cost_music = max(0, int(settings.get("sunoCreditsCostMusic", 5) or 0))
        required = int(cost_music) + int(reserve)
        if remaining < required:
            msg = f"Not enough Suno credits.\n\nRemaining: {remaining}\nRequired: {required} (music cost {cost_music} + reserve {reserve})"
            if auto:
                return {"ok": False, "skip_message": f"Auto-GSuno skipped: not enough credits ({remaining})"}
            return {"ok": False, "warning_message": msg}

        output_dir = str(settings.get("sunoOutputDir", "")).strip() or str(settings.get("downloadsDir", "")).strip()
        if not output_dir:
            if auto:
                return {"ok": False, "skip_message": "Auto-GSuno skipped: output directory is missing (set Downloads dir in Paths)"}
            return {"ok": False, "warning_message": "Output directory is missing. Set Downloads dir in Settings → Paths."}

        dirs = resolve_dirs(song, create_missing=True)
        prompt = str(song.get("lyricsPolished", "") or song.get("lyricsRaw", "")).strip()
        if not prompt:
            return {"ok": False, "warning_message": "Selected song has no lyrics to submit to Suno.", "error": True}

        model = "V5" if str(settings.get("sunoDefaultVersion", "v5.5")).strip().lower() == "v5" else "V5_5"
        db_cfg = self._db_cfg_accessor()
        request_hash = hash_suno_generate_request(
            model=model,
            title=str(song.get("title", "")).strip(),
            prompt=prompt,
            style=str(song.get("songDescription", "")).strip(),
            instrumental=False,
        )
        cached = get_suno_task_by_request_hash(db_cfg, request_hash) if db_cfg else None
        output_dir_ok = str(dirs.get("okDir", "")).strip()
        output_dir_alt = str(dirs.get("altDir", "")).strip() or output_dir_ok
        _batch_idx = song.get("batchIndex")
        track_no = int(_batch_idx) if isinstance(_batch_idx, int) else None

        return {
            "ok": True,
            "song_id": song_id,
            "request_hash": request_hash,
            "cached": cached,
            "dirs": dirs,
            "model": model,
            "prompt": prompt,
            "title": str(song.get("title", "")).strip(),
            "style": str(song.get("songDescription", "")).strip(),
            "track_no": track_no,
            "output_dir_ok": output_dir_ok,
            "output_dir_alt": output_dir_alt,
            "callback_url": str(settings.get("sunoCallbackUrl", "")).strip() or "https://api.example.com/callback",
            "batch_id": str(song.get("batchId", "")).strip(),
            "song_title": str(song.get("title", "")).strip(),
            "auto": auto,
        }

    def execute_suno_api_call(self, payload: dict, rate_lock: threading.Lock, rate_times: deque) -> dict:
        """Execute the Suno API call with rate limiting.

        Returns a dict with:
          - 'task_id': the Suno task ID
          - 'api_called': whether a new API call was made
          - 'used_cached': whether cached result was used
        """
        cached = payload.get("cached")
        task_id = str((cached or {}).get("taskId", "")).strip()

        if not task_id:
            while True:
                sleep_sec = 0.0
                with rate_lock:
                    now = time.monotonic()
                    while rate_times and (now - float(rate_times[0])) >= 10.0:
                        rate_times.popleft()
                    if len(rate_times) >= 20:
                        oldest = float(rate_times[0])
                        sleep_sec = max(0.05, 10.0 - (now - oldest))
                    else:
                        rate_times.append(now)
                        sleep_sec = 0.0
                if sleep_sec <= 0:
                    break
                time.sleep(float(sleep_sec))

            generated = suno_api_generate(
                generation_proxy=self._generation_proxy,
                model=payload["model"],
                title=payload["title"],
                lyrics=payload["prompt"],
                style=payload["style"],
                instrumental=False,
            )
            task_id = str(generated.get("taskId", "")).strip()

        return {"task_id": task_id, "api_called": True, "used_cached": False}

    def process_suno_result(self, payload: dict, task_id: str) -> dict:
        """Poll Suno API for track results and download if available.

        Returns a dict with:
          - 'downloaded': whether tracks were downloaded
          - 'submitted': whether submission is pending callback
          - 'message': status message for UI
          - 'schedule_poll': whether to schedule auto-poll
        """
        db_cfg = self._db_cfg_accessor()
        result = suno_api_try_get_tracks(self._generation_proxy, task_id)
        audio_urls = list(result.get("audioUrls") or [])

        if len(audio_urls) >= 2:
            ok_url = str(audio_urls[0] or "").strip()
            alt_url = str(audio_urls[1] or "").strip()
            track_no = payload.get("track_no")
            title = payload["title"]
            output_dir_ok = payload["output_dir_ok"]
            output_dir_alt = payload["output_dir_alt"]

            self._upsert_suno_task(
                db_cfg,
                {
                    "requestHash": payload["request_hash"],
                    "songUid": payload["song_id"],
                    "batchId": payload["batch_id"],
                    "trackNo": track_no,
                    "model": payload["model"],
                    "title": title,
                    "style": payload["style"],
                    "instrumental": False,
                    "taskId": task_id,
                    "status": str(result.get("status", "SUCCESS")).strip() or "SUCCESS",
                    "audioUrlOk": ok_url,
                    "audioUrlAlt": alt_url,
                    "outputDirOk": output_dir_ok,
                    "outputDirAlt": output_dir_alt,
                    "outputDir": output_dir_ok,
                },
            )

            paths_ok = build_suno_output_paths(output_dir=output_dir_ok, title=title, track_no=track_no)
            paths_alt = build_suno_output_paths(output_dir=output_dir_alt, title=title, track_no=track_no)

            if ok_url and not Path(paths_ok["ok"]).exists():
                download_to_file(ok_url, paths_ok["ok"])
            if alt_url and not Path(paths_alt["alt"]).exists():
                download_to_file(alt_url, paths_alt["alt"])

            return {
                "downloaded": True,
                "submitted": False,
                "message": f"Suno: downloaded {title}",
                "schedule_poll": False,
            }

        submitted_message = "Suno: auto-submitted" if payload.get("auto", False) else "Suno: submitted"
        return {
            "downloaded": False,
            "submitted": True,
            "message": f"{submitted_message} {payload['title']}",
            "schedule_poll": payload.get("auto", False),
        }

    def submit_song_to_suno(self, song: dict, settings: dict, *, auto: bool) -> None:
        """Full submission orchestration.

        This is the controller-level method that coordinates prepare -> execute -> process.
        The caller (main_window) handles status display and thread spawning.
        """
        host = self._host
        db_cfg = self._db_cfg_accessor()

        prep = self.prepare_suno_submission(
            song,
            settings,
            auto=auto,
            resolve_dirs=host._resolve_music_suno_dirs,
            get_remaining_credits=host._get_suno_remaining_credits_fresh,
        )
        if not prep["ok"]:
            skip_msg = prep.get("skip_message") or prep.get("warning_message") or "unknown reason"
            if self._logger:
                self._logger.error(f"[{time.strftime('%H:%M:%S')}] Suno submission blocked: {skip_msg}")
            if prep.get("skip_message"):
                host._set_music_suno_status(prep["skip_message"])
            if prep.get("warning_message") and not auto:
                self._warning_fn("Suno", prep["warning_message"])
            elif prep.get("warning_message"):
                if prep.get("skip_message"):
                    host._set_music_status(prep["skip_message"].replace("Auto-GSuno skipped: ", ""))
            return

        if prep.get("error"):
            host.bus.music_event.emit({"type": "suno_result", "message": f"Suno failed: {prep.get('warning_message', 'unknown error')}"})
            return

        title = prep["song_title"]
        mode_label = "auto-submitting" if auto else "submitting"
        host._set_music_suno_status(f"Suno: {mode_label} {title}...")
        host._set_music_status(f"Suno: {mode_label} {title}...")

        # Check for cached result with both URLs available
        cached_ok_url = str((prep.get("cached") or {}).get("audioUrlOk") or "").strip()
        cached_alt_url = str((prep.get("cached") or {}).get("audioUrlAlt") or "").strip()
        if prep.get("cached") and cached_ok_url and cached_alt_url:
            paths_ok = build_suno_output_paths(output_dir=prep["output_dir_ok"], title=title, track_no=prep["track_no"])
            paths_alt = build_suno_output_paths(output_dir=prep["output_dir_alt"], title=title, track_no=prep["track_no"])
            if not Path(paths_ok["ok"]).exists():
                download_to_file(cached_ok_url, paths_ok["ok"])
            if not Path(paths_alt["alt"]).exists():
                download_to_file(cached_alt_url, paths_alt["alt"])
            host.bus.music_event.emit(
                {
                    "type": "suno_result",
                    "message": f"Suno: downloaded cached {title}",
                }
            )
            return

        # Execute API call
        try:
            call_result = self.execute_suno_api_call(prep, host._suno_rate_lock, host._suno_generate_times)
        except InsufficientCreditsError as exc:
            msg = f"Suno submission failed: insufficient credits"
            if self._logger:
                self._logger.error(f"[{time.strftime('%H:%M:%S')}] {msg}: {exc}")
            host._set_music_suno_status(msg)
            host._set_music_status(msg)
            host.bus.music_event.emit({"type": "suno_result", "message": msg})
            return
        except LicenseExpiredError as exc:
            msg = f"Suno submission failed: license expired"
            if self._logger:
                self._logger.error(f"[{time.strftime('%H:%M:%S')}] {msg}: {exc}")
            host._set_music_suno_status(msg)
            host._set_music_status(msg)
            host.bus.music_event.emit({"type": "suno_result", "message": msg})
            return
        task_id = call_result["task_id"]

        # Upsert task record
        self._upsert_suno_task(
            db_cfg,
            {
                "requestHash": prep["request_hash"],
                "songUid": prep["song_id"],
                "batchId": prep["batch_id"],
                "trackNo": prep["track_no"],
                "model": prep["model"],
                "title": title,
                "style": prep["style"],
                "instrumental": False,
                "taskId": task_id,
                "status": "PENDING",
                "outputDirOk": prep["output_dir_ok"],
                "outputDirAlt": prep["output_dir_alt"],
                "outputDir": prep["output_dir_ok"],
            },
        )
        music_insert_history(
            db_cfg,
            kind="suno_retry",
            message=f"Suno retry submitted: {title}",
            song_uid=prep["song_id"],
        )

        # Process result
        process_result = self.process_suno_result(prep, task_id)
        host.bus.music_event.emit({"type": "suno_result", "message": process_result["message"]})

        if process_result["schedule_poll"]:
            host._music_suno_auto_poll_enabled = True
            if self._logger:
                self._logger.info(f"[{time.strftime('%H:%M:%S')}] Suno: scheduling auto-poll (task_id={task_id})")
            host.bus.music_event.emit({"type": "suno_schedule_poll", "delayMs": 3000, "maxTasks": 10})
        elif self._logger:
            self._logger.info(f"[{time.strftime('%H:%M:%S')}] Suno: downloaded immediately (task_id={task_id})")

        # For auto submissions, the suno_schedule_poll event handles polling.
        # For manual submissions, trigger an immediate poll.
        if not auto:
            host.bus.music_event.emit({"type": "suno_schedule_poll", "delayMs": 0, "maxTasks": 10})

    def update_settings(self, patch: dict) -> None:
        """Apply a settings patch and refresh UI controls."""
        if not patch:
            return
        host = self._host
        settings = host._apply_settings_patch_to_database(patch)
        host._music_ui_loading = True
        try:
            host._refresh_music_runtime_controls(settings)
            host._refresh_music_editor_state(settings)
        finally:
            host._music_ui_loading = False

    def persist_date_filters(self, source: str = "run") -> None:
        """Persist current date filter values."""
        from ...views.helpers.widget_factory import calendar_picker_value

        host = self._host
        if host._music_ui_loading:
            return
        if str(source).strip().lower() == "history" and hasattr(host, "music_history_from_input"):
            host.music_history_from_date = calendar_picker_value(host.music_history_from_input)
            host.music_history_to_date = calendar_picker_value(host.music_history_to_input)
        else:
            host.music_run_from_date = calendar_picker_value(host.music_run_from_input)
            host.music_run_to_date = calendar_picker_value(host.music_run_to_input)
        host._persist_music_runtime_state()
        host._refresh_music_history_table()

    def create_profile(self, name: str) -> dict | None:
        """Create a new generation profile with the given name."""
        host = self._host
        db_cfg = self._db_cfg_accessor()
        if not db_cfg:
            host._set_music_settings_status("Profiles require Postgres configured via .env")
            return None
        folder_name = "-".join(name.lower().split()) or name.lower()
        row = {
            "id": create_id("profile"),
            "name": name,
            "folderName": folder_name,
            "runPrefix": "",
            "logoPath": "",
            "videoTemplateId": "",
            "reelTemplateId": "",
            "createdAt": now_iso(),
            "updatedAt": now_iso(),
        }
        row = db_upsert_profile(db_cfg, row)
        host._reload_music_db_collections()
        host._music_settings_selected_profile_id = str(row["id"])
        return row

    def save_profile(self, profile_id: str, updates: dict) -> dict | None:
        """Save updates to an existing profile."""
        host = self._host
        db_cfg = self._db_cfg_accessor()
        if not db_cfg:
            host._set_music_settings_status("Profiles require Postgres configured via .env")
            return None
        rows = host._music_profiles()
        target = None
        for row in rows:
            if str(row.get("id", "")).strip() == profile_id:
                target = row
                break
        if not target:
            return None
        updated = {**target, **updates, "updatedAt": now_iso()}
        updated = db_upsert_profile(db_cfg, updated)
        host._reload_music_db_collections()
        return updated

    def delete_profile(self, profile_id: str) -> bool:
        """Delete a profile by ID. Returns True if deleted."""
        host = self._host
        db_cfg = self._db_cfg_accessor()
        if not db_cfg:
            host._set_music_settings_status("Profiles require Postgres configured via .env")
            return False
        db_delete_profile(db_cfg, profile_id)
        host._reload_music_db_collections()
        rows = host._music_profiles()
        settings = host._music_settings()
        patch = {
            "channelOkProfileIds": [x for x in list(settings.get("channelOkProfileIds") or []) if str(x).strip() != profile_id],
            "channelAltProfileIds": [x for x in list(settings.get("channelAltProfileIds") or []) if str(x).strip() != profile_id],
            "activeProfileId": None if str(settings.get("activeProfileId") or "").strip() == profile_id else settings.get("activeProfileId"),
            "activeProfileOkId": None if str(settings.get("activeProfileOkId") or "").strip() == profile_id else settings.get("activeProfileOkId"),
            "activeProfileAltId": None if str(settings.get("activeProfileAltId") or "").strip() == profile_id else settings.get("activeProfileAltId"),
        }
        host._apply_settings_patch_to_database(patch)
        host._music_settings_selected_profile_id = str(rows[0].get("id", "")).strip() if rows else None
        return True

    # ------------------------------------------------------------------
    # Pool/saved-text management
    # ------------------------------------------------------------------

    def save_saved_text(
        self, kind: str, name: str, content: str, match_key: str, existing_id: str, existing_created_at: str
    ) -> tuple[dict, list[dict]]:
        """Save a named text entry and return (saved_item, updated_list)."""
        host = self._host
        db_cfg = self._db_cfg_accessor()
        if not db_cfg:
            raise RuntimeError("Postgres is not configured via .env")
        item = {
            "id": existing_id or create_id("desc" if str(kind).startswith("desc") else "struct"),
            "name": name,
            "content": content,
            "matchKey": match_key,
            "updatedAt": now_iso(),
            "createdAt": existing_created_at or now_iso(),
        }
        item = db_upsert_saved_text(db_cfg, kind, item)
        host._reload_music_db_collections()
        rows = list(host._music_collection(kind))
        return item, rows

    def delete_saved_text(self, kind: str, removed_id: str) -> list[dict]:
        """Delete a saved text entry and return the updated list."""
        host = self._host
        db_cfg = self._db_cfg_accessor()
        if not db_cfg:
            raise RuntimeError("Postgres is not configured via .env")
        db_delete_saved_text(db_cfg, kind, removed_id)
        settings_patch: dict[str, object] = {}
        if removed_id:
            if str(kind).strip().lower().startswith("desc"):
                active_ids = [x for x in host._music_active_ids(kind) if str(x).strip() != removed_id]
                enabled_ids = [str(x).strip() for x in list(host._music_settings().get("enabledDescriptionIds") or []) if str(x).strip() != removed_id]
                settings_patch = {
                    "activeDescriptionIds": active_ids,
                    "enabledDescriptionIds": enabled_ids,
                }
            else:
                active_ids = [x for x in host._music_active_ids(kind) if str(x).strip() != removed_id]
                enabled_ids = [str(x).strip() for x in list(host._music_settings().get("enabledStructureIds") or []) if str(x).strip() != removed_id]
                settings_patch = {
                    "activeStructureIds": active_ids,
                    "enabledStructureIds": enabled_ids,
                }
        if settings_patch:
            host._apply_settings_patch_to_database(settings_patch)
        host._reload_music_db_collections()
        return list(host._music_collection(kind))

    def generate_pool(self, kind: str, count: int) -> tuple[bool, str]:
        """Generate pool entries. Returns (success, message)."""
        host = self._host
        cfg = host._music_db_cfg_from_forms()
        if cfg is None:
            return False, "Configure Database settings first."
        try:
            from music_pools import music_generate_pool_rows
            result = music_generate_pool_rows(cfg, kind, count)
            return True, f"Generated {int(result.get('inserted', 0) or 0)} {kind}"
        except Exception as exc:
            return False, str(exc)

    def import_pool(self, kind: str, file_path: str) -> tuple[bool, str]:
        """Import pool entries from a file. Returns (success, message)."""
        host = self._host
        cfg = host._music_db_cfg_from_forms()
        if cfg is None:
            return False, "Configure Database settings first."
        try:
            from music_pools import music_import_openings, music_import_titles, music_import_albums, music_parse_openings_file, music_parse_text_file
            if kind == "openings":
                result = music_import_openings(cfg, music_parse_openings_file(file_path))
            elif kind == "titles":
                result = music_import_titles(cfg, music_parse_text_file(file_path))
            else:
                result = music_import_albums(cfg, music_parse_text_file(file_path))
            return True, f"Imported {int(result.get('inserted', 0) or 0)} {kind}"
        except Exception as exc:
            return False, str(exc)

    def clear_pool(self, kind: str) -> tuple[bool, str]:
        """Clear all entries in a pool. Returns (success, message)."""
        host = self._host
        cfg = host._music_db_cfg_from_forms()
        if cfg is None:
            return False, "Configure Database settings first."
        from music_pools import music_clear_pool
        result = music_clear_pool(cfg, kind)
        if bool(result.get("ok", False)):
            host._music_pools_page = 0
            host._music_pools_selected_id = ""
            return True, f"Cleared {kind}"
        return False, str(result.get("message", "Clear failed"))

    def load_pool_data(self, *, kind: str, page: int, page_size: int) -> dict:
        """Fetch pool rows from the database for a given kind and pagination.

        Pure data logic — no UI coupling.

        Returns a dict with:
          - 'rows': list[dict] – pool rows
          - 'kind': str – the pool kind ('openings', 'titles', or 'albums')
          - 'limit': int – resolved page size
          - 'offset': int – resolved offset
        """
        host = self._host
        cfg = host._music_db_cfg_from_forms()
        if cfg is None:
            return {"rows": [], "kind": kind, "limit": page_size, "offset": 0, "error": "Database not configured"}

        limit = max(10, min(500, int(page_size or 100)))
        offset = max(0, int(page or 0)) * limit

        from ...database.music_pools import list_pool as music_list_pool
        result = music_list_pool(cfg, kind, limit, offset)
        rows = list(result.get("rows") or [])

        return {"rows": rows, "kind": kind, "limit": limit, "offset": offset}

    def load_saved_texts(self, kind: str) -> dict:
        """Load saved text records for descriptions or structures.

        Returns a dict with:
          - 'rows': list[dict] – all text records
          - 'active_ids': list[str] – currently active IDs
          - 'kind_key': str – the canonical key ('descriptions' or 'structures')
        """
        host = self._host
        key = "descriptions" if str(kind).strip().lower().startswith("desc") else "structures"
        rows = self._music_data.get(key)
        rows = rows if isinstance(rows, list) else []

        settings = self._settings_accessor()
        active_key = "activeDescriptionIds" if key == "descriptions" else "activeStructureIds"
        active_ids = [str(x).strip() for x in (settings.get(active_key) or []) if str(x).strip()]

        return {
            "rows": rows,
            "active_ids": active_ids,
            "kind_key": key,
        }

    def load_profiles(self) -> dict:
        """Load profile records with metadata for UI rendering.

        Returns a dict with:
          - 'profiles': list[dict] – profiles with computed UI state fields
          - 'ok_selected_list': list[str] – ordered OK profile IDs
          - 'alt_selected_list': list[str] – ordered ALT profile IDs
        """
        host = self._host
        profiles = self._music_data.get("profiles") if isinstance(self._music_data.get("profiles"), list) else []
        settings = self._settings_accessor()
        ok_selected_list = [str(x).strip() for x in (settings.get("channelOkProfileIds") or []) if str(x).strip()]
        alt_selected_list = [str(x).strip() for x in (settings.get("channelAltProfileIds") or []) if str(x).strip()]
        ok_selected_set = set(ok_selected_list)
        alt_selected_set = set(alt_selected_list)

        result = []
        for profile in profiles or []:
            profile_id = str((profile or {}).get("id", "")).strip()
            base_name = str((profile or {}).get("name", "Unnamed Profile"))
            is_ok_checked = profile_id in ok_selected_set
            is_alt_checked = profile_id in alt_selected_set
            is_disabled_ok = profile_id in alt_selected_set and not is_ok_checked
            is_disabled_alt = profile_id in ok_selected_set and not is_alt_checked

            result.append({
                "id": profile_id,
                "name": base_name,
                "ok_checked": is_ok_checked,
                "alt_checked": is_alt_checked,
                "ok_disabled": is_disabled_ok,
                "alt_disabled": is_disabled_alt,
                "ok_index": ok_selected_list.index(profile_id) if is_ok_checked else -1,
                "alt_index": alt_selected_list.index(profile_id) if is_alt_checked else -1,
            })

        return {
            "profiles": result,
            "ok_selected_list": ok_selected_list,
            "alt_selected_list": alt_selected_list,
        }

    def generate_music_batch(self, request: dict) -> None:
        """Orchestrate batch music generation for multiple songs."""
        host = self._host
        db_cfg = self._db_cfg_accessor()
        total = int(request.get("total", 0) or 0)
        completed = 0
        failed = 0
        settings = dict(request.get("settings") or {})
        try:
            worker_limit = int(settings.get("perfMusicWorkers", 1) or 1)
        except Exception:
            worker_limit = 1
        worker_limit = max(1, min(5, worker_limit))
        title_album_provider = str(settings.get("titleAlbumProvider") or settings.get("songDraftProvider") or request.get("provider", "deepseek")).strip() or "deepseek"
        lyrics_provider = str(settings.get("lyricsProvider") or title_album_provider).strip() or title_album_provider
        profiles_by_id = {str((row or {}).get("id", "")).strip(): dict(row) for row in (self._music_data.get("profiles") or []) if isinstance(row, dict)}
        try:
            date_list = list(request.get("date_list") or [])
            ok_ids = list(request.get("ok_ids") or [])
            alt_ids = list(request.get("alt_ids") or [])
            batch_tasks: list[tuple[str, int, str, str]] = []
            for ymd in date_list:
                for pair_index, profile_ok_id in enumerate(ok_ids):
                    profile_alt_id = alt_ids[pair_index] if pair_index < len(alt_ids) else ""
                    batch_tasks.append((str(ymd).strip(), int(pair_index), str(profile_ok_id).strip(), str(profile_alt_id).strip()))
            lock = threading.Lock()
            counter = {"completed": 0, "failed": 0}

            def run_one_batch(ymd: str, pair_index: int, profile_ok_id: str, profile_alt_id: str) -> None:
                nonlocal title_album_provider, lyrics_provider, settings, profiles_by_id, total
                if host._music_cancel_requested:
                    raise InterruptedError("Music generation cancelled")
                batch_id = f"batch-{ymd}-{pair_index + 1}-{int(time.time() * 1000)}"
                songs_per_batch = max(1, int(request.get("songs_per_batch", 1) or 1))
                pool_pick_max_attempts = int(settings.get("poolPickMaxAttempts", 5) or 5)
                pool_pick_max_attempts = max(1, min(20, pool_pick_max_attempts))
                raw_extra = settings.get("batchMaxExtraAttempts", None)
                if raw_extra is None:
                    raw_extra = songs_per_batch * 2
                batch_max_extra_attempts = int(raw_extra)
                batch_max_extra_attempts = max(0, min(500, batch_max_extra_attempts))
                batch_attempt_budget = songs_per_batch + batch_max_extra_attempts
                batch_attempts = 0
                song_index = 0
                batch_forced_album = ""
                while song_index < songs_per_batch:
                    if host._music_cancel_requested:
                        raise InterruptedError("Music generation cancelled")
                    if batch_attempts >= batch_attempt_budget:
                        raise RuntimeError(f"Batch generation retry budget exhausted (target={songs_per_batch}, attempts={batch_attempts})")
                    batch_attempts += 1
                    selected = self.resolve_generation_inputs(song_index)
                    history_window = int(settings.get("uniquenessHistoryWindow", 100) or 100)
                    avoid = get_avoid_lists(db_cfg, history_window) if db_cfg else host._music_recent_uniqueness_lists(history_window)
                    host.bus.music_event.emit(
                        {
                            "type": "status",
                            "message": f"Generating batch {batch_id}: {song_index + 1}/{songs_per_batch} (attempt {batch_attempts}/{batch_attempt_budget})",
                        }
                    )
                    seed_title = ""
                    seed_album = ""
                    forced_opening = ""
                    try:
                        if db_cfg:
                            last_pool_exc: Exception | None = None
                            for pool_attempt in range(1, pool_pick_max_attempts + 1):
                                pooled = get_pooled(
                                    db_cfg,
                                    opening=bool(settings.get("uniqueOpening", False)),
                                    title=True,
                                    album=True,
                                )
                                seed_title = str(pooled.get("title", "") or "").strip()
                                seed_album = str(pooled.get("album", "") or "").strip()
                                picked_opening = pooled.get("opening") if isinstance(pooled.get("opening"), dict) else None
                                try:
                                    if not seed_title:
                                        raise RuntimeError("Title pool is empty. Seed Postgres table title_pool.")
                                    if not seed_album:
                                        raise RuntimeError("Album pool is empty. Seed Postgres table album_pool.")
                                    if bool(settings.get("uniqueOpening", False)):
                                        line1 = str((picked_opening or {}).get("line1", "")).strip()
                                        line2 = str((picked_opening or {}).get("line2", "")).strip()
                                        if not line1 or not line2:
                                            raise RuntimeError("Opening pool is empty. Seed Postgres table opening_pairs.")
                                        forced_opening = f"{line1}\n{line2}"
                                    last_pool_exc = None
                                    break
                                except Exception as exc:
                                    last_pool_exc = exc if isinstance(exc, Exception) else RuntimeError(str(exc))
                                    if self._logger:
                                        self._logger.error(
                                            f"[{time.strftime('%H:%M:%S')}] Music pool pick failed: batch={batch_id} item={song_index + 1} pool_attempt={pool_attempt}/{pool_pick_max_attempts} error={last_pool_exc}"
                                        )
                                    time.sleep(0.05 * pool_attempt)
                            if last_pool_exc is not None:
                                raise last_pool_exc
                    except Exception as exc:
                        raise RuntimeError(f"Pool selection failed for batch {batch_id}: {exc}") from exc
                    last_error: Exception | None = None
                    draft: dict[str, str] | None = None
                    title_album: dict[str, str] | None = None
                    title_timeout_sec = int(settings.get("titleAlbumTimeoutSec", 30) or 30)
                    title_timeout_sec = max(10, min(120, title_timeout_sec))
                    title_max_attempts = int(settings.get("titleAlbumMaxAttempts", 6) or 6)
                    title_max_attempts = max(1, min(20, title_max_attempts))
                    draft_timeout_sec = int(settings.get("songDraftTimeoutSec", 30) or 30)
                    draft_timeout_sec = max(10, min(120, draft_timeout_sec))
                    draft_max_attempts = int(settings.get("songDraftMaxAttempts", 8) or 8)
                    draft_max_attempts = max(1, min(20, draft_max_attempts))

                    _log = self._logger.info if self._logger else (lambda msg: None)

                    for attempt in range(1, draft_max_attempts + 1):
                        try:
                            if host._music_cancel_requested:
                                raise InterruptedError("Music generation cancelled")
                            _log(
                                f"[{time.strftime('%H:%M:%S')}] Music generate attempt: title_album_provider={title_album_provider} lyrics_provider={lyrics_provider} attempt={attempt} batch={batch_id} item={song_index + 1}"
                            )
                            if title_album_provider == "slai":
                                title_album = generate_title_album_with_slai(
                                    api_key="",  # Key managed by Platform API
                                    model=str(settings.get("slaiSongModel", "gpt-5.5")).strip() or "gpt-5.5",
                                    language=str(settings.get("language", "English")).strip() or "English",
                                    creativity=int(settings.get("creativity", 55) or 55),
                                    description=selected["description"],
                                    structure=selected["structure"],
                                    seed_title=seed_title,
                                    seed_album=batch_forced_album or seed_album,
                                    forced_album=batch_forced_album,
                                    avoid_titles=avoid["titles"],
                                    avoid_albums=avoid["albums"],
                                    strict_level=int(settings.get("strictLevel", 3) or 3),
                                    timeout_sec=title_timeout_sec,
                                    max_attempts=title_max_attempts,
                                    should_cancel=lambda: bool(host._music_cancel_requested),
                                    on_log=_log,
                                )
                            else:
                                title_album = generate_title_album_with_deepseek(
                                    api_key="",  # Key managed by Platform API
                                    language=str(settings.get("language", "English")).strip() or "English",
                                    creativity=int(settings.get("creativity", 55) or 55),
                                    description=selected["description"],
                                    structure=selected["structure"],
                                    seed_title=seed_title,
                                    seed_album=batch_forced_album or seed_album,
                                    forced_album=batch_forced_album,
                                    avoid_titles=avoid["titles"],
                                    avoid_albums=avoid["albums"],
                                    strict_level=int(settings.get("strictLevel", 3) or 3),
                                    timeout_sec=title_timeout_sec,
                                    max_attempts=title_max_attempts,
                                    should_cancel=lambda: bool(host._music_cancel_requested),
                                    on_log=_log,
                                )

                            title = str((title_album or {}).get("title", "")).strip()
                            album = str((title_album or {}).get("album", "")).strip()
                            if not title or not album:
                                raise RuntimeError("Title/Album generation returned empty values")
                            if not batch_forced_album:
                                batch_forced_album = album
                            else:
                                album = batch_forced_album

                            if lyrics_provider == "suno":
                                from ...services.suno_lyrics import generate_lyrics_blocking

                                callback_url = str(settings.get("sunoCallbackUrl", "")).strip()
                                api_base_url = str(settings.get("sunoApiBaseUrl", "https://api.sunoapi.org")).strip() or "https://api.sunoapi.org"
                                if not callback_url:
                                    raise RuntimeError("Suno callback URL missing (Settings \u2192 Suno). Start ngrok or set callback URL.")
                                headers = " ".join([x.strip() for x in str(selected.get("structure", "")).splitlines() if x.strip().startswith("[")][:8])
                                raw_prompt = f"{title}. {selected.get('description', '')} {headers}".strip()
                                prompt = raw_prompt[:200]
                                lyrics_raw, _title2 = generate_lyrics_blocking(
                                    api_base_url=api_base_url,
                                    api_key="",  # Key managed by Platform API
                                    prompt=prompt,
                                    callback_url=callback_url,
                                    timeout_sec=30,
                                    poll_timeout_sec=30,
                                    max_wait_sec=180,
                                    poll_interval_sec=2.0,
                                )
                                if bool(settings.get("uniqueOpening", False)) and forced_opening:
                                    lyrics_raw = inject_opening(lyrics_raw, forced_opening)
                                draft = {"title": title, "album": album, "lyricsRaw": lyrics_raw}
                            elif lyrics_provider == "slai":
                                draft = generate_song_draft(
                                    generation_proxy=self._generation_proxy,
                                    language=str(settings.get("language", "English")).strip() or "English",
                                    creativity=int(settings.get("creativity", 55) or 55),
                                    description=selected["description"],
                                    structure=selected["structure"],
                                    avoid_titles=avoid["titles"],
                                    avoid_albums=avoid["albums"],
                                    avoid_openings=avoid["openings"],
                                    forced_title=title,
                                    forced_album=album,
                                    forced_opening=forced_opening,
                                    should_cancel=lambda: bool(host._music_cancel_requested),
                                    on_log=_log,
                                )
                            else:
                                draft = generate_song_draft(
                                    generation_proxy=self._generation_proxy,
                                    language=str(settings.get("language", "English")).strip() or "English",
                                    creativity=int(settings.get("creativity", 55) or 55),
                                    description=selected["description"],
                                    structure=selected["structure"],
                                    avoid_titles=avoid["titles"],
                                    avoid_albums=avoid["albums"],
                                    avoid_openings=avoid["openings"],
                                    forced_title=title,
                                    forced_album=album,
                                    forced_opening=forced_opening,
                                    should_cancel=lambda: bool(host._music_cancel_requested),
                                    on_log=_log,
                                )
                            break
                        except Exception as exc:
                            if isinstance(exc, InterruptedError):
                                raise
                            # Credits/license errors are fatal — no retry
                            if isinstance(exc, (InsufficientCreditsError, LicenseExpiredError)):
                                raise
                            last_error = exc if isinstance(exc, Exception) else RuntimeError(str(exc))
                            low = str(last_error).lower()
                            if "suno lyrics forbidden" in low or "suno lyrics unauthorized" in low:
                                raise last_error
                            if self._logger:
                                self._logger.error(f"[{time.strftime('%H:%M:%S')}] Music generate attempt failed: attempt={attempt} error={last_error}")
                            time.sleep(0.1 * attempt)
                    if not draft:
                        continue

                    created_at = now_iso()
                    song_uid = create_id("song")
                    song = {
                        "id": song_uid,
                        "songUid": song_uid,
                        "title": str(draft.get("title", "")).strip(),
                        "album": str(draft.get("album", "")).strip(),
                        "lyricsRaw": str(draft.get("lyricsRaw", "")).strip(),
                        "lyricsPolished": str(draft.get("lyricsRaw", "")).strip(),
                        "lyrics_raw": str(draft.get("lyricsRaw", "")).strip(),
                        "lyrics_polished": str(draft.get("lyricsRaw", "")).strip(),
                        "batchIndex": song_index + 1,
                        "songDescriptionTitle": selected["descriptionTitle"],
                        "songStructureTitle": selected["structureTitle"],
                        "songDescription": selected["description"],
                        "songStructure": selected["structure"],
                        "song_description": selected["description"],
                        "song_structure": selected["structure"],
                        "profileOkId": profile_ok_id,
                        "profileAltId": profile_alt_id,
                        "profileOkName": str(profiles_by_id.get(profile_ok_id, {}).get("name", "")).strip(),
                        "profileAltName": str(profiles_by_id.get(profile_alt_id, {}).get("name", "")).strip(),
                        "language": str(settings.get("language", "English")).strip() or "English",
                        "creativity": int(settings.get("creativity", 55) or 55),
                        "batchId": batch_id,
                        "createdAt": created_at,
                        "runDate": str(ymd).strip(),
                        "status": "generated",
                    }
                    if db_cfg:
                        upsert_song(db_cfg, song)
                        music_insert_history(
                            db_cfg,
                            kind="song_generated",
                            message=f"{str(song.get('title', '')).strip()} / {str(song.get('album', '')).strip()}",
                            song_uid=str(song.get("songUid", "")).strip(),
                        )
                    with lock:
                        counter["completed"] = int(counter.get("completed", 0) or 0) + 1
                        c2 = int(counter.get("completed", 0) or 0)
                        f2 = int(counter.get("failed", 0) or 0)
                    host.bus.music_event.emit({"type": "song", "song": song, "completed": c2, "failed": f2, "total": total})
                    song_index += 1

            max_workers = max(1, min(int(worker_limit), len(batch_tasks) if batch_tasks else 1))
            cancelled = False
            first_error: Exception | None = None
            if batch_tasks:
                with ThreadPoolExecutor(max_workers=max_workers) as ex:
                    futures = [ex.submit(run_one_batch, *args) for args in batch_tasks]
                    for fut in as_completed(futures):
                        try:
                            fut.result()
                        except InterruptedError:
                            cancelled = True
                            break
                        except Exception as exc:
                            first_error = exc if isinstance(exc, Exception) else RuntimeError(str(exc))
                            break
            with lock:
                completed = int(counter.get("completed", 0) or 0)
                failed = int(counter.get("failed", 0) or 0)
            if first_error is not None:
                raise first_error
            if cancelled:
                raise InterruptedError("Music generation cancelled")

            host.bus.music_event.emit(
                {
                    "type": "done",
                    "completed": completed,
                    "failed": failed,
                    "total": total,
                    "cancelled": False,
                }
            )
        except InterruptedError:
            host.bus.music_event.emit(
                {
                    "type": "done",
                    "completed": completed,
                    "failed": failed,
                    "total": total,
                    "cancelled": True,
                }
            )
        except (InsufficientCreditsError, LicenseExpiredError) as exc:
            if self._logger:
                self._logger.error(f"[{time.strftime('%H:%M:%S')}] Music generation blocked: {exc}")
            host.bus.music_event.emit(
                {
                    "type": "done",
                    "completed": completed,
                    "failed": failed + 1,
                    "total": total,
                    "cancelled": False,
                    "error": str(exc),
                }
            )
        except Exception as exc:
            if self._logger:
                self._logger.error(f"[{time.strftime('%H:%M:%S')}] Music generation fatal error: {exc}")
            host.bus.music_event.emit(
                {
                    "type": "done",
                    "completed": completed,
                    "failed": failed + 1,
                    "total": total,
                    "cancelled": False,
                    "error": str(exc),
                }
            )

    def validate_generation_inputs(self, settings: dict, *, get_remaining_credits: Any = None) -> dict:
        """Validate all inputs needed before starting music generation.

        Returns a dict with:
          - 'ok': bool - whether generation can proceed
          - 'warning': str | None - warning message for the user
          - 'provider': str - the song draft provider
          - 'ok_ids': list[str] - selected OK profile IDs
          - 'alt_ids': list[str] - selected ALT profile IDs
          - 'total': int - total estimated songs (dates x channels x count)
          - 'date_list': list[str] | None - resolved date list
          - 'lyrics_provider': str - resolved lyrics provider
          - 'remaining_credits': int | None - cached Suno credits
          - 'estimated_credits': int - estimated credit consumption
        """
        host = self._host
        db_cfg = self._db_cfg_accessor()

        provider = str(settings.get("songDraftProvider", "deepseek")).strip() or "deepseek"

        ok_ids = [x for x in list(settings.get("channelOkProfileIds") or []) if str(x).strip()]
        alt_ids = [x for x in list(settings.get("channelAltProfileIds") or []) if str(x).strip()]
        if not ok_ids or not alt_ids or len(ok_ids) != len(alt_ids):
            return {"ok": False, "warning": "Select the same number of OK and ALT channels before generating."}

        date_list = self._resolve_date_list()
        if not date_list:
            return {"ok": False, "warning": "Select a valid From and To date."}

        songs_per_batch = max(1, int(settings.get("defaultSongCount", 1) or 1))
        total = len(date_list) * len(ok_ids) * songs_per_batch

        lyrics_provider = str(settings.get("lyricsProvider", "")).strip() or str(settings.get("songDraftProvider", "deepseek")).strip() or "deepseek"

        remaining_credits: int | None = None
        if lyrics_provider == "suno" and get_remaining_credits is not None:
            try:
                remaining_credits = int(get_remaining_credits(max_age_sec=15.0))
            except Exception as exc:
                return {"ok": False, "warning": f"Cannot check Suno credits:\n{exc}"}

        if bool(settings.get("autoGSuno", False)):
            if not db_cfg:
                return {"ok": False, "warning": "Auto-Suno is ON, but Postgres is not configured."}
            if not str(settings.get("sunoOutputDir", "")).strip() and not str(settings.get("downloadsDir", "")).strip():
                return {"ok": False, "warning": "Auto-Suno is ON, but output directory is missing (set Downloads dir in Paths)."}

        if lyrics_provider == "suno":
            if not str(settings.get("sunoCallbackUrl", "")).strip():
                return {"ok": False, "warning": "Lyrics provider is Suno, but Suno callback URL is missing (Settings \u2192 Suno)."}

        estimated_credits = 0
        if lyrics_provider == "suno":
            cost_lyrics = max(0, int(settings.get("sunoCreditsCostLyrics", 1) or 0))
            estimated_credits += total * cost_lyrics

        if lyrics_provider == "suno":
            if remaining_credits is None:
                return {"ok": False, "warning": "Cannot check Suno credits. Try again."}
            reserve = max(0, int(settings.get("sunoCreditsReserve", 10) or 0))
            required = estimated_credits + reserve
            if remaining_credits < required:
                return {
                    "ok": False,
                    "warning": (
                        f"Not enough Suno credits.\n\n"
                        f"Remaining: {remaining_credits}\n"
                        f"Required: {required} (estimated {estimated_credits} + reserve {reserve})"
                    ),
                }

        if total > 200:
            return {"ok": False, "warning": f"Requested {total} songs. Reduce channels/dates/count to avoid costly mass generation."}

        return {
            "ok": True,
            "warning": None,
            "provider": provider,
            "ok_ids": ok_ids,
            "alt_ids": alt_ids,
            "date_list": date_list,
            "songs_per_batch": songs_per_batch,
            "total": total,
            "lyrics_provider": lyrics_provider,
            "remaining_credits": remaining_credits,
            "estimated_credits": estimated_credits,
        }

    def create_generation_batch(self, settings: dict, request: dict) -> dict:
        """Create a generation batch record and return batch metadata.

        This prepares the batch context that the worker thread will consume.
        """
        batch_id = f"batch-{int(request.get('date_index', 0))}-{request.get('profile_ok_id', '')}-{int(time.time() * 1000)}"
        songs_per_batch = max(1, int(request.get("songs_per_batch", 1) or 1))
        total_songs = int(request.get("total_songs", 0) or 0)

        return {
            "batch_id": batch_id,
            "songs_per_batch": songs_per_batch,
            "total": total_songs,
            "settings": settings,
            "date_list": request.get("date_list", []),
            "ok_ids": request.get("ok_ids", []),
            "alt_ids": request.get("alt_ids", []),
        }

    def resolve_generation_inputs(self, song_index: int) -> dict[str, str]:
        """Resolve description/structure selection for one song in a batch.

        Handles match-description-structure pairing, shuffle/all/cycle modes,
        and falls back to custom text when no saved item is selected.
        """
        host = self._host
        settings = host._music_settings()
        descriptions = host._music_collection("descriptions")
        structures = host._music_collection("structures")
        active_description_ids = [str(x).strip() for x in (settings.get("activeDescriptionIds") or []) if str(x).strip()]
        active_structure_ids = [str(x).strip() for x in (settings.get("activeStructureIds") or []) if str(x).strip()]
        enabled_description_ids = [str(x).strip() for x in (settings.get("enabledDescriptionIds") or []) if str(x).strip()]
        enabled_structure_ids = [str(x).strip() for x in (settings.get("enabledStructureIds") or []) if str(x).strip()]

        final_description = host.music_current_description
        final_structure = host.music_current_structure
        description_title = "Custom" if str(final_description or "").strip() else ""
        structure_title = "Custom" if str(final_structure or "").strip() else ""

        if bool(settings.get("matchDescriptionStructure", False)):
            pick_desc_base = (
                [row for row in descriptions if str((row or {}).get("id", "")).strip() in active_description_ids]
                if active_description_ids
                else [row for row in descriptions if str((row or {}).get("id", "")).strip() in enabled_description_ids]
                if enabled_description_ids
                else list(descriptions)
            )
            pick_struct_base = (
                [row for row in structures if str((row or {}).get("id", "")).strip() in active_structure_ids]
                if active_structure_ids
                else [row for row in structures if str((row or {}).get("id", "")).strip() in enabled_structure_ids]
                if enabled_structure_ids
                else list(structures)
            )
            structures_by_key = {
                host._normalize_music_match_key(str((row or {}).get("name", ""))): row
                for row in pick_struct_base
                if host._normalize_music_match_key(str((row or {}).get("name", "")))
            }
            matched_descriptions = [
                row
                for row in pick_desc_base
                if host._normalize_music_match_key(str((row or {}).get("matchKey", ""))) in structures_by_key
            ]
            picked_description = host._music_pick_random(matched_descriptions)
            if not picked_description:
                raise ValueError("Match is ON but no matched description/structure pair was found.")
            match_key = host._normalize_music_match_key(str((picked_description or {}).get("matchKey", "")))
            picked_structure = structures_by_key.get(match_key)
            if not picked_structure:
                raise ValueError("Match is ON but the selected description has no matching structure.")
            final_description = str((picked_description or {}).get("content", "")).strip()
            final_structure = str((picked_structure or {}).get("content", "")).strip()
            description_title = str((picked_description or {}).get("name", "")).strip()
            structure_title = str((picked_structure or {}).get("name", "")).strip()
        else:
            active_description_item = host._music_pick_active_item(descriptions, active_description_ids)
            shuffle_description_item = host._music_pick_from_pool_item(descriptions, enabled_description_ids) if bool(settings.get("shuffleDescription", False)) else None
            effective_description = str((shuffle_description_item or {}).get("content", "")).strip() if shuffle_description_item else host.music_current_description
            final_description = str((active_description_item or {}).get("content", "")).strip() if active_description_item else effective_description
            description_title = (
                str((active_description_item or {}).get("name", "")).strip()
                if active_description_item
                else str((shuffle_description_item or {}).get("name", "")).strip()
                if shuffle_description_item
                else ("Custom" if str(final_description or "").strip() else "")
            )

            if bool(settings.get("cycleStructures", False)):
                structure_pool = (
                    [row for row in structures if str((row or {}).get("id", "")).strip() in active_structure_ids]
                    if active_structure_ids
                    else [row for row in structures if str((row or {}).get("id", "")).strip() in enabled_structure_ids]
                    if enabled_structure_ids
                    else list(structures)
                )
                cycle_item = structure_pool[song_index % len(structure_pool)] if structure_pool else None
                final_structure = str((cycle_item or {}).get("content", "")).strip() if cycle_item else host.music_current_structure
                structure_title = str((cycle_item or {}).get("name", "")).strip() if cycle_item else ("Custom" if str(final_structure or "").strip() else "")
            else:
                active_structure_item = host._music_pick_active_item(structures, active_structure_ids)
                shuffle_structure_item = host._music_pick_from_pool_item(structures, enabled_structure_ids) if bool(settings.get("shuffleStructure", False)) else None
                effective_structure = str((shuffle_structure_item or {}).get("content", "")).strip() if shuffle_structure_item else host.music_current_structure
                final_structure = str((active_structure_item or {}).get("content", "")).strip() if active_structure_item else effective_structure
                structure_title = (
                    str((active_structure_item or {}).get("name", "")).strip()
                    if active_structure_item
                    else str((shuffle_structure_item or {}).get("name", "")).strip()
                    if shuffle_structure_item
                    else ("Custom" if str(final_structure or "").strip() else "")
                )

        return {
            "description": str(final_description or "").strip(),
            "structure": str(final_structure or "").strip(),
            "descriptionTitle": description_title,
            "structureTitle": structure_title,
        }

    # ------------------------------------------------------------------
    # Additional methods from controller
    # ------------------------------------------------------------------

    def clear_generated(self) -> tuple[bool, str]:
        """Clear all generated songs and history."""
        host = self._host
        cfg = host._music_db_cfg_from_forms()
        if cfg is None:
            return False, "Postgres is not configured via .env"
        from ...database.music_pools import clear_generated as music_clear_generated

        result = music_clear_generated(cfg)
        if bool(result.get("ok", False)):
            self._music_data["songs"] = []
            host.music_current_song_id = None
            host._refresh_music_ui()
            return True, str(result.get("message", "Cleared songs + history")).strip()
        return False, str(result.get("message", "Clear failed")).strip()

    def on_history_row_selected(self) -> None:
        """Handle history table row selection."""
        host = self._host
        if not hasattr(host, "music_history_table"):
            return
        row = int(host.music_history_table.currentRow())
        rows = list(getattr(host, "music_history_rows", []) or [])
        if row < 0 or row >= len(rows):
            return
        song = rows[row]
        if not isinstance(song, dict) or bool(song.get("__separator__", False)):
            return
        host.music_current_song_id = str(song.get("songUid") or song.get("id") or "").strip() or None
        host._cache_music_song_from_history(song)
        desc = song.get("songDescription", "") or song.get("song_description", "")
        struct = song.get("songStructure", "") or song.get("song_structure", "")
        host.music_current_description = str(desc).strip()
        host.music_current_structure = str(struct).strip()
        drafts = self._music_data.get("songDrafts") if isinstance(self._music_data.get("songDrafts"), list) else []
        if not drafts:
            drafts = [{"id": "draft-01", "title": "", "album": ""}]
            self._music_data["songDrafts"] = drafts
        drafts[0]["title"] = str(song.get("title", "")).strip()
        drafts[0]["album"] = str(song.get("album", "")).strip()
        host._persist_music_runtime_state()
        host._music_ui_loading = True
        try:
            host._refresh_music_editor_state()
        finally:
            host._music_ui_loading = False
        host._set_music_status(f"Loaded song: {drafts[0]['title'] or 'Untitled'}")

    def resolve_suno_dirs(self, db_cfg: Any, get_profile_by_id: Any, song: dict, settings: dict, *, create_missing: bool) -> dict[str, str]:
        """Resolve Suno output directories from DB mappings or profile-based planning.

        Pure logic — no UI coupling.

        Args:
            db_cfg: Database configuration (must be truthy).
            get_profile_by_id: Callable(profile_id) -> dict | None.
            song: The song dict containing batchId, profileOkId, profileAltId.
            settings: Settings dict containing activeProfileOkId/Id, activeProfileAltId, sunoOutputDir.
            create_missing: If True and no DB mapping exists, plan new directories.

        Returns:
            {"okDir": str, "altDir": str}
        """
        if not db_cfg:
            raise RuntimeError("Postgres database is not configured. Set Database settings and run Migrate.")

        batch_id = str(song.get("batchId", "")).strip()
        if batch_id:
            mapped = get_batch_run_dirs_by_batch_id(db_cfg, batch_id)
            if str(mapped.get("okDir", "")).strip():
                ok_dir = str(mapped.get("okDir", "")).strip()
                alt_dir = str(mapped.get("altDir", "")).strip() or ok_dir
                return {"okDir": ok_dir, "altDir": alt_dir}
            existing = get_latest_suno_output_dirs_by_batch_id(db_cfg, batch_id)
            if bool(existing.get("ok")) and str(existing.get("okDir", "")).strip():
                ok_dir = str(existing.get("okDir", "")).strip()
                alt_dir = str(existing.get("altDir", "")).strip() or ok_dir
                try:
                    upsert_batch_run_dirs(db_cfg, batch_id=batch_id, ok_dir=ok_dir, alt_dir=alt_dir)
                except Exception:
                    pass
                return {"okDir": ok_dir, "altDir": alt_dir}
        if not create_missing:
            return {"okDir": "", "altDir": ""}

        ok_id = str(song.get("profileOkId", "")).strip() or str(settings.get("activeProfileOkId") or settings.get("activeProfileId") or "").strip()
        alt_id = str(song.get("profileAltId", "")).strip() or str(settings.get("activeProfileAltId") or "").strip()
        ok_profile = get_profile_by_id(ok_id)
        alt_profile = get_profile_by_id(alt_id) if alt_id else None

        if not ok_profile:
            raise RuntimeError("No OK profile selected. Select a profile in Settings -> Profiles.")

        base_dir = str(settings.get("sunoOutputDir", "")).strip() or str(settings.get("downloadsDir", "")).strip()
        if not base_dir:
            raise RuntimeError("Suno output directory is not configured. Set it in Settings \u2192 Suno or Settings \u2192 Paths.")

        if batch_id:
            m = re.match(r"^batch-(\d{4}-\d{2}-\d{2})", batch_id)
            run_label = str(m.group(1)) if m else batch_id
            out = plan_next_paired_run_dirs_by_label(
                base_dir,
                str(ok_profile.get("folderName", "")).strip(),
                str((alt_profile or {}).get("folderName", "")).strip() or None,
                run_label,
            )
            try:
                upsert_batch_run_dirs(
                    db_cfg,
                    batch_id=batch_id,
                    ok_dir=str(out.get("okRunDir", "")).strip(),
                    alt_dir=str(out.get("altRunDir", "")).strip() or str(out.get("okRunDir", "")).strip(),
                )
            except Exception:
                pass
            return {"okDir": str(out.get("okRunDir", "")).strip(), "altDir": str(out.get("altRunDir", "")).strip() or str(out.get("okRunDir", "")).strip()}

        ok_dir = plan_next_run_dir(
            base_dir,
            str(ok_profile.get("folderName", "")).strip(),
            str(ok_profile.get("runPrefix", "")).strip(),
        )
        alt_dir = (
            plan_next_run_dir(
                base_dir,
                str((alt_profile or {}).get("folderName", "")).strip(),
                str((alt_profile or {}).get("runPrefix", "")).strip(),
            )
            if alt_profile
            else ok_dir
        )
        return {"okDir": ok_dir, "altDir": alt_dir}

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _resolve_date_list(self) -> list[str] | None:
        """Resolve the date range into a list of ISO date strings.

        Reads from host.ui widgets - pure data logic, no UI manipulation.
        """
        host = self._host

        start = self._parse_date_ymd(host.music_run_from_date)
        end = self._parse_date_ymd(host.music_run_to_date)
        if start is None or end is None:
            return None
        if start > end:
            return None
        out: list[str] = []
        current = start
        while current <= end:
            out.append(current.isoformat())
            current = current + timedelta(days=1)
        return out

    @staticmethod
    def _parse_date_ymd(value: str) -> date | None:
        """Parse a 'yyyy-MM-dd' string into a datetime.date, or None."""
        text = str(value or "").strip()
        if not text:
            return None
        try:
            return date.fromisoformat(text)
        except (ValueError, TypeError):
            return None

    # ------------------------------------------------------------------
    # Methods absorbed from MainWindow music domain (Phase 5)
    # ------------------------------------------------------------------

    def on_generate_clicked(self) -> None:
        """Handle the generate button click from the UI.

        Validates inputs, sets up generation state, and spawns the
        generation worker thread. The host provides UI update callbacks.
        """
        host = self._host
        if host._music_generating:
            host._music_cancel_requested = True
            host._set_music_status("Stopping music generation...")
            return
        settings = host._music_settings()
        result = self.validate_generation_inputs(
            settings, get_remaining_credits=host._get_suno_remaining_credits_fresh
        )
        if not result["ok"]:
            self._warning_fn("Generate", result["warning"])
            return
        host._music_cancel_requested = False
        host._set_music_generate_running(True)
        host._set_music_status(f"Generating 0/{result['total']} songs saved")
        host._music_suno_auto_poll_enabled = bool(settings.get("autoGSuno", False))
        host._music_generation_thread = threading.Thread(
            target=self.generate_music_batch,
            args=(
                {
                    "provider": result["provider"],
                    "settings": dict(settings),
                    "ok_ids": list(result["ok_ids"]),
                    "alt_ids": list(result["alt_ids"]),
                    "date_list": list(result["date_list"]),
                    "songs_per_batch": result["songs_per_batch"],
                    "total": result["total"],
                },
            ),
            daemon=True,
        )
        host._music_generation_thread.start()

    # ------------------------------------------------------------------
    # Timer / polling policy (Phase 7)
    # ------------------------------------------------------------------

    def start_polling(self, timer: Any) -> None:
        """Start the Suno auto-poll timer.

        The coordinator decides WHEN to start polling (the policy).
        MainWindow owns the QTimer object for lifecycle management.

        Args:
            timer: The QTimer instance to start (interval 30s, already configured).
        """
        self._suno_poll_timer = timer
        if timer is not None and not timer.isActive():
            timer.start()

    def stop_polling(self, timer: Any = None) -> None:
        """Stop the Suno auto-poll timer.

        Args:
            timer: The QTimer instance to stop. If None, uses the stored reference.
        """
        t = timer if timer is not None else getattr(self, "_suno_poll_timer", None)
        if t is not None and t.isActive():
            t.stop()

    def trigger_suno_poll(self, *, manual: bool = False, max_tasks: int = 10) -> None:
        """Trigger a Suno poll check in a background thread.

        Validates configuration and spawns the poll worker.
        """
        host = self._host
        if host._music_suno_poll_running:
            if self._logger:
                self._logger.info(f"[{time.strftime('%H:%M:%S')}] Suno poll: skipped (already running)")
            return
        cfg = host._music_db_cfg_from_forms()
        if not cfg:
            if self._logger:
                self._logger.info(f"[{time.strftime('%H:%M:%S')}] Suno poll: skipped (no DB config)")
            if manual:
                host._set_music_suno_status("No Suno DB configured")
            return
        settings = host._music_settings()
        output_dir = str(settings.get("sunoOutputDir", "")).strip() or str(settings.get("downloadsDir", "")).strip()
        if not output_dir:
            if self._logger:
                self._logger.info(f"[{time.strftime('%H:%M:%S')}] Suno poll: skipped (no output dir)")
            if manual:
                host._set_music_suno_status("No Suno output directory configured")
            return
        host._music_suno_poll_running = True
        if self._logger:
            self._logger.info(f"[{time.strftime('%H:%M:%S')}] Suno poll: starting (output_dir={output_dir[-60:]})")
        if not manual:
            host._set_music_suno_status("Suno auto-poll: checking...")

        def work():
            from ...services.music_suno import suno_api_try_get_tracks, download_to_file, build_suno_output_paths
            from ...database.music_db import list_pending_suno_tasks as db_list_pending, upsert_suno_task as db_upsert
            from pathlib import Path as _Path
            try:
                # Query pending tasks directly (same approach as right-click Download MP3)
                tasks = db_list_pending(cfg, max_tasks)
                if self._logger:
                    self._logger.info(f"[{time.strftime('%H:%M:%S')}] Suno poll: {len(tasks)} pending tasks found")
                if not tasks:
                    host.bus.music_event.emit({
                        "type": "suno_poll_result",
                        "result": {"ok": True, "checked": 0, "downloaded": 0},
                        "manual": manual,
                    })
                    return

                downloaded = 0
                failed = 0
                for task in tasks:
                    try:
                        task_id = str(task.get("taskId", "")).strip()
                        title = str(task.get("title", "")).strip()
                        track_no = int(task.get("trackNo")) if isinstance(task.get("trackNo"), int) else None
                        if not task_id:
                            continue

                        # Check Suno API for current audio URLs
                        result = suno_api_try_get_tracks(self._generation_proxy, task_id)
                        audio_urls = list(result.get("audioUrls") or [])
                        ok_url = str(audio_urls[0] or "").strip() if len(audio_urls) >= 1 else ""
                        alt_url = str(audio_urls[1] or "").strip() if len(audio_urls) >= 2 else ""

                        if not ok_url and not alt_url:
                            # Suno still processing — skip for now
                            if self._logger:
                                self._logger.info(f"[{time.strftime('%H:%M:%S')}] Suno poll: {title[:30]} — no URLs yet (status={result.get('status', '?')})")
                            continue

                        # Resolve download directories from task record
                        target_dir_ok = str(task.get("outputDirOk", "")).strip() or output_dir
                        target_dir_alt = str(task.get("outputDirAlt", "")).strip() or target_dir_ok

                        ok_downloaded = bool(task.get("downloadedOk", False))
                        alt_downloaded = bool(task.get("downloadedAlt", False))
                        ok_404 = False
                        alt_404 = False

                        # Download OK track
                        if ok_url and not ok_downloaded:
                            paths = build_suno_output_paths(output_dir=target_dir_ok, title=title, track_no=track_no)
                            if _Path(paths["ok"]).exists():
                                ok_downloaded = True
                            else:
                                try:
                                    if self._logger:
                                        self._logger.info(f"[{time.strftime('%H:%M:%S')}] Suno poll: downloading OK url={ok_url[:80]} → {paths['ok'][-60:]}")
                                    download_to_file(ok_url, paths["ok"])
                                    ok_downloaded = True
                                    downloaded += 1
                                    if self._logger:
                                        self._logger.info(f"[{time.strftime('%H:%M:%S')}] Suno poll: downloaded OK ✓")
                                except Exception as dl_exc:
                                    if "404" in str(dl_exc):
                                        # Track 404 count for this task
                                        ok_404 = True
                                        if self._logger:
                                            self._logger.warning(f"[{time.strftime('%H:%M:%S')}] Suno poll: OK URL 404: {title[:30]}")
                                    else:
                                        raise

                        # Download ALT track
                        if alt_url and not alt_downloaded:
                            paths = build_suno_output_paths(output_dir=target_dir_alt, title=title, track_no=track_no)
                            if _Path(paths["alt"]).exists():
                                alt_downloaded = True
                            else:
                                try:
                                    if self._logger:
                                        self._logger.info(f"[{time.strftime('%H:%M:%S')}] Suno poll: downloading ALT url={alt_url[:80]} → {paths['alt'][-60:]}")
                                    download_to_file(alt_url, paths["alt"])
                                    alt_downloaded = True
                                    downloaded += 1
                                    if self._logger:
                                        self._logger.info(f"[{time.strftime('%H:%M:%S')}] Suno poll: downloaded ALT ✓")
                                except Exception as dl_exc:
                                    if "404" in str(dl_exc):
                                        alt_404 = True
                                        if self._logger:
                                            self._logger.warning(f"[{time.strftime('%H:%M:%S')}] Suno poll: ALT URL 404: {title[:30]}")
                                    else:
                                        raise

                        # If both URLs return 404, mark task as done (permanently expired)
                        if ok_404 and alt_404:
                            ok_downloaded = True
                            alt_downloaded = True
                            if self._logger:
                                self._logger.warning(f"[{time.strftime('%H:%M:%S')}] Suno poll: both URLs expired, marking task done: {title[:40]}")

                        # Update task record in DB (mark as downloaded)
                        db_upsert(cfg, {
                            "requestHash": str(task.get("requestHash", "")).strip(),
                            "songUid": str(task.get("songUid", "")).strip(),
                            "batchId": str(task.get("batchId", "")).strip(),
                            "trackNo": task.get("trackNo"),
                            "model": str(task.get("model", "")).strip(),
                            "title": title,
                            "style": str(task.get("style", "")).strip(),
                            "instrumental": bool(task.get("instrumental", False)),
                            "taskId": task_id,
                            "status": str(result.get("status", "")).strip() or "SUCCESS",
                            "audioUrlOk": ok_url or None,
                            "audioUrlAlt": alt_url or None,
                            "outputDirOk": str(task.get("outputDirOk", "")).strip() or None,
                            "outputDirAlt": str(task.get("outputDirAlt", "")).strip() or None,
                            "downloadedOk": ok_downloaded,
                            "downloadedAlt": alt_downloaded,
                        })
                    except Exception as task_exc:
                        failed += 1
                        if self._logger:
                            self._logger.error(f"[{time.strftime('%H:%M:%S')}] Suno poll: task error: {task_exc}")

                if self._logger:
                    self._logger.info(f"[{time.strftime('%H:%M:%S')}] Suno poll: done. checked={len(tasks)} downloaded={downloaded} failed={failed}")
                host.bus.music_event.emit({
                    "type": "suno_poll_result",
                    "result": {"ok": True, "checked": len(tasks), "downloaded": downloaded, "failed": failed},
                    "manual": manual,
                })
            except Exception as e:
                if self._logger:
                    self._logger.error(f"[{time.strftime('%H:%M:%S')}] Suno poll: exception: {e}")
                host.bus.music_event.emit({
                    "type": "suno_poll_result",
                    "result": {"ok": False, "message": str(e)},
                    "manual": manual,
                })

        threading.Thread(target=work, daemon=True).start()

    def handle_song_event(self, event: dict) -> None:
        """Handle a 'song' event from the music event bus.

        Appends the generated song, triggers auto-image/suno if enabled,
        and updates status.
        """
        host = self._host
        song = event.get("song")
        if isinstance(song, dict):
            host._append_generated_music_song(song)
            batch_id = str(song.get("batchId", "")).strip()
            ok_id = str(song.get("profileOkId", "")).strip()
            alt_id = str(song.get("profileAltId", "")).strip()
            if batch_id and ok_id and alt_id:
                batches = getattr(host, "_auto_video_batches", None)
                if not isinstance(batches, dict):
                    batches = {}
                    host._auto_video_batches = batches
                songs_per_batch = max(1, int(host._music_settings().get("defaultSongCount", 1) or 1))
                batches[batch_id] = {"okProfileId": ok_id, "altProfileId": alt_id, "songsPerBatch": songs_per_batch}
            if bool(host._music_settings().get("autoGenImage", False)):
                host._image_coordinator.ensure_jobs_for_song(song)
            if bool(host._music_settings().get("autoGSuno", False)):
                host._submit_music_song_to_suno(song, auto=True)
        total = int(event.get("total", 0) or 0)
        completed = int(event.get("completed", 0) or 0)
        failed = int(event.get("failed", 0) or 0)
        suffix = f" · {failed} failed" if failed else ""
        host._set_music_status(f"Generating {completed}/{total} songs saved{suffix}")

    def handle_done_event(self, event: dict) -> None:
        """Handle a 'done' event — generation batch completed or cancelled."""
        host = self._host
        host._music_cancel_requested = False
        host._music_generation_thread = None
        host._set_music_generate_running(False)
        # Don't disable auto-poll here — keep polling until all Suno downloads complete
        # The poll loop will stop itself when there are no more pending tasks
        total = int(event.get("total", 0) or 0)
        completed = int(event.get("completed", 0) or 0)
        failed = int(event.get("failed", 0) or 0)
        if str(event.get("error", "")).strip():
            host._set_music_status(f"Music generation failed: {str(event.get('error', '')).strip()}")
        elif bool(event.get("cancelled", False)):
            host._set_music_status(f"Stopped: {completed}/{total} songs saved")
        else:
            suffix = f" · {failed} failed" if failed else ""
            host._set_music_status(f"Done: {completed}/{total} songs saved{suffix}")
        # Trigger a poll check to pick up any pending Suno downloads
        if host._music_suno_auto_poll_enabled:
            self._defer_call_fn(3000, lambda: self.trigger_suno_poll(manual=False, max_tasks=10))

    def handle_suno_poll_result_event(self, event: dict) -> None:
        """Handle a 'suno_poll_result' event — poll completed."""
        host = self._host
        host._music_suno_poll_running = False
        _raw_result = event.get("result")
        result: dict = _raw_result if isinstance(_raw_result, dict) else {}
        manual = bool(event.get("manual", False))
        # Always log poll results for debugging
        if self._logger:
            self._logger.info(f"[{time.strftime('%H:%M:%S')}] Suno poll result: checked={result.get('checked', '?')} downloaded={result.get('downloaded', '?')} failed={result.get('failed', '?')} ok={result.get('ok', '?')} message={str(result.get('message', ''))[:100]}")
        if not bool(result.get("ok", False)):
            message = str(result.get("message", "Suno poll failed")).strip() or "Suno poll failed"
            if self._logger:
                self._logger.error(f"[{time.strftime('%H:%M:%S')}] Suno poll failed: {message}")
            if manual:
                host._set_music_suno_status(message)
                host._set_music_status(message)
            # Retry even on failure if auto-poll is enabled (transient errors)
            if not manual and host._music_suno_auto_poll_enabled:
                self._defer_call_fn(15000, lambda: self.trigger_suno_poll(manual=False, max_tasks=10))
            return
        checked = int(result.get("checked", 0) or 0)
        downloaded = int(result.get("downloaded", 0) or 0)
        if downloaded > 0:
            message = f"Suno auto-poll: downloaded {downloaded} file(s) from {checked} task(s)"
            host._set_music_suno_status(message)
            host._set_music_status(message)
            # Trigger auto-video conversion immediately after downloads
            if bool(host._music_settings().get("autoVideoAfterSuno", False)):
                self._defer_call_fn(2000, host._auto_video_tick)
        elif manual:
            message = "Suno refresh: no pending downloads" if checked == 0 else f"Suno refresh: checked {checked} task(s), nothing new"
            host._set_music_suno_status(message)
            host._set_music_status(message)
        elif not manual and checked > 0:
            host._set_music_suno_status(f"Suno auto-poll: checking... ({checked} pending)")

        # Keep polling if there are still pending tasks
        if not manual and checked > 0:
            # Tasks still pending — poll again (shorter interval if downloads happened)
            delay = 5000 if downloaded > 0 else 15000
            self._defer_call_fn(delay, lambda: self.trigger_suno_poll(manual=False, max_tasks=10))
        elif not manual and checked == 0 and host._music_suno_auto_poll_enabled:
            # No more pending tasks — all downloads complete, stop polling
            host._music_suno_auto_poll_enabled = False
            host._set_music_suno_status("Suno auto-poll: all downloads complete")
            host._set_music_status("Suno: all downloads complete")
            # Trigger auto-video to start converting the downloaded MP3s
            if bool(host._music_settings().get("autoVideoAfterSuno", False)):
                self._defer_call_fn(2000, host._auto_video_tick)

    def handle_suno_schedule_poll_event(self, event: dict) -> None:
        """Handle a 'suno_schedule_poll' event — schedule next poll."""
        host = self._host
        delay_ms = int(event.get("delayMs", 0) or 0)
        max_tasks = int(event.get("maxTasks", 10) or 10)
        delay_ms = max(0, min(60000, delay_ms))
        max_tasks = max(1, min(50, max_tasks))
        self._defer_call_fn(delay_ms, lambda: self.trigger_suno_poll(manual=False, max_tasks=max_tasks))

    def on_polish_clicked(self) -> None:
        """Handle the lyrics polish button click.

        Validates inputs and spawns a background thread for polishing.
        """
        host = self._host
        settings = host._music_settings()
        api_key = str(settings.get("openaiApiKey", "")).strip()
        if not api_key:
            self._warning_fn("Polish", "OpenAI API key is missing. Set it in shared settings first.")
            return
        base = host.music_song_lyrics_editor.toPlainText().strip() if hasattr(host, "music_song_lyrics_editor") else ""
        if not base:
            self._warning_fn("Polish", "There are no lyrics to polish.")
            return
        strength = int(host.music_polish_slider.value() if hasattr(host, "music_polish_slider") else 60)
        host._set_music_status("Polishing lyrics...")

        def work():
            try:
                from ...services.music_generation import polish_lyrics_with_openai
                polished = polish_lyrics_with_openai(api_key=api_key, lyrics=base, strength=strength)
                host.bus.music_event.emit({"type": "lyrics_polished", "lyrics": polished})
            except Exception as exc:
                host.bus.music_event.emit({"type": "status", "message": f"Polish failed: {exc}"})

        threading.Thread(target=work, daemon=True).start()

    def handle_lyrics_polished_event(self, event: dict) -> None:
        """Handle a 'lyrics_polished' event — update song record and persist."""
        host = self._host
        lyrics = str(event.get("lyrics", "")).strip()
        if not lyrics:
            host._set_music_status("Polish returned empty lyrics")
            return
        current_song = host._current_music_song() or {}
        current_song_id = str(current_song.get("id", "")).strip()
        updated_song = host._update_music_song_record(current_song_id, {"lyricsPolished": lyrics}) if current_song_id else None
        if updated_song and self._db_cfg_accessor():
            try:
                from ...database.music_db import upsert_song as music_upsert_song
                music_upsert_song(self._db_cfg_accessor(), updated_song)
            except Exception as exc:
                if self._logger:
                    self._logger.error(f"[{time.strftime('%H:%M:%S')}] Failed to persist polished lyrics to DB: {exc}")
        host._refresh_music_ui()
        host._set_music_status("Lyrics polished")

    def on_ngrok_start(self) -> None:
        """Start ngrok tunnel for Suno callbacks.

        Starts the callback server, then ngrok, and updates UI status.
        """
        host = self._host
        callback_status = host._music_callback_server.start()
        port = int(callback_status.get("port") or 0)
        if port <= 0:
            host._set_music_suno_status(f"Callback server failed: {str(callback_status.get('lastError', '')).strip() or 'Unknown error'}")
            host._refresh_music_ngrok_status()
            return
        status = host._music_ngrok_manager.start(local_port=port, callback_path="/suno/callback")
        callback_url = str(status.get("callbackUrl", "")).strip()
        if callback_url and hasattr(host, "music_suno_callback_url"):
            host.music_suno_callback_url.setText(callback_url)
            host._save_music_suno_settings()
        host._refresh_music_ngrok_status()
        host._set_music_suno_status("ngrok started" if status.get("running") else str(status.get("lastError", "")).strip() or "ngrok failed")

    def on_ngrok_stop(self) -> None:
        """Stop ngrok tunnel and callback server."""
        host = self._host
        host._music_ngrok_manager.stop()
        host._music_callback_server.stop()
        host._refresh_music_ngrok_status()
        host._set_music_suno_status("ngrok stopped")
