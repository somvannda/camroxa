"""Upload generated music and artwork to Backblaze for public streaming."""

from __future__ import annotations

import asyncio
import logging
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from platform_api.models.enums import ImageKind
from platform_api.repositories.streaming_repo import (
    B2_BACKFILL_ALERT_ADVISORY_LOCK_ID,
    B2_BACKFILL_ALERT_SETTING_KEY,
    B2_BACKFILL_SWEEP_ADVISORY_LOCK_ID,
    B2_BACKFILL_SWEEP_SETTING_KEY,
    StreamingRepository,
)
from platform_api.services.storage_service import StorageService, StorageServiceError
from platform_api.services.mp3_duration_header import ensure_mp3_duration_header_async
from platform_api.services.streaming_config_service import resolve_streaming_storage_config
from platform_api.services.streaming_slug import slugify
from platform_api.services.music_genre_utils import parse_suno_clip_tags, resolve_stream_genres
from platform_api.services.suno_audio_resolver import (
    SunoTaskDownloadUrls,
    download_suno_mp3_bytes,
    fetch_timestamped_lrc_with_pool,
    normalize_http_download_url,
    poll_suno_generate_with_pool,
    refresh_suno_task_download_urls,
    variant_url_candidates,
)
from platform_api.services.audio_package_service import AudioPackageService
from platform_api.services.audio_packager import GCM_MIME, looks_like_camxora_audio
from platform_api.services.audio_preview_trim import PreviewTrimError, trim_audio_bytes
from platform_api.services.web_music_previews import PREVIEW_SECONDS
from platform_api.services.suno_lrc import looks_like_lrc
from platform_api.services.web_music_storage_keys import (
    usable_web_music_b2_key,
    web_music_object_key,
)


import httpx

logger = logging.getLogger(__name__)

WEB_MUSIC_B2_BACKFILL_COOLDOWN_S = 20.0

_IMAGE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; Camxora-Platform/1.0)",
    "Accept": "image/*,*/*;q=0.8",
}

_SWEEP_CONCURRENCY = 3
_RETRY_SWEEP_ERRORS_KEPT = 10
_RETRY_SWEEP_HEARTBEAT_S = 20.0
_RETRY_SWEEP_STALE_S = 120.0

# Background auto-capture retrier (env-tunable, prod defaults sane). It re-runs
# failed mp3 uploads until Suno/B2 capture succeeds, without touching the manual
# admin sweep (which is skipped while one is running).
_AUTO_RETRY_ENABLED = os.getenv("STREAMING_AUTO_RETRY_ENABLED", "1") != "0"
_AUTO_RETRY_INTERVAL_S = float(os.getenv("STREAMING_AUTO_RETRY_INTERVAL_S", "300"))
_AUTO_RETRY_MAX_AGE_HOURS = int(os.getenv("STREAMING_AUTO_RETRY_MAX_AGE_HOURS", "48"))
# attempt_count grows by 2 per failed retry (pending mark + failed mark), so a
# cap of 7 ≈ up to 3 auto re-attempts per job.
_AUTO_RETRY_MAX_ATTEMPT_COUNT = int(os.getenv("STREAMING_AUTO_RETRY_MAX_ATTEMPT_COUNT", "7"))
_AUTO_RETRY_PASS_LIMIT = int(os.getenv("STREAMING_AUTO_RETRY_PASS_LIMIT", "20"))
_AUTO_RETRY_CONCURRENCY = int(os.getenv("STREAMING_AUTO_RETRY_CONCURRENCY", "3"))
# Session advisory lock making each pass single-winner across uvicorn workers.
_AUTO_RETRY_ADVISORY_LOCK = 730000002

# Web-music companion-asset recovery (wav/lrc/srt/encrypted package). WAV needs a
# Suno conversion per variant (~30-60s), so it is capped hard per cycle.
_ASSET_RECOVERY_ENABLED = os.getenv("WEB_MUSIC_ASSET_RECOVERY_ENABLED", "1") != "0"
_ASSET_PASS_TASK_LIMIT = int(os.getenv("WEB_MUSIC_ASSET_PASS_TASK_LIMIT", "8"))
_ASSET_WAV_MAX_PER_PASS = int(os.getenv("WEB_MUSIC_ASSET_WAV_MAX_PER_PASS", "2"))
_ASSET_LRC_MAX_PER_PASS = int(os.getenv("WEB_MUSIC_ASSET_LRC_MAX_PER_PASS", "6"))
_ASSET_SRT_ENABLED = os.getenv("WEB_MUSIC_ASSET_SRT_ENABLED", "1") != "0"

# Durable B2 backfill sweep. The periodic loop claims a single winner per
# interval across uvicorn workers, and the failure alert is rate-limited so a
# chronic (often transient) companion-asset failure cannot page every pass.
_B2_BACKFILL_ALERT_COOLDOWN_S = float(os.getenv("B2_BACKFILL_ALERT_COOLDOWN_S", "21600"))

