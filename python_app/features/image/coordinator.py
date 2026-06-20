"""ImageGenerationCoordinator — orchestrates image generation workflows.

Absorbs logic from controllers/image_controller.py and MainWindow image domain
methods, using dependency injection for all external collaborators.
"""

from __future__ import annotations

import re
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Protocol

from ..ports import EventBusPort, LoggerPort
from ...services.api_errors import InsufficientCreditsError, LicenseExpiredError

if TYPE_CHECKING:
    from ...services.generation_proxy import GenerationProxy

from ...database.persistence import DbCfg

from ...database.image_db import (
    get_image_job_by_key,
    upsert_image_job,
    pick_least_used_preset,
    pick_least_used_value,
    list_image_jobs,
    retry_image_job,
)
from ...database.music_db import (
    get_batch_run_dirs_by_batch_id,
    upsert_batch_run_dirs,
    get_latest_suno_output_dirs_by_batch_id,
    list_songs_by_batch_id,
)
from ...services.music_suno import plan_next_paired_run_dirs_by_label
from ...services.image_generation import run_pending_image_jobs


class ImageDbPort(Protocol):
    """Database interface for image job persistence."""

    def list_image_jobs(self, db_cfg: Any, **filters: Any) -> list[dict]: ...
    def upsert_image_job(self, db_cfg: Any, job: dict) -> None: ...


class ImageServicePort(Protocol):
    """External image generation service interface."""

    def poll_generation_status(self, job_uids: list[str]) -> list[dict]: ...
    def submit_generation(self, request: dict) -> dict: ...