# Web-music MP3 capture. Web-music uploads do not create stream_upload_jobs rows,
# so the desktop auto-retry cannot see them. This pass re-runs the web-music B2
# backfill for tasks that still have a Suno audio URL but no B2 MP3.
_WEB_MUSIC_MP3_RECOVERY_ENABLED = os.getenv("WEB_MUSIC_MP3_RECOVERY_ENABLED", "1") != "0"
_WEB_MUSIC_MP3_PASS_LIMIT = int(os.getenv("WEB_MUSIC_MP3_PASS_LIMIT", "10"))
_WEB_MUSIC_MP3_MAX_AGE_HOURS = int(os.getenv("WEB_MUSIC_MP3_MAX_AGE_HOURS", "168"))
_WEB_MUSIC_MP3_CONCURRENCY = int(os.getenv("WEB_MUSIC_MP3_CONCURRENCY", "3"))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _iso_created_at(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    text = str(value).strip()
    return text or None


_LRC_TIMESTAMP_RE = re.compile(
    r"\[(\d{1,3}):(\d{1,2})(?:[.:](\d{1,3}))?\]\s*(.*)"
)


def _lrc_text_to_srt(lrc: str) -> str:
    """Convert LRC subtitles to SRT text (mirrors admin download conversion)."""
    entries: list[tuple[float, str]] = []
    for raw in str(lrc or "").splitlines():
        match = _LRC_TIMESTAMP_RE.match(raw.strip())
        if not match:
            continue
        minutes, seconds, millis, text = match.groups()
        cleaned = str(text or "").strip()
        if not cleaned:
            continue
        total = int(minutes) * 60 + int(seconds)
        if millis:
            if len(millis) == 1:
                total += int(millis) / 10.0
            elif len(millis) == 2:
                total += int(millis) / 100.0
            else:
                total += int(millis[:3]) / 1000.0
        entries.append((max(0.0, float(total)), cleaned))
    if not entries:
        return ""
    chunks: list[str] = []

    def _clock(total_ms: int) -> str:
        hours, rem = divmod(total_ms, 3_600_000)
        minutes, rem = divmod(rem, 60_000)
        secs, millis = divmod(rem, 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    for index, (start, text) in enumerate(entries):
        end = entries[index + 1][0] if index + 1 < len(entries) else start + 3.0
        if end <= start:
            end = start + 1.5
        start_ms = max(0, int(round(start * 1000)))
        end_ms = max(start_ms + 200, int(round(end * 1000)))
        chunks.append(f"{index + 1}\n{_clock(start_ms)} --> {_clock(end_ms)}\n{text}\n")
    return "\n".join(chunks)


class _FailedMp3RetrySweep:
    """DB-backed "retry all failed mp3" sweep shared across uvicorn workers.

    Prod runs camxora-api with --workers 4, so sweep state cannot live in one
    process. Ownership is claimed atomically in `system_settings` guarded by a
    Postgres advisory xact lock; progress + heartbeat are written there so any
    worker answers /status consistently. If the owning worker dies, the
    heartbeat goes stale and a later click reclaims and resumes.
    """

    def __init__(self) -> None:
        self._task: asyncio.Task[Any] | None = None
        self._heartbeat_task: asyncio.Task[Any] | None = None
        self._pool: Any = None
        self._cancel = False
        self.total = 0
        self.scanned = 0
        self.succeeded = 0
        self.still_failed = 0
        self.last_errors: list[dict[str, str]] = []
        self.started_at: str | None = None

    def _snapshot(self, running: bool, *, finished: bool = False) -> dict[str, Any]:
        return {
            "running": running,
            "started_at": self.started_at,
            "finished_at": _now_iso() if finished else None,
            "total": self.total,
            "scanned": self.scanned,
            "succeeded": self.succeeded,
            "still_failed": self.still_failed,
            "heartbeat_at": _now_iso(),
            "last_errors": list(self.last_errors),
        }

    async def status(self, pool: Any) -> dict[str, Any]:
        repo = StreamingRepository(pool)
        # Live DB counters so the admin page can always answer "how many failed
        # are left" and "how many were recovered by retries" (any worker).
        try:
            failed_mp3_now = await repo.count_failed_mp3_jobs()
            retried_success_total = await repo.count_retried_success_jobs()
        except Exception:
            logger.exception("Upload-job live counters failed (non-fatal)")
            failed_mp3_now = 0
            retried_success_total = 0
        state = await repo.get_retry_sweep_state()
        if not state:
            return {
                "running": False,
                "started_at": None,
                "finished_at": None,
                "total": 0,
                "scanned": 0,
                "succeeded": 0,
                "still_failed": 0,
                "remaining": 0,
                "failed_mp3_now": failed_mp3_now,
                "retried_success_total": retried_success_total,
                "last_errors": [],
            }
        stale = _state_is_stale(state)
        running = bool(state.get("running")) and not stale
        total = int(state.get("total") or 0)
        scanned = int(state.get("scanned") or 0)
        return {
            "running": running,
            "stale": stale,
            "started_at": state.get("started_at"),
            "finished_at": state.get("finished_at"),
            "total": total,
            "scanned": scanned,
            "succeeded": int(state.get("succeeded") or 0),
            "still_failed": int(state.get("still_failed") or 0),
            "remaining": max(0, total - scanned),
            "failed_mp3_now": failed_mp3_now,
            "retried_success_total": retried_success_total,
            "last_errors": state.get("last_errors") or [],
        }

    async def start(self, pool: Any) -> dict[str, Any]:
        repo = StreamingRepository(pool)
        if self._task and not self._task.done():
            return {"started": False, "running": True, "total": self.total}
        claimed = await repo.claim_retry_sweep(
            self._snapshot(running=True), stale_after_s=_RETRY_SWEEP_STALE_S
        )
        if not claimed:
            state = await repo.get_retry_sweep_state() or {}
            return {
                "started": False,
                "running": True,
                "total": int(state.get("total") or 0),
            }
        job_ids = await repo.list_failed_mp3_job_ids()
        if not job_ids:
            self.started_at = None
            await repo.upsert_retry_sweep_state(self._snapshot(running=False, finished=True))
            return {"started": False, "running": False, "total": 0}
        self._pool = pool
        self.total = len(job_ids)
        self.scanned = 0
        self.succeeded = 0
        self.still_failed = 0
        self.last_errors = []
        self.started_at = _now_iso()
        self._cancel = False
        await repo.upsert_retry_sweep_state(self._snapshot(running=True))
        self._task = asyncio.create_task(self._run(pool, list(job_ids)))
        return {"started": True, "running": True, "total": self.total}

    async def _heartbeat_loop(self) -> None:
        try:
            while not self._cancel:
                await asyncio.sleep(_RETRY_SWEEP_HEARTBEAT_S)
                if self._cancel:
                    break
                await StreamingRepository(self._pool).upsert_retry_sweep_state(
                    self._snapshot(running=True)
                )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Retry sweep heartbeat failed (non-fatal)")

    async def _run(self, pool: Any, job_ids: list[UUID]) -> None:
        service = StreamingUploadService(pool)
        semaphore = asyncio.Semaphore(_SWEEP_CONCURRENCY)
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        async def retry_one(job_id: UUID) -> None:
            async with semaphore:
                ok = False
                error = ""
                try:
                    await service.retry_failed_job(job_id)
                    ok = True
                except Exception as exc:  # retry_failed_job re-raises after marking job failed
                    error = str(exc) or exc.__class__.__name__
                self.scanned += 1
                if ok:
                    self.succeeded += 1
                else:
                    self.still_failed += 1
                    if len(self.last_errors) >= _RETRY_SWEEP_ERRORS_KEPT:
                        self.last_errors.pop(0)
                    self.last_errors.append({"job_id": str(job_id), "error": error[:300]})
                if self.scanned % 50 == 0:
                    logger.info(
                        "Failed-mp3 retry sweep progress %s/%s (ok=%s failed=%s)",
                        self.scanned,
                        self.total,
                        self.succeeded,
                        self.still_failed,
                    )

        try:
            await asyncio.gather(*(retry_one(job_id) for job_id in job_ids))
        finally:
            if self._heartbeat_task:
                self._cancel = True
                self._heartbeat_task.cancel()
                try:
                    await self._heartbeat_task
                except (asyncio.CancelledError, Exception):
                    pass
                self._heartbeat_task = None
            try:
                await StreamingRepository(pool).upsert_retry_sweep_state(
                    self._snapshot(running=False, finished=True)
                )
            except Exception:
                logger.exception("Failed to persist retry sweep final state")
            logger.info(
                "Failed-mp3 retry sweep finished: scanned=%s ok=%s failed=%s",
                self.scanned,
                self.succeeded,
                self.still_failed,
            )


def _state_is_stale(state: dict[str, Any]) -> bool:
    if not state.get("running"):
        return False
    raw = state.get("heartbeat_at")
    if not raw:
        return True
    try:
        heartbeat = datetime.fromisoformat(str(raw))
    except ValueError:
        return True
    return (datetime.now(timezone.utc) - heartbeat).total_seconds() > _RETRY_SWEEP_STALE_S


_retry_sweep = _FailedMp3RetrySweep()


class StreamingUploadService:
    def __init__(self, pool: Any) -> None:
        self._pool = pool
        self._repo = StreamingRepository(pool)
        self._web_music_backfill_inflight: set[tuple[str, str]] = set()
        self._web_music_backfill_last: dict[tuple[str, str], float] = {}

    async def _encrypt_ingested_mp3(
        self,
        plaintext: bytes,
        *,
        subject_type: str,
        subject_id: UUID,
        variant: str,
        storage_key: str,
        storage: Any,
        null_suno_urls: bool,
    ) -> None:
        try:
            base_key = str(storage_key).rsplit(".mp3", 1)[0]
            await AudioPackageService(self._pool).package_plaintext(
                plaintext,
                subject_type=subject_type,
                subject_id=subject_id,
                variant=variant,
                base_key=base_key,
                storage=storage,
                null_suno_urls=null_suno_urls,
                source_key=storage_key,
            )
        except Exception as exc:
            logger.warning(
                "Audio packaging failed subject_type=%s id=%s variant=%s: %s",
                subject_type,
                subject_id,
                variant,
                exc,
            )

    async def _encrypt_ingested_mp3(
        self,
        plaintext: bytes,
        *,
        subject_type: str,
        subject_id: UUID,
        variant: str,
        storage_key: str,
        storage: Any,
        null_suno_urls: bool,
    ) -> None:
        try:
            base_key = str(storage_key).rsplit(".mp3", 1)[0]
            await AudioPackageService(self._pool).package_plaintext(
                plaintext,
                subject_type=subject_type,
                subject_id=subject_id,
                variant=variant,
                base_key=base_key,
                storage=storage,
                null_suno_urls=null_suno_urls,
                source_key=storage_key,
            )
        except Exception as exc:
            logger.warning(
                "Audio packaging failed subject_type=%s id=%s variant=%s: %s",
                subject_type,
                subject_id,
                variant,
                exc,
            )

    def schedule_suno_streaming_upload(self, *, suno_task_id: UUID) -> None:
        asyncio.create_task(self._run_suno_streaming_upload(suno_task_id))

    def schedule_web_music_b2_backfill(self, *, suno_task_id: UUID, variant: str | None = None) -> None:
        """Retry Backblaze upload when playback/download hits Suno fallback."""
        token = (str(suno_task_id), str(variant or "*"))
        if token in self._web_music_backfill_inflight:
            return
        now = time.monotonic()
        last = self._web_music_backfill_last.get(token, 0.0)
        if last and (now - last) < WEB_MUSIC_B2_BACKFILL_COOLDOWN_S:
            return
        self._web_music_backfill_inflight.add(token)
        self._web_music_backfill_last[token] = now

        async def _run() -> None:
            try:
                await self._run_web_music_b2_backfill(suno_task_id, variant)
            finally:
                self._web_music_backfill_inflight.discard(token)

        asyncio.create_task(_run())

    async def _run_web_music_b2_backfill(self, suno_task_id: UUID, variant: str | None) -> None:
        try:
            context = await self._repo.get_suno_stream_context(suno_task_id)
            if not context or str(context.get("source") or "").strip().lower() != "web_music":
                return
            row = await self._pool.fetchrow(
                """
                SELECT b2_storage_key_ok, b2_storage_key_alt,
                       package_status_ok, package_status_alt
                FROM suno_tasks
                WHERE id = $1
                """,
                suno_task_id,
            )
            if row is None:
                return
            refreshed = await self._refresh_task_download_urls(context)
            variants: list[str] = []
            if variant in {"ok", "alt"}:
                variants = [variant]
            else:
                variants = ["ok", "alt"]
            for key in variants:
                pkg_col = "package_status_ok" if key == "ok" else "package_status_alt"
                if str(row.get(pkg_col) or "") == "ready":
                    continue
                b2_col = "b2_storage_key_ok" if key == "ok" else "b2_storage_key_alt"
                existing = usable_web_music_b2_key(row.get(b2_col), suno_task_id)
                if existing:
                    await self._package_existing_web_music_mp3(
                        suno_task_id=suno_task_id,
                        variant=key,
                        storage_key=existing,
                    )
                    continue
                source = normalize_http_download_url(
                    refreshed.audio_url_ok if key == "ok" else refreshed.audio_url_alt
                ) or normalize_http_download_url(
                    context.get("audio_url_ok") if key == "ok" else context.get("audio_url_alt")
                )
                if not source:
                    continue
                await self._upload_web_music_variant(
                    context=context,
                    variant=key,
                    source_url=source,
                    refreshed=refreshed,
                )
        except Exception as exc:
            logger.warning("Web music B2 backfill failed task=%s: %s", suno_task_id, exc)

    async def _package_existing_web_music_mp3(
        self,
        *,
        suno_task_id: UUID,
        variant: str,
        storage_key: str,
    ) -> None:
        config = await resolve_streaming_storage_config(self._pool)
        if not config.configured:
            return
        storage = StorageService.from_config(config)
        data = await storage.download_bytes(key=storage_key)
        if not data:
            return
        await self._encrypt_ingested_mp3(
            data,
            subject_type="suno_task",
            subject_id=suno_task_id,
            variant=variant,
            storage_key=storage_key,
            storage=storage,
            null_suno_urls=True,
        )

    async def _run_suno_streaming_upload(self, suno_task_id: UUID) -> None:
        try:
            context = await self._repo.get_suno_stream_context(suno_task_id)
            if not context:
                return

            source = str(context.get("source") or "").strip().lower()
            is_web_music = source == "web_music"

            if not is_web_music and not context.get("song_id"):
                return

            refreshed = await self._refresh_task_download_urls(context)
            audio_ok = normalize_http_download_url(
                refreshed.audio_url_ok or context.get("audio_url_ok")
            )
            audio_alt = normalize_http_download_url(
                refreshed.audio_url_alt or context.get("audio_url_alt")
            )
            if refreshed.refreshed and (refreshed.audio_url_ok or refreshed.audio_url_alt):
                await self._persist_refreshed_audio_urls(
                    suno_task_id=suno_task_id,
                    refreshed=refreshed,
                )
            if audio_ok:
                if is_web_music:
                    await self._upload_web_music_variant(
                        context=context,
                        variant="ok",
                        source_url=audio_ok,
                        refreshed=refreshed,
                    )
                else:
                    await self._upload_mp3_variant(
                        context=context,
                        variant="ok",
                        source_url=audio_ok,
                        refreshed=refreshed,
                    )
            if audio_alt:
                if is_web_music:
                    await self._upload_web_music_variant(
                        context=context,
                        variant="alt",
                        source_url=audio_alt,
                        refreshed=refreshed,
                    )
                else:
                    await self._upload_mp3_variant(
                        context=context,
                        variant="alt",
                        source_url=audio_alt,
                        refreshed=refreshed,
                    )
        except Exception as exc:
            logger.exception("Streaming upload failed for suno_task_id=%s: %s", suno_task_id, exc)

    async def _refresh_task_download_urls(self, context: dict[str, Any]) -> SunoTaskDownloadUrls:
        external_task_id = str(context.get("external_task_id") or "").strip()
        if not external_task_id:
            return SunoTaskDownloadUrls()
        try:
            return await refresh_suno_task_download_urls(
                external_task_id,
                poll_status=lambda task_id: poll_suno_generate_with_pool(self._pool, task_id),
            )
        except Exception as exc:
            logger.warning(
                "Unable to refresh Suno download URLs for external_task_id=%s: %s",
                external_task_id,
                str(exc)[:200],
            )
            return SunoTaskDownloadUrls()

    async def _persist_refreshed_audio_urls(
        self,
        *,
        suno_task_id: UUID,
        refreshed: SunoTaskDownloadUrls,
    ) -> None:
        await self._pool.execute(
            """
            UPDATE suno_tasks
            SET audio_url_ok = CASE WHEN $2 <> '' THEN $2 ELSE audio_url_ok END,
                audio_url_alt = CASE WHEN $3 <> '' THEN $3 ELSE audio_url_alt END,
                audio_id_ok = CASE WHEN $4 <> '' THEN $4 ELSE audio_id_ok END,
                audio_id_alt = CASE WHEN $5 <> '' THEN $5 ELSE audio_id_alt END,
                updated_at = NOW()
            WHERE id = $1
            """,
            suno_task_id,
            refreshed.audio_url_ok,
            refreshed.audio_url_alt,
            refreshed.audio_id_ok,
            refreshed.audio_id_alt,
        )

    async def _download_mp3_with_recovery(
        self,
        *,
        external_task_id: str,
        audio_id: str,
        primary_url: str,
        fallback_urls: list[str],
    ) -> bytes:
        """Download the MP3, falling back to the provider's Recovery Audio endpoint.

        The provider's temp hosts expire within hours; recovery re-mints a fresh
        playable link (scoped to the key that generated the task), so a late B2
        backup can still succeed.
        """
        try:
            return await download_suno_mp3_bytes(primary_url, fallback_urls=fallback_urls)
        except Exception as exc:
            task_id = str(external_task_id or "").strip()
            clip_id = str(audio_id or "").strip()
            if not task_id or not clip_id:
                raise
            from platform_api.services.suno_audio_resolver import recover_suno_task_download_urls

            try:
                mapping = await recover_suno_task_download_urls(self._pool, task_id)
            except Exception:
                raise exc
            recovered = str(mapping.get(clip_id) or "").strip()
            if not recovered:
                raise
            logger.info(
                "Recovered expired MP3 via provider recovery task=%s clip=%s", task_id, clip_id
            )
            return await download_suno_mp3_bytes(recovered)

    async def _upload_mp3_variant(
        self,
        *,
        context: dict[str, Any],
        variant: str,
        source_url: str,
        refreshed: SunoTaskDownloadUrls | None = None,
    ) -> None:
        user_id = UUID(str(context["user_id"]))
        song_id = UUID(str(context["song_id"])) if context.get("song_id") else None
        batch_id = UUID(str(context["batch_id"])) if context.get("batch_id") else None
        suno_task_id = UUID(str(context["suno_task_id"]))

        if variant == "alt":
            album_name = str(context.get("alt_album") or context.get("song_album") or "Alternate Album").strip()
            channel_role = "alt"
        else:
            album_name = str(context.get("ok_album") or context.get("song_album") or "Album").strip()
            channel_role = "ok"

        title = str(context.get("song_title") or "Untitled").strip() or "Untitled"
        plain_lyrics = str(context.get("song_lyrics") or "").strip() or None
        album_slug = slugify(album_name, fallback="album")
        song_slug = slugify(title, fallback="track")
        storage_key = f"{user_id}/{album_slug}/{song_slug}-{variant}.mp3"

        # Idempotency: skip if this task+variant is already archived to B2.
        # Repeated callbacks/reconciles were re-creating jobs for the same track.
        _already_archived = await self._pool.fetchval(
            """
            SELECT 1 FROM stream_tracks
            WHERE suno_task_id = $1 AND variant = $2
              AND COALESCE(storage_key, '') <> ''
            LIMIT 1
            """,
            suno_task_id,
            variant,
        )
        if _already_archived:
            return

        # Idempotency (in flight): a pending job, or one that failed moments ago,
        # means this task+variant is already being captured. Re-delivered Suno
        # callbacks and desktop reconcile polling used to stack duplicate jobs
        # here (observed: dozens per task), which then re-downloaded expired Suno
        # URLs and surfaced as recurring 404s.
        if await self._repo.has_active_upload_job(
            suno_task_id=suno_task_id,
            kind=f"mp3_{variant}",
        ):
            return

        job_id = await self._repo.create_upload_job(
            user_id=user_id,
            kind=f"mp3_{variant}",
            song_id=song_id,
            batch_id=batch_id,
            suno_task_id=suno_task_id,
            source_url=normalize_http_download_url(source_url) or None,
            storage_key=storage_key,
        )

        try:
            config = await resolve_streaming_storage_config(self._pool)
            if not config.configured:
                await self._repo.mark_upload_job(job_id, status="failed", error="Streaming storage is not configured.")
                return

            candidates = variant_url_candidates(
                variant=variant,
                stored_ok=normalize_http_download_url(context.get("audio_url_ok")),
                stored_alt=normalize_http_download_url(context.get("audio_url_alt")),
                refreshed=refreshed,
            )
            primary_url = candidates[0] if candidates else normalize_http_download_url(source_url)
            fallback_urls = candidates[1:] if len(candidates) > 1 else []
            if not primary_url:
                raise StorageServiceError(
                    "No valid Suno download URL available. Re-poll record-info or retry after Suno callback."
                )
            _audio_id = ""
            if refreshed is not None:
                _audio_id = refreshed.audio_id_alt if variant == "alt" else refreshed.audio_id_ok
            if not _audio_id:
                _audio_id = str(
                    context.get("audio_id_alt" if variant == "alt" else "audio_id_ok") or ""
                ).strip()
            data = await self._download_mp3_with_recovery(
                external_task_id=str(context.get("external_task_id") or ""),
                audio_id=_audio_id,
                primary_url=primary_url,
                fallback_urls=fallback_urls,
            )
            # Write a Xing/Info header so players/ffprobe report the true length
            # (Suno CDN MP3s omit it and over-report, so exports look short).
            data = await ensure_mp3_duration_header_async(data)
            storage = StorageService.from_config(config)
            await storage.upload_bytes(key=storage_key, data=data, content_type="audio/mpeg")

            album_id = await self._repo.get_or_create_album(
                user_id=user_id,
                batch_id=batch_id,
                album_name=album_name,
                album_slug=album_slug,
                channel_role=channel_role,
            )

            duration_seconds = None
            suno_image_url = ""
            tags_text = ""
            suno_audio_id = ""
            if refreshed is not None:
                if variant == "alt":
                    duration_seconds = refreshed.duration_alt
                    suno_image_url = refreshed.image_url_alt
                    tags_text = refreshed.tags_alt
                    suno_audio_id = refreshed.audio_id_alt
                else:
                    duration_seconds = refreshed.duration_ok
                    suno_image_url = refreshed.image_url_ok
                    tags_text = refreshed.tags_ok
                    suno_audio_id = refreshed.audio_id_ok
            if not suno_audio_id:
                if variant == "alt":
                    suno_audio_id = str(context.get("audio_id_alt") or "").strip()
                else:
                    suno_audio_id = str(context.get("audio_id_ok") or "").strip()

            lyrics = plain_lyrics
            external_task_id = str(context.get("external_task_id") or "").strip()
            if suno_audio_id and external_task_id:
                lrc = await fetch_timestamped_lrc_with_pool(
                    self._pool,
                    external_task_id=external_task_id,
                    audio_id=suno_audio_id,
                )
                if looks_like_lrc(lrc):
                    lyrics = lrc

            primary_genre, catalog_genres = resolve_stream_genres(
                description_genres=context.get("description_genres"),
                suno_tags_text=tags_text,
            )
            genre = primary_genre
            tags = parse_suno_clip_tags(tags_text) or None
            track_number = None
            batch_index = context.get("batch_index")
            if batch_index is not None:
                try:
                    track_number = int(batch_index) + 1
                except (TypeError, ValueError):
                    track_number = None

            cover_storage_key = await self._maybe_upload_suno_cover(
                user_id=user_id,
                album_id=album_id,
                album_slug=album_slug,
                variant=variant,
                image_url=suno_image_url,
                storage=storage,
            )

            await self._repo.update_album_genre(album_id, genre, genres=catalog_genres or None)
            track_id = await self._repo.upsert_track(
                user_id=user_id,
                album_id=album_id,
                song_id=song_id,
                suno_task_id=suno_task_id,
                title=title,
                lyrics=lyrics,
                variant=variant,
                storage_key=storage_key,
                size_bytes=len(data),
                duration_seconds=duration_seconds,
                genre=genre,
                track_number=track_number,
                cover_storage_key=cover_storage_key,
                suno_image_url=suno_image_url or None,
                tags=tags,
                genres=catalog_genres or None,
                suno_audio_id=suno_audio_id or None,
            )
            del track_id
            await self._repo.mark_upload_job(
                job_id, status="success", storage_key=storage_key, album_id=album_id
            )
        except Exception as exc:
            await self._repo.mark_upload_job(job_id, status="failed", error=str(exc)[:500])
            logger.warning("MP3 streaming upload failed job=%s: %s", job_id, exc)

    def schedule_web_music_wav_upload(self, *, suno_task_id: UUID, variant: str | None = None) -> None:
        """Kick WAV conversion + B2 upload now for a completed web-music task."""
        asyncio.create_task(self._run_web_music_wav_upload(suno_task_id, variant))

    async def _run_web_music_wav_upload(self, suno_task_id: UUID, variant: str | None) -> None:
        try:
            context = await self._repo.get_suno_stream_context(suno_task_id)
            if not context or str(context.get("source") or "").strip().lower() != "web_music":
                return
            config = await resolve_streaming_storage_config(self._pool)
            if not config.configured:
                return
            storage = StorageService.from_config(config)
            variants = [variant] if variant in {"ok", "alt"} else ["ok", "alt"]
            for v in variants:
                b2_col = f"b2_wav_storage_key_{v}"
                wav_task_col = f"wav_task_id_{v}"
                wav_status_col = f"wav_status_{v}"
                row = await self._pool.fetchrow(
                    f"SELECT {b2_col} AS k, {wav_task_col} AS t, {wav_status_col} AS s FROM suno_tasks WHERE id = $1",
                    suno_task_id,
                )
                wav_key = str(row.get("k") or "").strip() if row else ""
                wav_task = str(row.get("t") or "").strip() if row else ""
                wav_status = str(row.get("s") or "").strip() if row else ""
                if wav_key or (wav_task and wav_status != "success"):
                    continue
                title = str(context.get("song_title") or "Untitled").strip() or "Untitled"
                await self._upload_web_music_wav(
                    context=context,
                    variant=v,
                    suno_task_id=suno_task_id,
                    song_slug=slugify(title, fallback="track"),
                    user_id=UUID(str(context["user_id"])),
                    storage=storage,
                )
        except Exception as exc:
            logger.warning("Web music WAV upload scheduling failed task=%s: %s", suno_task_id, exc)

    async def _upload_web_music_variant(
        self,
        *,
        context: dict[str, Any],
        variant: str,
        source_url: str,
        refreshed: SunoTaskDownloadUrls | None = None,
    ) -> None:
        """Upload web music MP3 to Backblaze with simplified structure (no albums)."""
        user_id = UUID(str(context["user_id"]))
        suno_task_id = UUID(str(context["suno_task_id"]))
        title = str(context.get("song_title") or "Untitled").strip() or "Untitled"
        song_slug = slugify(title, fallback="track")
        storage_key = web_music_object_key(user_id, suno_task_id, variant, "mp3")

        try:
            config = await resolve_streaming_storage_config(self._pool)
            if not config.configured:
                logger.warning("Streaming storage not configured, skipping web music upload for task=%s", suno_task_id)
                return

            candidates = variant_url_candidates(
                variant=variant,
                stored_ok=normalize_http_download_url(context.get("audio_url_ok")),
                stored_alt=normalize_http_download_url(context.get("audio_url_alt")),
                refreshed=refreshed,
            )
            primary_url = candidates[0] if candidates else normalize_http_download_url(source_url)
            fallback_urls = candidates[1:] if len(candidates) > 1 else []
            if not primary_url:
                logger.warning("No valid Suno download URL for web music task=%s variant=%s", suno_task_id, variant)
                return

            data = await download_suno_mp3_bytes(primary_url, fallback_urls=fallback_urls)
            full_data = await ensure_mp3_duration_header_async(data)
            if bool(context.get("is_preview")):
                try:
                    data = await trim_audio_bytes(
                        full_data,
                        seconds=int(context.get("preview_seconds") or PREVIEW_SECONDS),
                        fmt="mp3",
                    )
                except PreviewTrimError as exc:
                    # Never store the full track for a preview. The on-demand
                    # fallback trims too, and refuses to serve if it cannot.
                    logger.error(
                        "Preview MP3 trim failed task=%s variant=%s: %s",
                        suno_task_id,
                        variant,
                        exc,
                    )
                    return
            data = await ensure_mp3_duration_header_async(data)
            storage = StorageService.from_config(config)
            await storage.upload_bytes(key=storage_key, data=data, content_type="audio/mpeg")

            if variant == "ok":
                await self._pool.execute(
                    """
                    UPDATE suno_tasks
                    SET b2_storage_key_ok = $2,
                        b2_uploaded_at_ok = NOW(),
                        updated_at = NOW()
                    WHERE id = $1
                    """,
                    suno_task_id,
                    storage_key,
                )
            else:
                await self._pool.execute(
                    """
                    UPDATE suno_tasks
                    SET b2_storage_key_alt = $2,
                        b2_uploaded_at_alt = NOW(),
                        updated_at = NOW()
                    WHERE id = $1
                    """,
                    suno_task_id,
                    storage_key,
                )

            await self._encrypt_ingested_mp3(
                data,
                subject_type="suno_task",
                subject_id=suno_task_id,
                variant=variant,
                storage_key=storage_key,
                storage=storage,
                null_suno_urls=True,
            )

            # Keep the full-length master in a private object. It is never
            # referenced by playback/download; an unlock copies it over the
            # served key after a pack purchase.
            if bool(context.get("is_preview")):
                try:
                    full_blob = await AudioPackageService(self._pool).encrypt_suno_export(
                        full_data,
                        subject_id=suno_task_id,
                        variant=variant,
                    )
                    full_key = web_music_object_key(user_id, suno_task_id, variant, "full.mp3")
                    await storage.upload_bytes(
                        key=full_key,
                        data=full_blob,
                        content_type=(
                            GCM_MIME if looks_like_camxora_audio(full_blob) else "audio/mpeg"
                        ),
                    )
                    await self._pool.execute(
                        f"UPDATE suno_tasks SET b2_full_storage_key_{variant} = $2, updated_at = NOW() WHERE id = $1",
                        suno_task_id,
                        full_key,
                    )
                except Exception as exc:
                    logger.warning(
                        "Web music full-master upload failed task=%s variant=%s: %s",
                        suno_task_id,
                        variant,
                        exc,
                    )

            logger.info("Web music MP3 uploaded to B2: task=%s variant=%s key=%s size=%d", 
                       suno_task_id, variant, storage_key, len(data))
            
            asyncio.create_task(self._upload_web_music_lrc(
                context=context,
                variant=variant,
                suno_task_id=suno_task_id,
                song_slug=song_slug,
                user_id=user_id,
                refreshed=refreshed,
            ))
            # Also upload WAV to B2
            asyncio.create_task(self._upload_web_music_wav(
                context=context,
                variant=variant,
                suno_task_id=suno_task_id,
                song_slug=song_slug,
                user_id=user_id,
                storage=storage,
            ))
        except Exception as exc:
            logger.warning("Web music B2 upload failed task=%s variant=%s: %s", suno_task_id, variant, exc)

    async def _backfill_web_music_wav(self, *, suno_task_id: UUID, variant: str) -> bool:
        """Resume/complete a web-music WAV -> B2 backup. True if B2 now has it."""
        context = await self._repo.get_suno_stream_context(suno_task_id)
        if not context or str(context.get("source") or "").strip().lower() != "web_music":
            return False
        config = await resolve_streaming_storage_config(self._pool)
        if not config.configured:
            return False
        storage = StorageService.from_config(config)
        await self._upload_web_music_wav(
            context=context,
            variant=variant,
            suno_task_id=suno_task_id,
            song_slug="",
            user_id=UUID(str(context["user_id"])),
            storage=storage,
        )
        column = "b2_wav_storage_key_ok" if variant == "ok" else "b2_wav_storage_key_alt"
        row = await self._pool.fetchrow(
            f"SELECT {column} AS key FROM suno_tasks WHERE id = $1",
            suno_task_id,
        )
        return bool(row and str(row["key"] or "").strip())

    async def _upload_web_music_wav(
        self,
        *,
        context: dict[str, Any],
        variant: str,
        suno_task_id: UUID,
        song_slug: str,
        user_id: UUID,
        storage: Any,
    ) -> None:
        """Upload web music WAV to Backblaze after MP3 upload completes."""
        try:
            from platform_api.clients.suno_client import (
                extract_suno_wav_task_id,
                parse_suno_wav_poll,
            )
            from platform_api.services.suno_audio_resolver import (
                _suno_client_from_env,
                call_with_owning_suno_key,
            )
            
            wav_task_id_col = "wav_task_id_ok" if variant == "ok" else "wav_task_id_alt"
            wav_url_col = "wav_url_ok" if variant == "ok" else "wav_url_alt"
            audio_id = context.get(f"audio_id_{variant}") or ""
            external_task_id = str(context.get("external_task_id") or "").strip()
            
            if not audio_id or not external_task_id:
                logger.info("Skipping WAV upload: missing audio_id or external_task_id for task=%s variant=%s", suno_task_id, variant)
                return

            # Check if WAV conversion already started
            row = await self._pool.fetchrow(
                f"""
                SELECT {wav_task_id_col} as wav_task_id, {wav_url_col} as wav_url
                FROM suno_tasks
                WHERE id = $1
                """,
                suno_task_id,
            )
            
            wav_task_id = row.get("wav_task_id") if row else None
            wav_url = row.get("wav_url") if row else None
            suno = _suno_client_from_env()
            
            # Submit WAV conversion if not started
            if not wav_task_id:
                try:
                    result, _wav_owner_key = await call_with_owning_suno_key(
                        self._pool,
                        lambda k: suno.submit_wav_task(
                            task_id=external_task_id,
                            audio_id=audio_id,
                            api_key=k,
                        ),
                    )
                    wav_task_id = extract_suno_wav_task_id(result)
                    
                    # Update database with WAV task ID
                    if variant == "ok":
                        await self._pool.execute(
                            "UPDATE suno_tasks SET wav_task_id_ok = $2 WHERE id = $1",
                            suno_task_id,
                            wav_task_id,
                        )
                    else:
                        await self._pool.execute(
                            "UPDATE suno_tasks SET wav_task_id_alt = $2 WHERE id = $1",
                            suno_task_id,
                            wav_task_id,
                        )
                except Exception as exc:
                    logger.warning("Failed to submit WAV conversion for task=%s variant=%s: %s", suno_task_id, variant, exc)
                    if variant in {"ok", "alt"} and getattr(exc, "is_retryable", None) is False:
                        await self._pool.execute(
                            f"UPDATE suno_tasks SET wav_status_{variant} = 'failed', updated_at = NOW() WHERE id = $1",
                            suno_task_id,
                        )
                    return

            # Poll for WAV URL
            if not wav_url and wav_task_id:
                max_retries = 90
                for attempt in range(max_retries):
                    try:
                        result, _ = await call_with_owning_suno_key(
                            self._pool,
                            lambda k: suno.poll_wav_status(wav_task_id=wav_task_id, api_key=k),
                        )
                        status, url, error = parse_suno_wav_poll(result)
                        
                        if status == "success" and url:
                            wav_url = url
                            # Update database with WAV URL
                            if variant == "ok":
                                await self._pool.execute(
                                    "UPDATE suno_tasks SET wav_url_ok = $2, wav_status_ok = $3 WHERE id = $1",
                                    suno_task_id,
                                    wav_url,
                                    "success",
                                )
                            else:
                                await self._pool.execute(
                                    "UPDATE suno_tasks SET wav_url_alt = $2, wav_status_alt = $3 WHERE id = $1",
                                    suno_task_id,
                                    wav_url,
                                    "success",
                                )
                            break
                        elif status == "failed":
                            logger.warning("WAV conversion failed for task=%s variant=%s: %s", suno_task_id, variant, error)
                            if variant == "ok":
                                await self._pool.execute(
                                    "UPDATE suno_tasks SET wav_status_ok = 'failed', updated_at = NOW() WHERE id = $1",
                                    suno_task_id,
                                )
                            else:
                                await self._pool.execute(
                                    "UPDATE suno_tasks SET wav_status_alt = 'failed', updated_at = NOW() WHERE id = $1",
                                    suno_task_id,
                                )
                            return
                        
                        await asyncio.sleep(2)
                    except Exception as exc:
                        logger.warning("WAV poll attempt %d failed for task=%s variant=%s: %s", attempt, suno_task_id, variant, exc)
                        if attempt < max_retries - 1:
                            await asyncio.sleep(2)
                        else:
                            return

            # Download and upload WAV to B2
            if wav_url:
                import httpx
                
                wav_storage_key = web_music_object_key(user_id, suno_task_id, variant, "wav")
                
                async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
                    response = await client.get(wav_url)
                    response.raise_for_status()
                    wav_data = response.content
                full_wav_data = wav_data

                if bool(context.get("is_preview")):
                    try:
                        wav_data = await trim_audio_bytes(
                            wav_data,
                            seconds=int(context.get("preview_seconds") or PREVIEW_SECONDS),
                            fmt="wav",
                        )
                    except PreviewTrimError as exc:
                        logger.error(
                            "Preview WAV trim failed task=%s variant=%s: %s",
                            suno_task_id,
                            variant,
                            exc,
                        )
                        return
                
                wav_data = await AudioPackageService(self._pool).encrypt_suno_export(
                    wav_data,
                    subject_id=suno_task_id,
                    variant=variant,
                )
                wav_content_type = (
                    GCM_MIME if looks_like_camxora_audio(wav_data) else "audio/wav"
                )
                await storage.upload_bytes(
                    key=wav_storage_key,
                    data=wav_data,
                    content_type=wav_content_type,
                )
                
                # Update database with B2 WAV storage key
                if variant == "ok":
                    await self._pool.execute(
                        """
                        UPDATE suno_tasks
                        SET b2_wav_storage_key_ok = $2,
                            b2_wav_uploaded_at_ok = NOW(),
                            updated_at = NOW()
                        WHERE id = $1
                        """,
                        suno_task_id,
                        wav_storage_key,
                    )
                else:
                    await self._pool.execute(
                        """
                        UPDATE suno_tasks
                        SET b2_wav_storage_key_alt = $2,
                            b2_wav_uploaded_at_alt = NOW(),
                            updated_at = NOW()
                        WHERE id = $1
                        """,
                        suno_task_id,
                        wav_storage_key,
                    )
                
                logger.info("Web music WAV uploaded to B2: task=%s variant=%s key=%s size=%d", 
                           suno_task_id, variant, wav_storage_key, len(wav_data))

                if bool(context.get("is_preview")):
                    try:
                        full_wav_blob = await AudioPackageService(self._pool).encrypt_suno_export(
                            full_wav_data,
                            subject_id=suno_task_id,
                            variant=variant,
                        )
                        full_wav_key = web_music_object_key(
                            user_id, suno_task_id, variant, "full.wav"
                        )
                        await storage.upload_bytes(
                            key=full_wav_key,
                            data=full_wav_blob,
                            content_type=(
                                GCM_MIME
                                if looks_like_camxora_audio(full_wav_blob)
                                else "audio/wav"
                            ),
                        )
                        await self._pool.execute(
                            f"UPDATE suno_tasks SET b2_full_wav_storage_key_{variant} = $2, updated_at = NOW() WHERE id = $1",
                            suno_task_id,
                            full_wav_key,
                        )
                    except Exception as exc:
                        logger.warning(
                            "Web music full WAV upload failed task=%s variant=%s: %s",
                            suno_task_id,
                            variant,
                            exc,
                        )
        except Exception as exc:
            logger.warning("Web music WAV B2 upload failed task=%s variant=%s: %s", suno_task_id, variant, exc)

    def schedule_web_music_lrc_upload(
        self,
        *,
        suno_task_id: UUID,
        variant: str,
        lrc_text: str | None = None,
    ) -> None:
        """Upload timed LRC to Backblaze (from cached text or Suno fetch)."""
        asyncio.create_task(
            self._run_web_music_lrc_upload(
                suno_task_id,
                variant,
                lrc_text=lrc_text,
            )
        )

    async def _run_web_music_lrc_upload(
        self,
        suno_task_id: UUID,
        variant: str,
        *,
        lrc_text: str | None = None,
    ) -> None:
        try:
            variant_key = str(variant or "ok").strip().lower()
            if variant_key not in {"ok", "alt"}:
                return
            context = await self._repo.get_suno_stream_context(suno_task_id)
            if not context or str(context.get("source") or "").strip().lower() != "web_music":
                return
            b2_col = "b2_lrc_storage_key_ok" if variant_key == "ok" else "b2_lrc_storage_key_alt"
            row = await self._pool.fetchrow(
                f"""
                SELECT {b2_col} AS b2_lrc_key, instrumental
                FROM suno_tasks
                WHERE id = $1
                """,
                suno_task_id,
            )
            if row is None or row.get("b2_lrc_key") or bool(row.get("instrumental")):
                return
            lrc = str(lrc_text or "").strip()
            if not looks_like_lrc(lrc):
                external_task_id = str(context.get("external_task_id") or "").strip()
                audio_id = str(context.get(f"audio_id_{variant_key}") or "").strip()
                if not external_task_id or not audio_id:
                    refreshed = await self._refresh_task_download_urls(context)
                    audio_id = str(
                        (refreshed.audio_id_ok if variant_key == "ok" else refreshed.audio_id_alt)
                        or audio_id
                    ).strip()
                if not external_task_id or not audio_id:
                    return
                lrc = await fetch_timestamped_lrc_with_pool(
                    self._pool,
                    external_task_id=external_task_id,
                    audio_id=audio_id,
                )
            if not looks_like_lrc(lrc):
                return
            await self._upload_web_music_lrc(
                context=context,
                variant=variant_key,
                suno_task_id=suno_task_id,
                song_slug=slugify(str(context.get("song_title") or "Untitled").strip() or "Untitled", fallback="track"),
                user_id=UUID(str(context["user_id"])),
                lrc_text=lrc,
            )
        except Exception as exc:
            logger.warning("Web music LRC B2 upload failed task=%s variant=%s: %s", suno_task_id, variant, exc)

    async def _upload_web_music_lrc(
        self,
        *,
        context: dict[str, Any],
        variant: str,
        suno_task_id: UUID,
        song_slug: str,
        user_id: UUID,
        lrc_text: str | None = None,
        refreshed: SunoTaskDownloadUrls | None = None,
    ) -> None:
        """Upload web music LRC to Backblaze (SRT is derived on download)."""
        variant_key = str(variant or "ok").strip().lower()
        if variant_key not in {"ok", "alt"}:
            return
        b2_col = "b2_lrc_storage_key_ok" if variant_key == "ok" else "b2_lrc_storage_key_alt"
        uploaded_col = "b2_lrc_uploaded_at_ok" if variant_key == "ok" else "b2_lrc_uploaded_at_alt"
        existing = await self._pool.fetchval(
            f"SELECT {b2_col} FROM suno_tasks WHERE id = $1",
            suno_task_id,
        )
        if existing:
            return
        lrc = str(lrc_text or "").strip()
        if not looks_like_lrc(lrc):
            external_task_id = str(context.get("external_task_id") or "").strip()
            audio_id = str(context.get(f"audio_id_{variant_key}") or "").strip()
            if refreshed:
                audio_id = str(
                    (refreshed.audio_id_ok if variant_key == "ok" else refreshed.audio_id_alt)
                    or audio_id
                ).strip()
            if not external_task_id or not audio_id:
                return
            lrc = await fetch_timestamped_lrc_with_pool(
                self._pool,
                external_task_id=external_task_id,
                audio_id=audio_id,
            )
        if not looks_like_lrc(lrc):
            return
        storage_key = web_music_object_key(user_id, suno_task_id, variant_key, "lrc")
        try:
            config = await resolve_streaming_storage_config(self._pool)
            if not config.configured:
                return
            storage = StorageService.from_config(config)
            lrc_bytes = lrc.encode("utf-8")
            lrc_bytes = await AudioPackageService(self._pool).encrypt_suno_export(
                lrc_bytes,
                subject_id=suno_task_id,
                variant=variant_key,
            )
            lrc_content_type = (
                GCM_MIME if looks_like_camxora_audio(lrc_bytes) else "text/plain; charset=utf-8"
            )
            await storage.upload_bytes(
                key=storage_key,
                data=lrc_bytes,
                content_type=lrc_content_type,
            )
            await self._pool.execute(
                f"""
                UPDATE suno_tasks
                SET {b2_col} = $2,
                    {uploaded_col} = NOW(),
                    updated_at = NOW()
                WHERE id = $1
                """,
                suno_task_id,
                storage_key,
            )
            logger.info(
                "Web music LRC uploaded to B2: task=%s variant=%s key=%s",
                suno_task_id,
                variant_key,
                storage_key,
            )
        except Exception as exc:
            logger.warning(
                "Web music LRC B2 upload failed task=%s variant=%s: %s",
                suno_task_id,
                variant_key,
                exc,
            )

    async def _maybe_upload_suno_cover(
        self,
        *,
        user_id: UUID,
        album_id: UUID,
        album_slug: str,
        variant: str,
        image_url: str,
        storage: StorageService,
    ) -> str | None:
        url = str(image_url or "").strip()
        if not url:
            return None
        row = await self._pool.fetchrow(
            "SELECT cover_storage_key FROM stream_albums WHERE id = $1",
            album_id,
        )
        if row and str(row.get("cover_storage_key") or "").strip():
            return None
        try:
            image_bytes = await self._download_image_bytes(url)
        except Exception as exc:
            logger.warning("Suno cover download failed for album %s: %s", album_id, str(exc)[:200])
            return None
        if not image_bytes:
            return None
        storage_key = f"{user_id}/{album_slug}/cover-suno-{variant}.jpg"
        try:
            await storage.upload_bytes(key=storage_key, data=image_bytes, content_type="image/jpeg")
            await self._repo.update_album_cover(album_id, storage_key)
            return storage_key
        except Exception as exc:
            logger.warning("Suno cover upload failed for album %s: %s", album_id, str(exc)[:200])
            return None

    @staticmethod
    async def _download_image_bytes(url: str) -> bytes:
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            response = await client.get(url, headers=_IMAGE_HEADERS)
            response.raise_for_status()
            data = response.content
            if len(data) < 512:
                raise StorageServiceError("Suno image response was too small.")
            return data

    async def upload_album_cover_from_image_job(
        self,
        *,
        user_id: UUID,
        batch_id: UUID,
        channel_role: str,
        image_bytes: bytes,
        preferred_kind: str,
    ) -> None:
        del preferred_kind
        context_row = await self._pool.fetchrow(
            "SELECT ok_album, alt_album FROM batches WHERE id = $1",
            batch_id,
        )
        if not context_row:
            return

        role = channel_role.lower()
        if role == "alt":
            album_name = str(context_row.get("alt_album") or "Alternate Album").strip()
        else:
            album_name = str(context_row.get("ok_album") or "Album").strip()
        album_slug = slugify(album_name, fallback="album")
        storage_key = f"{user_id}/{album_slug}/cover.jpg"

        job_id = await self._repo.create_upload_job(
            user_id=user_id,
            kind="cover",
            batch_id=batch_id,
            storage_key=storage_key,
        )
        try:
            config = await resolve_streaming_storage_config(self._pool)
            if not config.configured:
                await self._repo.mark_upload_job(job_id, status="failed", error="Streaming storage is not configured.")
                return

            storage = StorageService.from_config(config)
            await storage.upload_bytes(key=storage_key, data=image_bytes, content_type="image/jpeg")

            album_id = await self._repo.get_or_create_album(
                user_id=user_id,
                batch_id=batch_id,
                album_name=album_name,
                album_slug=album_slug,
                channel_role=role,
            )
            await self._repo.update_album_cover(album_id, storage_key)
            await self._repo.mark_upload_job(
                job_id, status="success", storage_key=storage_key, album_id=album_id
            )
        except Exception as exc:
            await self._repo.mark_upload_job(job_id, status="failed", error=str(exc)[:500])
            logger.warning("Cover streaming upload failed job=%s: %s", job_id, exc)

    async def upload_album_cover_from_profile_logo(
        self,
        *,
        user_id: UUID,
        batch_id: UUID,
        channel_role: str,
        logo_path: str,
    ) -> None:
        path = Path(logo_path)
        project_root = Path(__file__).resolve().parents[2]
        candidate = path if path.is_absolute() else (project_root / path)
        if not candidate.is_file():
            return
        await self.upload_album_cover_from_image_job(
            user_id=user_id,
            batch_id=batch_id,
            channel_role=channel_role,
            image_bytes=candidate.read_bytes(),
            preferred_kind="logo",
        )

    async def maybe_upload_cover_after_image_job(
        self,
        *,
        user_id: UUID,
        batch_id: UUID | None,
        channel_role: str,
        kind: ImageKind,
        image_bytes: bytes,
    ) -> None:
        if batch_id is None:
            return
        if kind not in {ImageKind.THUMBNAIL, ImageKind.BACKGROUND}:
            return

        role = str(channel_role or "ok").lower()
        album = await self._repo.find_album_for_batch_role(
            user_id=user_id,
            batch_id=batch_id,
            channel_role=role,
        )
        if album and album.get("cover_storage_key"):
            if kind == ImageKind.BACKGROUND:
                return

        await self.upload_album_cover_from_image_job(
            user_id=user_id,
            batch_id=batch_id,
            channel_role=role,
            image_bytes=image_bytes,
            preferred_kind=str(kind.value),
        )

    async def retry_failed_job(self, job_id: UUID) -> dict[str, Any]:
        """Re-run a failed MP3 upload job using its stored source URL."""
        job = await self._repo.get_upload_job(job_id)
        if not job:
            raise ValueError("Upload job not found.")
        if job.get("permanent_failed"):
            raise ValueError("Upload job is permanently failed.")
        if str(job.get("status") or "") not in {"failed", "pending"}:
            raise ValueError("Only pending or failed upload jobs can be retried.")

        kind = str(job.get("kind") or "")
        if not kind.startswith("mp3_"):
            raise ValueError("Only MP3 upload jobs can be retried from admin.")

        source_url = normalize_http_download_url(job.get("source_url"))
        suno_task_id = job.get("suno_task_id")
        if not suno_task_id:
            raise ValueError("Upload job is missing Suno task reference.")

        variant = kind.removeprefix("mp3_")
        if variant not in {"ok", "alt"}:
            raise ValueError(f"Unsupported MP3 upload kind: {kind}")

        context = await self._repo.get_suno_stream_context(UUID(str(suno_task_id)))
        if not context:
            raise ValueError("Original Suno task context was not found.")

        refreshed = await self._refresh_task_download_urls(context)
        if refreshed.refreshed and (refreshed.audio_url_ok or refreshed.audio_url_alt):
            await self._persist_refreshed_audio_urls(
                suno_task_id=UUID(str(suno_task_id)),
                refreshed=refreshed,
            )
            context = await self._repo.get_suno_stream_context(UUID(str(suno_task_id))) or context

        await self._repo.mark_upload_job(job_id, status="pending", error=None)

        try:
            config = await resolve_streaming_storage_config(self._pool)
            if not config.configured:
                await self._repo.mark_upload_job(
                    job_id,
                    status="failed",
                    error="Streaming storage is not configured.",
                )
                raise ValueError("Streaming storage is not configured.")

            if variant == "alt":
                album_name = str(
                    context.get("alt_album") or context.get("song_album") or "Alternate Album"
                ).strip()
                channel_role = "alt"
            else:
                album_name = str(context.get("ok_album") or context.get("song_album") or "Album").strip()
                channel_role = "ok"

            user_id = UUID(str(context["user_id"]))
            song_id = UUID(str(context["song_id"])) if context.get("song_id") else None
            batch_id = UUID(str(context["batch_id"])) if context.get("batch_id") else None
            title = str(context.get("song_title") or "Untitled").strip() or "Untitled"
            plain_lyrics = str(context.get("song_lyrics") or "").strip() or None
            album_slug = slugify(album_name, fallback="album")
            song_slug = slugify(title, fallback="track")
            storage_key = str(job.get("storage_key") or f"{user_id}/{album_slug}/{song_slug}-{variant}.mp3")

            suno_audio_id = ""
            if refreshed is not None:
                suno_audio_id = refreshed.audio_id_alt if variant == "alt" else refreshed.audio_id_ok
            if not suno_audio_id:
                suno_audio_id = str(
                    context.get("audio_id_alt" if variant == "alt" else "audio_id_ok") or ""
                ).strip()
            external_task_id = str(context.get("external_task_id") or "").strip()
            lyrics = plain_lyrics
            if suno_audio_id and external_task_id:
                lrc = await fetch_timestamped_lrc_with_pool(
                    self._pool,
                    external_task_id=external_task_id,
                    audio_id=suno_audio_id,
                )
                if looks_like_lrc(lrc):
                    lyrics = lrc

            candidates = variant_url_candidates(
                variant=variant,
                stored_ok=normalize_http_download_url(context.get("audio_url_ok")),
                stored_alt=normalize_http_download_url(context.get("audio_url_alt")),
                refreshed=refreshed,
            )
            primary_url = candidates[0] if candidates else source_url
            fallback_urls = candidates[1:] if len(candidates) > 1 else []
            if not primary_url:
                raise ValueError(
                    "No valid Suno download URL available for retry. Check Suno task record-info."
                )
            data = await self._download_mp3_with_recovery(
                external_task_id=external_task_id,
                audio_id=suno_audio_id,
                primary_url=primary_url,
                fallback_urls=fallback_urls,
            )
            data = await ensure_mp3_duration_header_async(data)
            storage = StorageService.from_config(config)
            await storage.upload_bytes(key=storage_key, data=data, content_type="audio/mpeg")

            album_id = await self._repo.get_or_create_album(
                user_id=user_id,
                batch_id=batch_id,
                album_name=album_name,
                album_slug=album_slug,
                channel_role=channel_role,
            )
            track_id = await self._repo.upsert_track(
                user_id=user_id,
                album_id=album_id,
                song_id=song_id,
                suno_task_id=UUID(str(suno_task_id)),
                title=title,
                lyrics=lyrics,
                variant=variant,
                storage_key=storage_key,
                size_bytes=len(data),
                suno_audio_id=suno_audio_id or None,
            )
            await self._repo.mark_upload_job(
                job_id, status="success", storage_key=storage_key, album_id=album_id
            )
            return {"ok": True, "job_id": str(job_id), "storage_key": storage_key}
        except Exception as exc:
            await self._repo.mark_upload_job(job_id, status="failed", error=str(exc)[:500])
            raise

    async def start_failed_mp3_retry_sweep(self) -> dict[str, Any]:
        """Start a background sweep that retries every failed mp3_ok/mp3_alt job.

        Runs server-side (bounded concurrency) so the request returns instantly
        even for thousands of jobs. See _retry_sweep.
        """
        return await _retry_sweep.start(self._pool)

    async def failed_mp3_retry_sweep_status(self) -> dict[str, Any]:
        """Live progress of the background failed-mp3 retry sweep."""
        return await _retry_sweep.status(self._pool)

    async def run_auto_retry_pass(self) -> int:
        """One auto-capture pass: retry eligible failed mp3 uploads.

        Single-winner across workers (session advisory lock), bounded budget
        (attempt cap + 48h window) and concurrency. Skips while the manual
        admin retry sweep owns the backlog. Returns how many jobs recovered.
        """
        if not _AUTO_RETRY_ENABLED:
            return 0
        repo = StreamingRepository(self._pool)
        sweep_state = await repo.get_retry_sweep_state() or {}
        if sweep_state.get("running") and not _state_is_stale(sweep_state):
            return 0
        async with self._pool.acquire() as conn:
            locked = await conn.fetchval(
                "SELECT pg_try_advisory_lock($1)", _AUTO_RETRY_ADVISORY_LOCK
            )
            if not locked:
                return 0
            try:
                job_ids = await repo.list_failed_mp3_jobs_for_auto_retry(
                    max_attempt_count=_AUTO_RETRY_MAX_ATTEMPT_COUNT,
                    max_age_hours=_AUTO_RETRY_MAX_AGE_HOURS,
                    limit=_AUTO_RETRY_PASS_LIMIT,
                )
                if not job_ids:
                    return 0
                semaphore = asyncio.Semaphore(_AUTO_RETRY_CONCURRENCY)

                async def retry_one(job_id: UUID) -> int:
                    async with semaphore:
                        try:
                            await self.retry_failed_job(job_id)
                            return 1
                        except Exception as exc:
                            logger.info(
                                "Auto-retry could not recover job=%s: %s",
                                job_id,
                                str(exc)[:200],
                            )
                            return 0

                results = await asyncio.gather(*(retry_one(jid) for jid in job_ids))
                return int(sum(results))
            finally:
                try:
                    await conn.fetchval(
                        "SELECT pg_advisory_unlock($1)", _AUTO_RETRY_ADVISORY_LOCK
                    )
                except Exception:
                    pass

    async def run_web_music_mp3_recovery_pass(self, *, limit: int | None = None) -> int:
        """Re-capture web-music MP3s that never reached B2.

        Web-music uploads are not recorded in ``stream_upload_jobs``, so the
        desktop auto-retry is blind to them. This pass finds web-music tasks that
        still expose a Suno audio URL but have no B2 MP3 and re-runs the backfill.
        Returns how many tasks captured at least one missing variant.
        """
        if not _WEB_MUSIC_MP3_RECOVERY_ENABLED:
            return 0
        tasks = await self._repo.list_web_music_missing_mp3_tasks(
            limit=limit or _WEB_MUSIC_MP3_PASS_LIMIT,
            max_age_hours=_WEB_MUSIC_MP3_MAX_AGE_HOURS,
        )
        if not tasks:
            return 0
        semaphore = asyncio.Semaphore(_WEB_MUSIC_MP3_CONCURRENCY)

        async def recover_one(row: dict[str, Any]) -> int:
            async with semaphore:
                task_id = UUID(str(row["id"]))
                try:
                    await self._run_web_music_b2_backfill(task_id, None)
                except Exception as exc:
                    logger.info(
                        "Web-music MP3 recovery could not capture task=%s: %s",
                        task_id,
                        str(exc)[:200],
                    )
                    return 0
                keys = await self._pool.fetchrow(
                    """
                    SELECT b2_storage_key_ok, b2_storage_key_alt
                    FROM suno_tasks WHERE id = $1
                    """,
                    task_id,
                )
                if keys is None:
                    return 0
                if row.get("missing_ok") and str(keys.get("b2_storage_key_ok") or "").strip():
                    return 1
                if row.get("missing_alt") and str(keys.get("b2_storage_key_alt") or "").strip():
                    return 1
                return 0

        results = await asyncio.gather(*(recover_one(row) for row in tasks))
        return int(sum(results))

    async def start_web_music_asset_recovery(self) -> dict[str, Any]:
        """Claim + start one web-music companion-asset recovery pass (async)."""
        repo = StreamingRepository(self._pool)
        if not _ASSET_RECOVERY_ENABLED:
            return {"started": False, "running": False, "reason": "disabled"}
        now = _now_iso()
        state = {
            "running": True,
            "started_at": now,
            "finished_at": None,
            "heartbeat_at": now,
            "counters": {
                "tasks_scanned": 0,
                "wav_recovered": 0,
                "wav_failed": 0,
                "lrc_recovered": 0,
                "lrc_noop": 0,
                "srt_created": 0,
                "pkg_recovered": 0,
                "pkg_failed": 0,
                "errors": 0,
            },
            "last_errors": [],
        }
        claimed = await repo.claim_asset_recovery_owner(
            state, stale_after_s=_RETRY_SWEEP_STALE_S
        )
        if not claimed:
            return {"started": False, "running": True}
        asyncio.create_task(self._asset_recovery_worker(state))
        return {"started": True, "running": True}

    async def web_music_asset_recovery_status(self) -> dict[str, Any]:
        repo = StreamingRepository(self._pool)
        state = await repo.get_asset_recovery_state()
        if not state:
            return {
                "running": False,
                "started_at": None,
                "finished_at": None,
                "counters": {},
                "last_errors": [],
            }
        running = bool(state.get("running")) and not _state_is_stale(state)
        return {
            "running": running,
            "started_at": state.get("started_at"),
            "finished_at": state.get("finished_at"),
            "counters": state.get("counters") or {},
            "last_errors": state.get("last_errors") or [],
        }

    async def _asset_recovery_worker(self, state: dict[str, Any]) -> None:
        repo = StreamingRepository(self._pool)
        counters: dict[str, int] = state.get("counters") or {}
        last_errors: list[dict[str, str]] = state.get("last_errors") or []

        def bump(key: str, amount: int = 1) -> None:
            counters[key] = int(counters.get(key, 0)) + amount

        def record_error(what: str, task_id: UUID, exc: Exception) -> None:
            bump("errors")
            last_errors.append(
                {"what": what, "task_id": str(task_id), "error": str(exc)[:220]}
            )
            if len(last_errors) > 8:
                last_errors.pop(0)

        # Moving watermark: each pass advances past the oldest scanned task so
        # permanently-gapped tasks cannot clog the newest window and starve the
        # historical backlog. Wrap around (None) once a pass hits the tail.
        cursor_state: dict[str, Any] = {"value": state.get("cursor") or None}

        async def persist(running: bool = True, finished: bool = False) -> None:
            await repo.upsert_asset_recovery_state(
                {
                    "running": running,
                    "started_at": state.get("started_at"),
                    "finished_at": _now_iso() if finished else None,
                    "heartbeat_at": _now_iso(),
                    "counters": counters,
                    "last_errors": last_errors,
                    "cursor": cursor_state["value"],
                }
            )

        try:
            storage: Any | None = None
            config = await resolve_streaming_storage_config(self._pool)
            if config.configured:
                storage = StorageService.from_config(config)

            async def fetch_col(col: str, task_id: UUID) -> str:
                value = await self._pool.fetchval(
                    f"SELECT {col} FROM suno_tasks WHERE id = $1", task_id
                )
                return str(value or "").strip()

            rows = await repo.list_web_music_asset_tasks(
                limit=_ASSET_PASS_TASK_LIMIT,
                before=cursor_state["value"],
            )
            wav_budget = _ASSET_WAV_MAX_PER_PASS
            lrc_budget = _ASSET_LRC_MAX_PER_PASS

            for row in rows:
                if not row.get("id"):
                    continue
                bump("tasks_scanned")
                task_id = UUID(str(row["id"]))
                user_id = UUID(str(row["user_id"])) if row.get("user_id") else None
                if not user_id:
                    continue
                cursor_state["value"] = _iso_created_at(row.get("created_at"))
                context = await repo.get_suno_stream_context(task_id) or {}
                title = str(
                    context.get("song_title") or row.get("song_title") or "Untitled"
                ).strip() or "Untitled"
                song_slug = slugify(title, fallback="track")

                for variant in ("ok", "alt"):
                    b2_col = f"b2_storage_key_{variant}"
                    mp3_key = str(row.get(b2_col) or "").strip()
                    if not mp3_key:
                        continue
                    # --- encrypted package ---
                    pkg_status = str(row.get(f"package_status_{variant}") or "none")
                    if pkg_status != "ready":
                        try:
                            await self._package_existing_web_music_mp3(
                                suno_task_id=task_id,
                                variant=variant,
                                storage_key=mp3_key,
                            )
                            after = await fetch_col(
                                f"package_status_{variant}", task_id
                            )
                            if after == "ready":
                                bump("pkg_recovered")
                            else:
                                bump("pkg_failed")
                        except Exception as exc:
                            bump("pkg_failed")
                            record_error("package", task_id, exc)
                    # --- WAV (capped; requires Suno conversion when no url yet) ---
                    wav_key = str(row.get(f"b2_wav_storage_key_{variant}") or "").strip()
                    wav_task = str(row.get(f"wav_task_id_{variant}") or "").strip()
                    wav_status = str(row.get(f"wav_status_{variant}") or "").strip()
                    wav_eligible = not wav_key and wav_status != "failed"
                    if wav_eligible and wav_budget > 0 and storage is not None:
                        wav_budget -= 1
                        try:
                            await self._upload_web_music_wav(
                                context=context,
                                variant=variant,
                                suno_task_id=task_id,
                                song_slug=song_slug,
                                user_id=user_id,
                                storage=storage,
                            )
                            after = await fetch_col(
                                f"b2_wav_storage_key_{variant}", task_id
                            )
                            if after:
                                bump("wav_recovered")
                            else:
                                bump("wav_failed")
                        except Exception as exc:
                            bump("wav_failed")
                            record_error("wav", task_id, exc)
                        await persist()
                    # --- LRC (capped) ---
                    instrumental = bool(row.get("instrumental"))
                    lrc_key = str(
                        row.get(f"b2_lrc_storage_key_{variant}") or ""
                    ).strip()
                    if not instrumental and not lrc_key and lrc_budget > 0:
                        lrc_budget -= 1
                        try:
                            await self._run_web_music_lrc_upload(task_id, variant)
                            after = await fetch_col(
                                f"b2_lrc_storage_key_{variant}", task_id
                            )
                            if after:
                                lrc_key = after
                                bump("lrc_recovered")
                            else:
                                bump("lrc_noop")  # timestamped LRC genuinely absent
                        except Exception as exc:
                            record_error("lrc", task_id, exc)
                        await persist()
                    # --- SRT derived from an existing stored LRC ---
                    if _ASSET_SRT_ENABLED and storage is not None and not instrumental:
                        lrc_now = lrc_key or str(
                            row.get(f"b2_lrc_storage_key_{variant}") or ""
                        ).strip()
                        if lrc_now:
                            try:
                                srt_key = web_music_object_key(
                                    user_id, task_id, variant, "srt"
                                )
                                try:
                                    await storage.download_bytes(key=srt_key)
                                except Exception:
                                    lrc_bytes = await storage.download_bytes(key=lrc_now)
                                    srt_text = _lrc_text_to_srt(
                                        lrc_bytes.decode("utf-8", "replace")
                                    )
                                    if srt_text:
                                        await storage.upload_bytes(
                                            key=srt_key,
                                            data=srt_text.encode("utf-8"),
                                            content_type="text/plain; charset=utf-8",
                                        )
                                        bump("srt_created")
                            except Exception as exc:
                                record_error("srt", task_id, exc)
                await persist()
            # Tail reached (fewer rows than the pass cap): wrap the watermark so
            # the next pass starts from the newest tasks again.
            if len(rows) < _ASSET_PASS_TASK_LIMIT:
                cursor_state["value"] = None
            await persist(running=False, finished=True)
            logger.info(
                "Web-music asset recovery pass done: %s", counters
            )
        except Exception as exc:
            logger.exception("Web-music asset recovery pass failed")
            record_error("pass", UUID(int=0), exc)
            try:
                await persist(running=False, finished=True)
            except Exception:
                pass

    async def retry_failed_jobs(
        self,
        *,
        limit: int = 50,
        max_age_hours: int = 72,
    ) -> dict[str, Any]:
        """Retry recent failed MP3 upload jobs (Recovery-Audio backed).

        Only jobs younger than ``max_age_hours`` are eligible — older ones are
        usually past the provider's recovery window.
        """
        rows = await self._pool.fetch(
            """
            SELECT id FROM stream_upload_jobs
            WHERE status = 'failed' AND kind IN ('mp3_ok', 'mp3_alt')
              AND created_at > now() - make_interval(hours => $1)
            ORDER BY created_at DESC
            LIMIT $2
            """,
            max(1, min(int(max_age_hours or 72), 24 * 90)),
            max(1, min(int(limit or 50), 1000)),
        )
        retried = succeeded = failed = 0
        for row in rows:
            retried += 1
            try:
                await self.retry_failed_job(row["id"])
                succeeded += 1
            except Exception:
                failed += 1
        return {"retried": retried, "succeeded": succeeded, "failed": failed}

    async def run_backfill_sweep(
        self,
        *,
        window_hours: int = 336,
        limit: int = 200,
        max_attempts: int = 6,
        alert: bool = True,
    ) -> dict[str, Any]:
        """Ensure every recent track has a durable B2 copy.

        - Reprocesses stuck ``pending`` / retryable ``failed`` MP3 jobs (with the
          provider Recovery-Audio fallback).
        - Backfills studio MP3s missing from the catalog (B2).
        - Marks jobs permanently failed after ``max_attempts`` so they stop
          retrying forever.
        - Alerts the ops channel when a sweep still leaves failures behind.
        """
        stats: dict[str, Any] = {
            "jobs_retried": 0,
            "jobs_succeeded": 0,
            "jobs_failed": 0,
            "permanent": 0,
            "backfilled": 0,
            "backfill_failed": 0,
            "wav_backfilled": 0,
            "wav_failed": 0,
        }
        jobs = await self._repo.list_retryable_upload_jobs(
            window_hours=window_hours,
            max_attempts=max_attempts,
            limit=limit,
        )
        for job in jobs:
            job_id = job["id"]
            stats["jobs_retried"] += 1
            try:
                await self.retry_failed_job(job_id)
                stats["jobs_succeeded"] += 1
            except Exception:
                stats["jobs_failed"] += 1
                fresh = await self._repo.get_upload_job(job_id)
                attempts = int((fresh or {}).get("attempt_count") or 0)
                if attempts >= max_attempts:
                    await self._repo.mark_upload_job_permanent_failed(
                        job_id,
                        error=f"Exceeded {max_attempts} upload attempts.",
                    )
                    stats["permanent"] += 1

        missing = await self._repo.list_studio_tasks_missing_b2(
            window_hours=window_hours,
            limit=limit,
        )
        for row in missing:
            context = await self._repo.get_suno_stream_context(UUID(str(row["id"])))
            if not context:
                continue
            try:
                refreshed = await self._refresh_task_download_urls(context)
            except Exception:
                refreshed = None
            for variant, flag in (("ok", "missing_ok"), ("alt", "missing_alt")):
                if not row.get(flag):
                    continue
                try:
                    source_url = normalize_http_download_url(
                        context.get("audio_url_ok" if variant == "ok" else "audio_url_alt")
                    )
                    await self._upload_mp3_variant(
                        context=context,
                        variant=variant,
                        source_url=source_url or "",
                        refreshed=refreshed,
                    )
                    stats["backfilled"] += 1
                except Exception:
                    stats["backfill_failed"] += 1

        # Web-music WAV is deliberately not backfilled. It is a paid, optional
        # export that the download path generates on demand, so rebuilding every
        # missing one here would undo that and re-fill B2 with ~37 MiB per track.
        # (`_backfill_web_music_wav` is kept for explicit admin/tool use.)

        if alert and (
            stats["jobs_failed"] or stats["backfill_failed"] or stats["wav_failed"]
        ):
            try:
                from platform_api.services.telegram_ops_alert_service import schedule_ops_message

                # Rate-limit the alert: a chronic failure (often a transient
                # companion WAV that keeps getting retried) would otherwise page
                # on every 15-minute sweep. Claim a single window across workers.
                should_alert = await self._repo.claim_periodic_report(
                    key=B2_BACKFILL_ALERT_SETTING_KEY,
                    lock_id=B2_BACKFILL_ALERT_ADVISORY_LOCK_ID,
                    interval_s=_B2_BACKFILL_ALERT_COOLDOWN_S,
                )
                if should_alert:
                    schedule_ops_message(
                        "<b>B2 backfill sweep</b>\n"
                        f"jobs retried={stats['jobs_retried']} ok={stats['jobs_succeeded']} "
                        f"failed={stats['jobs_failed']} permanent={stats['permanent']}\n"
                        f"backfilled={stats['backfilled']} backfill_failed={stats['backfill_failed']} "
                        f"wav={stats['wav_backfilled']} wav_failed={stats['wav_failed']}",
                        kind="backfill_sweep",
                    )
            except Exception:
                logger.warning("Could not send B2 backfill sweep alert", exc_info=True)
        return stats

    async def run_backfill_sweep_periodic(self, interval_s: float) -> dict[str, Any] | None:
        """One periodic sweep, claimed by a single uvicorn worker.

        ``main`` starts the backfill loop in every worker process, so without a
        cross-worker claim the same sweep ran (and alerted) once per worker each
        interval. Returns ``None`` when another worker already won this window.
        """
        claimed = await self._repo.claim_periodic_report(
            key=B2_BACKFILL_SWEEP_SETTING_KEY,
            lock_id=B2_BACKFILL_SWEEP_ADVISORY_LOCK_ID,
            interval_s=interval_s,
        )
        if not claimed:
            return None
        return await self.run_backfill_sweep()


async def run_streaming_auto_retry_loop(pool: Any) -> None:
    """Background loop (started by main startup) that auto-retries failed mp3
    uploads and keeps web-music companion assets (wav/lrc/srt/package) on B2."""
    service = StreamingUploadService(pool)
    while True:
        try:
            recovered = await service.run_auto_retry_pass()
            if recovered:
                logger.info("Streaming auto-retry pass recovered %s upload job(s)", recovered)
        except Exception:
            logger.exception("Streaming auto-retry pass failed (non-fatal)")
        try:
            web_recovered = await service.run_web_music_mp3_recovery_pass()
            if web_recovered:
                logger.info(
                    "Web-music MP3 recovery captured %s task(s)", web_recovered
                )
        except Exception:
            logger.exception("Web-music MP3 recovery pass failed (non-fatal)")
        try:
            started = await service.start_web_music_asset_recovery()
            if started.get("started"):
                logger.info("Web-music asset recovery pass started by auto loop.")
        except Exception:
            logger.exception("Web-music asset recovery start failed (non-fatal)")
        await asyncio.sleep(_AUTO_RETRY_INTERVAL_S)