class ImageGenerationCoordinator:
    """Coordinates image generation workflows with injected dependencies."""

    def __init__(
        self,
        db: ImageDbPort,
        service: ImageServicePort,
        bus: EventBusPort,
        settings_accessor: Callable[[], dict],
        db_cfg_accessor: Callable[[], Any],
        logger: LoggerPort | None = None,
        profile_accessor: Callable[[str], dict | None] | None = None,
        status_callback: Callable[[str], None] | None = None,
        db_cfg: DbCfg | None = None,
        generation_proxy: GenerationProxy | None = None,
    ) -> None:
        if db is None:
            raise ValueError("ImageGenerationCoordinator requires a non-None db dependency")
        if service is None:
            raise ValueError("ImageGenerationCoordinator requires a non-None service dependency")
        if bus is None:
            raise ValueError("ImageGenerationCoordinator requires a non-None bus dependency")
        if settings_accessor is None:
            raise ValueError("ImageGenerationCoordinator requires a non-None settings_accessor dependency")
        if db_cfg_accessor is None:
            raise ValueError("ImageGenerationCoordinator requires a non-None db_cfg_accessor dependency")
        self._db = db
        self._service = service
        self._bus = bus
        self._settings_accessor = settings_accessor
        self._db_cfg_accessor = db_cfg_accessor
        self._db_cfg: DbCfg | None = db_cfg
        self._logger = logger
        self._profile_accessor = profile_accessor
        self._status_callback = status_callback
        self._generation_proxy: GenerationProxy | None = generation_proxy

        # Coordinator-owned state (previously on self.host)
        self._image_poll_running: bool = False
        self._image_cancel_requested: bool = False

    def update_db_cfg(self, cfg: DbCfg | None) -> None:
        """Update the database configuration after a reconnection."""
        self._db_cfg = cfg

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _music_settings(self) -> dict:
        """Return current music/image settings via the injected accessor."""
        return self._settings_accessor()

    def _music_profile_by_id(self, profile_id: str) -> dict | None:
        """Return a profile dict by ID via the injected accessor."""
        if self._profile_accessor is None:
            return None
        return self._profile_accessor(profile_id)

    def _set_image_status(self, msg: str) -> None:
        """Forward status messages via the callback or logger."""
        if self._status_callback is not None:
            self._status_callback(msg)
        elif self._logger is not None:
            self._logger.info(msg)

    def _log(self, msg: str) -> None:
        """Log a message via the injected logger."""
        if self._logger is not None:
            self._logger.info(msg)

    # ------------------------------------------------------------------
    # Timer / polling policy (Phase 7)
    # ------------------------------------------------------------------

    def start_polling(self, auto_poll_timer: Any, live_refresh_timer: Any) -> None:
        """Start the image auto-poll timer based on current settings.

        The coordinator decides WHEN to start/stop polling (the policy).
        MainWindow owns the QTimer objects for lifecycle management.

        Args:
            auto_poll_timer: QTimer for periodic image polling (interval 30s).
            live_refresh_timer: QTimer for live UI refresh during polls (interval 1.5s).
        """
        self._auto_poll_timer = auto_poll_timer
        self._live_refresh_timer = live_refresh_timer
        self.sync_auto_poll_timer()

    def stop_polling(self, auto_poll_timer: Any = None, live_refresh_timer: Any = None) -> None:
        """Stop all image polling timers.

        Args:
            auto_poll_timer: The auto-poll QTimer to stop. If None, uses stored reference.
            live_refresh_timer: The live-refresh QTimer to stop. If None, uses stored reference.
        """
        t = auto_poll_timer if auto_poll_timer is not None else getattr(self, "_auto_poll_timer", None)
        if t is not None and t.isActive():
            t.stop()
        t2 = live_refresh_timer if live_refresh_timer is not None else getattr(self, "_live_refresh_timer", None)
        if t2 is not None and t2.isActive():
            t2.stop()

    def sync_auto_poll_timer(self) -> None:
        """Sync the auto-poll timer state based on current settings.

        Starts the timer if autoGenImage is enabled, generation proxy is available,
        and DB is configured. Stops it otherwise. Preserves the original 30s interval.
        """
        timer = getattr(self, "_auto_poll_timer", None)
        if timer is None:
            return
        settings = self._music_settings()
        enabled = bool(settings.get("autoGenImage", False))
        api_ok = self._generation_proxy is not None
        db_ok = bool(self._db_cfg_accessor())
        if enabled and api_ok and db_ok:
            if not timer.isActive():
                timer.start()
        else:
            if timer.isActive():
                timer.stop()

    def start_live_refresh(self) -> None:
        """Start the live refresh timer (called when image poll starts)."""
        t = getattr(self, "_live_refresh_timer", None)
        if t is not None and not t.isActive():
            t.start()

    def stop_live_refresh(self) -> None:
        """Stop the live refresh timer (called when image poll completes)."""
        t = getattr(self, "_live_refresh_timer", None)
        if t is not None and t.isActive():
            t.stop()

    # ------------------------------------------------------------------
    # Methods absorbed from controllers/image_controller.py
    # ------------------------------------------------------------------

    def trigger_image_poll(self, *, manual: bool = False, max_jobs: int = 8) -> None:
        if self._image_poll_running:
            if manual:
                self._set_image_status("Image worker already running...")
            return
        db_cfg = self._db_cfg_accessor()
        if not db_cfg:
            if manual:
                self._set_image_status("Image generation requires Postgres configured via .env")
            return
        settings = self._music_settings()
        if not self._generation_proxy:
            if manual:
                self._set_image_status("Image generation unavailable: not connected to Platform API")
            return
        self._image_poll_running = True
        if manual:
            self._set_image_status("Running image jobs...")
        self._bus.emit("music_event", {"type": "image_poll_started", "manual": bool(manual)})

        def work():
            try:
                result = run_pending_image_jobs(
                    db_cfg=db_cfg,
                    settings=settings,
                    generation_proxy=self._generation_proxy,
                    max_jobs=max_jobs,
                    should_cancel=lambda: bool(self._image_cancel_requested),
                    on_log=self._log,
                )
                self._bus.emit("music_event", {"type": "image_poll_result", "result": result, "manual": manual})
            except InsufficientCreditsError as exc:
                self._log(f"[{time.strftime('%H:%M:%S')}] Image poll failed: insufficient credits — {exc}")
                self._bus.emit(
                    "music_event",
                    {
                        "type": "image_poll_result",
                        "result": {"ok": False, "message": f"Insufficient credits: {exc}"},
                        "manual": manual,
                    },
                )
            except LicenseExpiredError as exc:
                self._log(f"[{time.strftime('%H:%M:%S')}] Image poll failed: license expired — {exc}")
                self._bus.emit(
                    "music_event",
                    {
                        "type": "image_poll_result",
                        "result": {"ok": False, "message": f"License expired: {exc}"},
                        "manual": manual,
                    },
                )
            except Exception as exc:
                self._log(f"[{time.strftime('%H:%M:%S')}] Image poll failed: {exc}")
                self._bus.emit(
                    "music_event",
                    {
                        "type": "image_poll_result",
                        "result": {"ok": False, "message": str(exc)},
                        "manual": manual,
                    },
                )
            finally:
                self._image_poll_running = False

        threading.Thread(target=work, daemon=True).start()

    def ensure_jobs_for_song(self, song: dict) -> None:
        db_cfg = self._db_cfg_accessor()
        if not db_cfg:
            return
        settings = self._music_settings()
        if not bool(settings.get("autoGenImage", False)):
            return
        batch_id = str(song.get("batchId", "")).strip()
        ok_id = str(song.get("profileOkId", "")).strip()
        alt_id = str(song.get("profileAltId", "")).strip()
        pair_index = _batch_pair_index(batch_id)
        if not batch_id or not ok_id or not alt_id:
            return
        ymd = _batch_run_date(batch_id)
        if not ymd:
            return
        dirs = self._ensure_batch_dirs(batch_id=batch_id, run_label=ymd, ok_id=ok_id, alt_id=alt_id)
        if not dirs:
            return
        # Resolve samples once from OK profile so both channels share the same valid pool
        ok_profile = self._music_profile_by_id(ok_id)
        ok_image_cfg = (ok_profile or {}).get("imageConfig") if isinstance((ok_profile or {}).get("imageConfig"), dict) else {}
        ok_profile_bg_samples = (ok_image_cfg or {}).get("backgroundSamples") if isinstance((ok_image_cfg or {}).get("backgroundSamples"), list) else []
        ok_profile_thumb_samples = (ok_image_cfg or {}).get("thumbnailSamples") if isinstance((ok_image_cfg or {}).get("thumbnailSamples"), list) else []
        bg_samples = [str(x).strip() for x in (ok_profile_bg_samples if ok_profile_bg_samples else list(settings.get("imageBgSamples") or [])) if str(x).strip()]
        thumb_samples = [str(x).strip() for x in (ok_profile_thumb_samples if ok_profile_thumb_samples else list(settings.get("imageThumbSamples") or [])) if str(x).strip()]

        ok_thumb_preset_id, ok_thumb_sample = self._enqueue_batch_channel_jobs(batch_id=batch_id, ymd=ymd, pair_index=pair_index, profile_id=ok_id, role="OK", bg_samples=bg_samples, thumb_samples=thumb_samples)
        exclude_preset_ids = [ok_thumb_preset_id] if ok_thumb_preset_id else []
        exclude_samples = [ok_thumb_sample] if ok_thumb_sample else []
        self._enqueue_batch_channel_jobs(batch_id=batch_id, ymd=ymd, pair_index=pair_index, profile_id=alt_id, role="ALT", bg_samples=bg_samples, thumb_samples=thumb_samples, exclude_thumb_preset_ids=exclude_preset_ids, exclude_thumb_sample_paths=exclude_samples)
        self.trigger_image_poll(manual=False, max_jobs=8)

    def enqueue_manual(
        self,
        *,
        batches: list[dict],
        prompt: str,
        bg_samples: list[str],
        thumb_samples: list[str],
    ) -> dict:
        db_cfg = self._db_cfg_accessor()
        if not db_cfg:
            return {"ok": False, "message": "Postgres is not configured"}
        batch_rows = [b for b in list(batches or []) if isinstance(b, dict) and str(b.get("batchId", "")).strip()]
        if not batch_rows:
            return {"ok": False, "message": "Select at least 1 batch from Music History before generating images"}
        total_batches = 0
        total_jobs = 0
        skipped = 0
        for b in batch_rows:
            batch_id = str(b.get("batchId", "")).strip()
            ok_id = str(b.get("profileOkId", "")).strip()
            alt_id = str(b.get("profileAltId", "")).strip()
            ymd = str(b.get("runDate", "")).strip() or _batch_run_date(batch_id)
            pair_index = _batch_pair_index(batch_id)
            if not batch_id or not ok_id or not alt_id:
                skipped += 1
                continue
            if not ymd:
                skipped += 1
                continue
            if not self._ensure_existing_batch_dirs(batch_id=batch_id):
                skipped += 1
                continue
            ok_thumb_preset_id, ok_thumb_sample = self._enqueue_batch_channel_jobs(batch_id=batch_id, ymd=ymd, pair_index=pair_index, profile_id=ok_id, role="OK", prompt=prompt, bg_samples=bg_samples, thumb_samples=thumb_samples)
            exclude_preset_ids = [ok_thumb_preset_id] if ok_thumb_preset_id else []
            exclude_samples = [ok_thumb_sample] if ok_thumb_sample else []
            self._enqueue_batch_channel_jobs(batch_id=batch_id, ymd=ymd, pair_index=pair_index, profile_id=alt_id, role="ALT", prompt=prompt, bg_samples=bg_samples, thumb_samples=thumb_samples, exclude_thumb_preset_ids=exclude_preset_ids, exclude_thumb_sample_paths=exclude_samples)
            total_batches += 1
            total_jobs += 4
        return {"ok": True, "batches": total_batches, "jobs": total_jobs, "skipped": skipped}

    def retry_job(self, job_uid: str) -> None:
        db_cfg = self._db_cfg_accessor()
        if not db_cfg:
            return
        retry_image_job(db_cfg, job_uid)
        self.trigger_image_poll(manual=True, max_jobs=8)

    def retry_jobs(self, job_uids: list[str]) -> None:
        db_cfg = self._db_cfg_accessor()
        if not db_cfg:
            return
        uids = [str(x).strip() for x in (job_uids or []) if str(x).strip()]
        if not uids:
            return
        for uid in uids:
            retry_image_job(db_cfg, uid)
        self.trigger_image_poll(manual=True, max_jobs=8)

    def enqueue_missing_thumbnails(self) -> dict:
        db_cfg = self._db_cfg_accessor()
        if not db_cfg:
            return {"ok": False, "message": "Postgres is not configured"}
        if not self._generation_proxy:
            return {"ok": False, "message": "Image generation unavailable: not connected to Platform API"}
        all_jobs = list_image_jobs(db_cfg, limit=10000)
        batch_profile_map: dict[str, dict] = {}
        for j in all_jobs:
            kind = str(j.get("kind", "")).strip().lower()
            status = str(j.get("status", "")).strip().upper()
            batch_id = str(j.get("batchId", "")).strip()
            profile_id = str(j.get("profileId", "")).strip()
            key = f"{batch_id}||{profile_id}"
            entry = batch_profile_map.get(key)
            if entry is None:
                entry = {"batch_id": batch_id, "profile_id": profile_id, "bg_ready": False, "has_thumb": False}
                batch_profile_map[key] = entry
            if kind == "background" and status in ("READY",):
                entry["bg_ready"] = True
            if kind == "thumbnail":
                entry["has_thumb"] = True
        candidates = [v for v in batch_profile_map.values() if v["bg_ready"] and not v["has_thumb"]]
        if not candidates:
            return {"ok": False, "message": "No batches with ready backgrounds and missing thumbnails"}
        enqueued = 0
        for c in candidates:
            batch_id = c["batch_id"]
            profile_id = c["profile_id"]
            ymd = _batch_run_date(batch_id)
            if not ymd:
                continue
            pair_index = _batch_pair_index(batch_id)
            self._enqueue_batch_channel_jobs(batch_id=batch_id, ymd=ymd, pair_index=pair_index, profile_id=profile_id, role="OK", skip_bg=True)
            enqueued += 1
        if enqueued == 0:
            return {"ok": False, "message": "Failed to enqueue any thumbnail jobs"}
        return {"ok": True, "enqueued": enqueued}

    def enqueue_thumbnail_for_batch(self, batch_id: str, profile_id: str) -> dict:
        db_cfg = self._db_cfg_accessor()
        if not db_cfg:
            return {"ok": False, "message": "Postgres is not configured"}
        if not str(batch_id or "").strip() or not str(profile_id or "").strip():
            return {"ok": False, "message": "Missing batch or profile info"}
        thumb_exists = get_image_job_by_key(db_cfg, batch_id=batch_id, profile_id=profile_id, kind="thumbnail")
        if thumb_exists:
            return {"ok": False, "message": "Thumbnail job already exists for this batch/profile"}
        ymd = _batch_run_date(batch_id)
        if not ymd:
            return {"ok": False, "message": "Cannot determine run date for this batch"}
        pair_index = _batch_pair_index(batch_id)
        self._enqueue_batch_channel_jobs(batch_id=batch_id, ymd=ymd, pair_index=pair_index, profile_id=profile_id, role="OK", skip_bg=True)
        job_uid = f"img-{batch_id}-{profile_id}-thumbnail"
        return {"ok": True, "jobUid": job_uid}

    def process_poll_result(self, result: dict, *, manual: bool, cancelled: bool = False) -> dict:
        """Compute summary dict from an image poll result.

        Returns a dict with:
          - ok: bool (original result ok flag)
          - message: str (error or summary text)
          - checked: int
          - completed: int
          - failed: int
          - deferred: int
          - cancelled: bool
          - should_refresh_table: bool
          - should_auto_poll: bool
        """
        if not bool(result.get("ok", False)):
            message = str(result.get("message", "Image jobs failed")).strip() or "Image jobs failed"
            return {
                "ok": False,
                "message": message,
                "checked": 0,
                "completed": 0,
                "failed": 0,
                "deferred": 0,
                "cancelled": False,
                "should_refresh_table": False,
                "should_auto_poll": False,
            }

        checked = int(result.get("checked", 0) or 0)
        completed = int(result.get("completed", 0) or 0)
        failed = int(result.get("failed", 0) or 0)
        deferred = int(result.get("deferred", 0) or 0)

        if cancelled:
            message = f"Stopped: {completed} completed · {failed} failed"
            return {
                "ok": True,
                "message": message,
                "checked": checked,
                "completed": completed,
                "failed": failed,
                "deferred": deferred,
                "cancelled": True,
                "should_refresh_table": True,
                "should_auto_poll": False,
            }

        if checked == 0 and manual:
            message = "No pending image jobs"
            return {
                "ok": True,
                "message": message,
                "checked": 0,
                "completed": 0,
                "failed": 0,
                "deferred": 0,
                "cancelled": False,
                "should_refresh_table": True,
                "should_auto_poll": False,
            }

        suffix = f" · {failed} failed" if failed else ""
        defer_suffix = f" · {deferred} waiting for background" if deferred else ""
        message = f"Image jobs: {completed} completed from {checked} checked{suffix}{defer_suffix}"

        should_auto_poll = manual and (checked > 0 or deferred > 0)

        return {
            "ok": True,
            "message": message,
            "checked": checked,
            "completed": completed,
            "failed": failed,
            "deferred": deferred,
            "cancelled": False,
            "should_refresh_table": checked > 0,
            "should_auto_poll": should_auto_poll,
        }

    def list_jobs_for_ui(self, *, from_ymd: str = "", to_ymd: str = "", limit: int = 5000) -> list[dict]:
        db_cfg = self._db_cfg_accessor()
        if not db_cfg:
            return []
        return list_image_jobs(db_cfg, from_ymd=from_ymd, to_ymd=to_ymd, limit=limit)

    def compute_row_spans(self, grouped_rows: list[dict]) -> list[dict]:
        """Compute row layout info for the image jobs table.

        Returns a list of row descriptors, each with:
          - type: "header" | "data"
          - group_index: index into grouped_rows (for data rows)
          - span: (row_span, col_span) for header rows, None for data rows
        """
        result: list[dict] = []
        last_batch = ""
        for i, g in enumerate(grouped_rows):
            batch_id = str(g.get("batchId", "")).strip()
            if batch_id and batch_id != last_batch:
                result.append({
                    "type": "header",
                    "batchId": batch_id,
                    "runDate": str(g.get("runDate", "")).strip(),
                    "span": (1, 7),  # span all columns
                })
                last_batch = batch_id
            result.append({
                "type": "data",
                "group_index": i,
                "span": None,
            })
        return result

    def build_image_job_rows(self, grouped_rows: list[dict], ui_colors: dict) -> list[dict]:
        """Build row data dicts for the image jobs table.

        Each returned dict contains all computed fields needed for cell population:
          profile_name, role, bg_uid, th_uid, bg_status, th_status,
          bg_color, th_color, bg_tip, th_tip, bg_out, th_out,
          bg_attempt, th_attempt, bg_enabled, th_enabled, row_meta.
        """
        rows: list[dict] = []
        for g in grouped_rows:
            profile_id = str(g.get("profileId", "")).strip()
            profile_name = str(g.get("profileName", "")).strip()
            role = str(g.get("role", "")).strip()
            batch_id = str(g.get("batchId", "")).strip()
            bg = g.get("bg") or {}
            th = g.get("th") or {}
            bg_status = str(bg.get("status", "")).strip().upper()
            th_status = str(th.get("status", "")).strip().upper()
            bg_out = str(bg.get("outputImagePath", "")).strip()
            th_out = str(th.get("outputImagePath", "")).strip()
            bg_err = str(bg.get("error", "")).strip()
            th_err = str(th.get("error", "")).strip()
            bg_attempt = int(bg.get("attemptCount", 0) or 0)
            th_attempt = int(th.get("attemptCount", 0) or 0)
            bg_uid = str(bg.get("jobUid", "")).strip()
            th_uid = str(th.get("jobUid", "")).strip()

            bg_color = ui_colors.get("text_muted", "#888888")
            if bg_status == "READY":
                bg_color = ui_colors.get("success_border", "#22c55e")
            elif bg_status == "FAILED":
                bg_color = ui_colors.get("danger_border", "#ef4444")
            elif bg_status in ("PENDING", "RUNNING"):
                bg_color = ui_colors.get("warning_border", "#f59e0b")

            th_color = ui_colors.get("text_muted", "#888888")
            if th_status == "READY":
                th_color = ui_colors.get("success_border", "#22c55e")
            elif th_status == "FAILED":
                th_color = ui_colors.get("danger_border", "#ef4444")
            elif th_status in ("PENDING", "RUNNING"):
                th_color = ui_colors.get("warning_border", "#f59e0b")

            bg_tip = "\n".join(
                [x for x in [f"BG: {bg_status or '-'}", f"Attempts: {bg_attempt}", bg_err] if str(x or "").strip()]
            ).strip()
            th_tip = "\n".join(
                [x for x in [f"TH: {th_status or '-'}", f"Attempts: {th_attempt}", th_err] if str(x or "").strip()]
            ).strip()

            row_meta = {"batchId": batch_id, "profileId": profile_id, "bgUid": bg_uid, "thUid": th_uid}

            rows.append({
                "profile_name": profile_name,
                "role": role,
                "bg_uid": bg_uid,
                "th_uid": th_uid,
                "bg_status": bg_status,
                "th_status": th_status,
                "bg_color": bg_color,
                "th_color": th_color,
                "bg_tip": bg_tip,
                "th_tip": th_tip,
                "bg_out": bg_out,
                "th_out": th_out,
                "bg_attempt": bg_attempt,
                "th_attempt": th_attempt,
                "bg_enabled": bool(bg_uid) and bg_status != "RUNNING",
                "th_enabled": bg_status == "READY" and th_status != "RUNNING",
                "row_meta": row_meta,
            })
        return rows

    def group_jobs_for_ui(self, *, from_ymd: str = "", to_ymd: str = "", limit: int = 5000) -> tuple[list[dict], bool]:
        """Return (grouped_rows, has_pending) for the image jobs table.

        Each grouped row dict contains: batchId, runDate, profileId, profileName,
        role, bg (job dict or None), th (job dict or None).
        """
        rows = self.list_jobs_for_ui(from_ymd=from_ymd, to_ymd=to_ymd, limit=limit)
        grouped: dict[tuple[str, str], dict] = {}
        for j in rows:
            batch_id = str(j.get("batchId", "")).strip()
            profile_id = str(j.get("profileId", "")).strip()
            if not batch_id or not profile_id:
                continue
            key = (batch_id, profile_id)
            g = grouped.get(key)
            if not g:
                profile = self._music_profile_by_id(profile_id) or {}
                grouped[key] = g = {
                    "batchId": batch_id,
                    "runDate": str(j.get("runDate", "")).strip(),
                    "profileId": profile_id,
                    "profileName": str(profile.get("name", "") or ""),
                    "role": str(j.get("channelRole", "")).strip(),
                    "bg": None,
                    "th": None,
                }
            kind = str(j.get("kind", "")).strip().lower()
            if kind == "background":
                g["bg"] = j
            elif kind == "thumbnail":
                g["th"] = j
        grouped_rows = list(grouped.values())
        grouped_rows.sort(key=lambda x: (str(x.get("batchId", "")), str(x.get("profileName", ""))))
        has_pending = False
        for g in grouped_rows:
            for _job_entry in (g.get("bg"), g.get("th")):
                st = str((_job_entry or {}).get("status", "")).strip().upper()
                if st in ("PENDING", "RUNNING"):
                    has_pending = True
                    break
            if has_pending:
                break
        return grouped_rows, has_pending

    # ------------------------------------------------------------------
    # Private helper methods (absorbed from controller)
    # ------------------------------------------------------------------

    def _ensure_batch_dirs(self, *, batch_id: str, run_label: str, ok_id: str, alt_id: str) -> dict | None:
        db_cfg = self._db_cfg_accessor()
        existing = get_batch_run_dirs_by_batch_id(db_cfg, batch_id)
        if str(existing.get("okDir", "")).strip():
            ok_dir = str(existing.get("okDir", "")).strip()
            alt_dir = str(existing.get("altDir", "")).strip() or ok_dir
            return {"okDir": ok_dir, "altDir": alt_dir}
        settings = self._music_settings()
        base_dir = str(settings.get("sunoOutputDir", "")).strip() or str(settings.get("downloadsDir", "")).strip()
        if not base_dir:
            self._log(f"[{time.strftime('%H:%M:%S')}] Image batch dirs skipped: output directory is missing")
            return None
        ok_profile = self._music_profile_by_id(ok_id)
        alt_profile = self._music_profile_by_id(alt_id)
        if not ok_profile or not alt_profile:
            return None
        out = plan_next_paired_run_dirs_by_label(
            base_dir,
            str(ok_profile.get("folderName", "")).strip(),
            str(alt_profile.get("folderName", "")).strip() or None,
            run_label,
        )
        ok_dir = str(out.get("okRunDir", "")).strip()
        alt_dir = str(out.get("altRunDir", "")).strip() or ok_dir
        if ok_dir:
            upsert_batch_run_dirs(db_cfg, batch_id=batch_id, ok_dir=ok_dir, alt_dir=alt_dir)
        return {"okDir": ok_dir, "altDir": alt_dir}

    def _ensure_existing_batch_dirs(self, *, batch_id: str) -> dict | None:
        db_cfg = self._db_cfg_accessor()
        existing = get_batch_run_dirs_by_batch_id(db_cfg, batch_id)
        if str(existing.get("okDir", "")).strip():
            ok_dir = str(existing.get("okDir", "")).strip()
            alt_dir = str(existing.get("altDir", "")).strip() or ok_dir
            return {"okDir": ok_dir, "altDir": alt_dir}
        found = get_latest_suno_output_dirs_by_batch_id(db_cfg, batch_id)
        if not bool(found.get("ok", False)):
            return None
        ok_dir = str(found.get("okDir", "")).strip()
        alt_dir = str(found.get("altDir", "")).strip() or ok_dir
        if ok_dir:
            upsert_batch_run_dirs(db_cfg, batch_id=batch_id, ok_dir=ok_dir, alt_dir=alt_dir)
        return {"okDir": ok_dir, "altDir": alt_dir}

    def _enqueue_batch_channel_jobs(
        self,
        *,
        batch_id: str,
        ymd: str,
        pair_index: int,
        profile_id: str,
        role: str,
        prompt: str | None = None,
        bg_samples: list[str] | None = None,
        thumb_samples: list[str] | None = None,
        exclude_thumb_preset_ids: list[str] | None = None,
        exclude_thumb_sample_paths: list[str] | None = None,
        skip_bg: bool = False,
    ) -> tuple[str | None, str | None]:
        db_cfg = self._db_cfg_accessor()
        settings = self._music_settings()
        profile = self._music_profile_by_id(profile_id)
        image_cfg = (profile or {}).get("imageConfig") if isinstance((profile or {}).get("imageConfig"), dict) else {}
        mode = str((image_cfg or {}).get("mode", "bg_thumb")).strip() or "bg_thumb"
        thumb_only = mode.lower().replace("-", "_") == "thumb_only"
        bg_random = bool(settings.get("imageBgRandom", False))
        thumb_random = bool(settings.get("imageThumbRandom", False))
        if isinstance(image_cfg, dict):
            v = image_cfg.get("backgroundRandom", None)
            if v is not None:
                bg_random = bool(v)
            v = image_cfg.get("thumbnailRandom", None)
            if v is not None:
                thumb_random = bool(v)
        bg_exists = get_image_job_by_key(db_cfg, batch_id=batch_id, profile_id=profile_id, kind="background")
        thumb_exists = get_image_job_by_key(db_cfg, batch_id=batch_id, profile_id=profile_id, kind="thumbnail")
        if skip_bg:
            if thumb_exists:
                return (None, None)
        else:
            if (thumb_only and thumb_exists) or (bg_exists and thumb_exists):
                return (None, None)
        manual_prompt = str(prompt or "").strip() if prompt is not None else ""
        profile_base_prompt = str((image_cfg or {}).get("basePrompt", "")).strip()
        global_base_prompt = str(settings.get("imagePrompt", "")).strip()
        base_prompt = manual_prompt or profile_base_prompt or global_base_prompt
        prompt_source = "manual" if manual_prompt else ("profile" if profile_base_prompt else ("global" if global_base_prompt else "preset"))
        if not base_prompt:
            preset = pick_least_used_preset(db_cfg, kind="background") if db_cfg else None
            base_prompt = str((preset or {}).get("prompt", "")).strip() or "cinematic lighting, high detail"
            prompt_source = "preset"
        bg_base = str((image_cfg or {}).get("backgroundPrompt", "")).strip() or base_prompt
        thumb_base = str((image_cfg or {}).get("thumbnailPrompt", "")).strip() or base_prompt
        bg_prompt = bg_base
        bg_no_text_instr = (
            "Do not generate any text, letters, numbers, typography, logos, watermarks, dates, titles, labels, stickers, or signage in the background image. "
            "No readable characters anywhere."
        )
        bg_prompt = f"{bg_prompt}\n\n{bg_no_text_instr}".strip()
        thumb_prompt = thumb_base
        thumb_preset_id: str | None = None
        if not thumb_exists:
            _exclude_ids_int = [int(x) for x in (exclude_thumb_preset_ids or []) if x]
            thumb_preset = pick_least_used_preset(db_cfg, kind="thumbnail", exclude_ids=_exclude_ids_int or None) if db_cfg else None
            if thumb_preset:
                thumb_preset_id = str(thumb_preset.get("id", ""))
            thumb_style_prompt = str((thumb_preset or {}).get("prompt", "")).strip()
            style_instr = (
                "Generate ONLY typography/text on a pure black background. Do not add cars, scenes, gradients, textures, frames, or extra graphics. "
                "Use the embedded style reference image (in the corner box) only to match typography/text style. "
                "Keep everything except the text pure black. "
                "Text size rules (16:9): the rendered text block (including any glow/outer pixels) should be about 38–42% of the frame width and 18–22% of the frame height, "
                "centered horizontally and positioned slightly above the vertical middle (center Y ≈ 45% of frame height)."
            )
            merged = f"{thumb_base}\n\n{thumb_style_prompt}".strip() if thumb_style_prompt else thumb_base
            thumb_prompt = f"{merged}\n\n{style_instr}".strip()
        include_titles = (image_cfg or {}).get("thumbnailIncludeTrackTitles", None)
        if include_titles is not None and bool(include_titles) and db_cfg and not thumb_exists:
            try:
                songs = list_songs_by_batch_id(db_cfg, str(batch_id or "").strip())
            except Exception:
                songs = []
            titles = [str(s.get("title", "")).strip() for s in (songs or []) if isinstance(s, dict) and str(s.get("title", "")).strip()]
            if titles:
                titles = titles[:10]
                safe_titles = [t[:80] for t in titles]
                lines = "\n".join([f"- {t}" for t in safe_titles])
                instr = (
                    "Include the following track titles as the main typography content. "
                    "Make the layout readable and balanced for a vertical list. "
                    "Leave comfortable padding on all sides and keep good contrast. "
                    "Do not add any other words beyond the track titles.\n\n"
                    f"Track titles:\n{lines}"
                )
                thumb_prompt = f"{thumb_prompt}\n\n{instr}".strip()
        profile_bg_samples = (image_cfg or {}).get("backgroundSamples") if isinstance((image_cfg or {}).get("backgroundSamples"), list) else []
        profile_thumb_samples = (image_cfg or {}).get("thumbnailSamples") if isinstance((image_cfg or {}).get("thumbnailSamples"), list) else []
        bg = (
            []
            if bool(bg_random) and bg_samples is None
            else [
                str(x).strip()
                for x in (
                    bg_samples
                    if bg_samples is not None
                    else (profile_bg_samples if profile_bg_samples else list(settings.get("imageBgSamples") or []))
                )
                if str(x).strip()
            ]
        )
        excluded_thumb_paths = {str(p).strip() for p in (exclude_thumb_sample_paths or []) if str(p).strip()}
        th = (
            []
            if bool(thumb_random) and thumb_samples is None
            else [
                str(x).strip()
                for x in (
                    thumb_samples
                    if thumb_samples is not None
                    else (profile_thumb_samples if profile_thumb_samples else list(settings.get("imageThumbSamples") or []))
                )
                if str(x).strip() and str(x).strip() not in excluded_thumb_paths
            ]
        )
        thumb_input_path = ""
        if thumb_only and not bool(bg_random):
            usable = [p for p in bg if p and Path(p).exists()]
            picked = pick_least_used_value(db_cfg, kind="bg_sample", values=usable) if usable else ""
            thumb_input_path = str(picked or "").strip()
        if not bg_exists and not thumb_only and not skip_bg:
            upsert_image_job(
                db_cfg,
                {
                    "jobUid": f"img-{batch_id}-{profile_id}-background",
                    "batchId": batch_id,
                    "runDate": ymd,
                    "pairIndex": int(pair_index or 0),
                    "profileId": profile_id,
                    "channelRole": str(role or "").strip().upper(),
                    "kind": "background",
                    "status": "PENDING",
                    "prompt": bg_prompt,
                    "promptSource": prompt_source,
                    "samplePaths": bg,
                    "attemptCount": 0,
                },
            )
        if not thumb_exists:
            upsert_image_job(
                db_cfg,
                {
                    "jobUid": f"img-{batch_id}-{profile_id}-thumbnail",
                    "batchId": batch_id,
                    "runDate": ymd,
                    "pairIndex": int(pair_index or 0),
                    "profileId": profile_id,
                    "channelRole": str(role or "").strip().upper(),
                    "kind": "thumbnail",
                    "status": "PENDING",
                    "prompt": thumb_prompt,
                    "promptSource": prompt_source,
                    "samplePaths": th,
                    "inputImagePath": thumb_input_path,
                    "attemptCount": 0,
                },
            )
        thumb_sample_return = th[0] if th else ""
        return (thumb_preset_id, thumb_sample_return)

    # ------------------------------------------------------------------
    # Methods absorbed from MainWindow image domain
    # ------------------------------------------------------------------

    def on_generate_now_clicked(
        self,
        *,
        batch_rows: list[dict],
        prompt: str = "",
        bg_samples: list[str] | None = None,
        thumb_samples: list[str] | None = None,
        bg_random: bool = False,
        thumb_random: bool = False,
        bg_dir: str = "",
        thumb_dir: str = "",
    ) -> dict:
        """Validate and enqueue image generation jobs for selected batches.

        Returns a result dict with:
          - ok: bool
          - warning: str (non-empty if validation failed; caller should show QMessageBox)
          - message: str (status text for success)
          - jobs: int (number of jobs enqueued)
          - batches: int (number of batches processed)
          - skipped: int (number of batches skipped)
        """
        db_cfg = self._db_cfg_accessor()
        if not db_cfg:
            return {"ok": False, "warning": "Postgres is not configured."}
        if not self._generation_proxy:
            return {"ok": False, "warning": "Image generation unavailable: not connected to Platform API."}
        if not batch_rows:
            return {"ok": False, "warning": "Select at least 1 batch in the Batches list before generating images."}

        # Validate background samples
        resolved_bg: list[str] = []
        if bg_random:
            from ...services.image_generation import list_images_in_folder
            bg_candidates = [str(r.get("filePath", "")).strip() for r in list_images_in_folder(bg_dir) if str(r.get("filePath", "")).strip()]
            if not bg_candidates:
                return {"ok": False, "warning": "Background Random is enabled, but the background samples folder has no images."}
        else:
            resolved_bg = [s for s in (bg_samples or []) if s and Path(s).exists()]
            if not resolved_bg:
                return {"ok": False, "warning": "No usable background samples found. Please re-select background samples (existing image files) or enable Random."}

        # Validate thumbnail samples
        resolved_thumb: list[str] = []
        if thumb_random:
            from ...services.image_generation import list_images_in_folder
            thumb_candidates = [str(r.get("filePath", "")).strip() for r in list_images_in_folder(thumb_dir) if str(r.get("filePath", "")).strip()]
            if not thumb_candidates:
                return {"ok": False, "warning": "Thumbnail Random is enabled, but the thumbnail samples folder has no images."}
        else:
            resolved_thumb = [s for s in (thumb_samples or []) if s and Path(s).exists()]
            if not resolved_thumb:
                return {"ok": False, "warning": "No usable thumbnail samples found. Please re-select thumbnail samples (existing image files) or enable Random."}

        # Reset cancel flag and enqueue
        self._image_cancel_requested = False
        result = self.enqueue_manual(
            batches=batch_rows,
            prompt=str(prompt or "").strip(),
            bg_samples=resolved_bg,
            thumb_samples=resolved_thumb,
        )
        if not bool(result.get("ok", False)):
            return {"ok": False, "warning": str(result.get("message", "Failed to enqueue image jobs"))}

        jobs = int(result.get("jobs", 0) or 0)
        batches = int(result.get("batches", 0) or 0)
        skipped = int(result.get("skipped", 0) or 0)
        suffix = f" · skipped {skipped}" if skipped else ""
        message = f"Enqueued {jobs} job(s) across {batches} batch(es){suffix}"
        self._set_image_status(message)
        self.trigger_image_poll(manual=True, max_jobs=8)
        return {"ok": True, "warning": "", "message": message, "jobs": jobs, "batches": batches, "skipped": skipped}

    def on_generate_thumbnails_clicked(self) -> dict:
        """Validate and enqueue missing thumbnail jobs.

        Returns a result dict with:
          - ok: bool
          - warning: str (non-empty if validation failed)
          - info: str (non-empty if nothing to do - caller should show info dialog)
          - message: str (status text for success)
          - enqueued: int
        """
        db_cfg = self._db_cfg_accessor()
        if not db_cfg:
            return {"ok": False, "warning": "Postgres is not configured."}
        if not self._generation_proxy:
            return {"ok": False, "warning": "Image generation unavailable: not connected to Platform API."}
        result = self.enqueue_missing_thumbnails()
        if not bool(result.get("ok", False)):
            return {"ok": False, "info": str(result.get("message", "Nothing to do")), "warning": ""}
        count = int(result.get("enqueued", 0) or 0)
        message = f"Enqueued {count} thumbnail job(s)"
        self._set_image_status(message)
        self.trigger_image_poll(manual=True, max_jobs=8)
        return {"ok": True, "warning": "", "info": "", "message": message, "enqueued": count}

    def refresh_jobs_table(self, *, from_ymd: str = "", to_ymd: str = "") -> dict:
        """Retrieve image jobs data for table display.

        Returns a dict with:
          - grouped_rows: list[dict] — grouped job rows
          - has_pending: bool — whether any jobs are pending/running
          - row_layout: list[dict] — computed row spans for table layout
          - row_data_list: list[dict] — computed row display data
        """
        grouped_rows, has_pending = self.group_jobs_for_ui(from_ymd=from_ymd, to_ymd=to_ymd, limit=5000)
        row_layout = self.compute_row_spans(grouped_rows)
        ui_colors: dict[str, str] = {}  # Will be passed by caller if needed
        return {
            "grouped_rows": grouped_rows,
            "has_pending": has_pending,
            "row_layout": row_layout,
        }

    def on_retry_failed(self, job_uids: list[str]) -> None:
        """Retry all specified failed image jobs."""
        uids = [str(x).strip() for x in (job_uids or []) if str(x).strip()]
        if not uids:
            return
        self.retry_jobs(uids)


# ------------------------------------------------------------------
# Module-level helpers (absorbed from controller module)
# ------------------------------------------------------------------


def _batch_run_date(batch_id: str) -> str:
    m = re.match(r"^batch-(\d{4}-\d{2}-\d{2})", str(batch_id or "").strip())
    return str(m.group(1)) if m else ""


def _batch_pair_index(batch_id: str) -> int:
    m = re.match(r"^batch-\d{4}-\d{2}-\d{2}-(\d+)-\d+$", str(batch_id or "").strip())
    if not m:
        return 0
    try:
        return max(0, int(m.group(1)) - 1)
    except Exception:
        return 0
