"""DistroKid WAV conversion, usage metering, and upload-history operations."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from platform_api.clients.key_pool_client_wrapper import KeyPoolClientWrapper
from platform_api.clients.suno_client import SunoClient, parse_suno_wav_poll
from platform_api.exceptions import ForbiddenError, NotFoundError, QuotaExceededError, ValidationError
from platform_api.services.distrokid_entitlement_service import (
    DISTROKID_MONTHLY_WAV_LIMIT,
    license_has_active_distrokid,
)


class DistroKidService:
    """Owns user-scoped DistroKid data and provider interactions."""

    def __init__(self, *, pool: Any, license_repo: Any, credit_service: Any, suno_client: SunoClient,
                 key_pool_service: Any) -> None:
        self._pool = pool
        self._license_repo = license_repo
        self._credit_service = credit_service
        self._suno_client = suno_client
        self._suno_keys = KeyPoolClientWrapper(key_pool_service, provider="suno")

    @staticmethod
    def period_key(now: datetime | None = None) -> str:
        return (now or datetime.now(timezone.utc)).astimezone(timezone.utc).strftime("%Y-%m")

    async def _require_entitlement(self, user_id: UUID) -> None:
        license_obj = await self._license_repo.get_active_for_user(user_id)
        if not license_has_active_distrokid(license_obj):
            raise ForbiddenError(
                "An active DistroKid add-on is required for WAV conversion.",
                details={"entitlement": "distrokid"},
            )

    async def usage(self, user_id: UUID) -> dict[str, Any]:
        key = self.period_key()
        used = await self._pool.fetchval(
            "SELECT used_count FROM distrokid_wav_usage WHERE user_id = $1 AND period_key = $2",
            user_id, key,
        )
        return {"used": int(used or 0), "limit": DISTROKID_MONTHLY_WAV_LIMIT, "period_key": key}

    async def _reserve_usage(self, user_id: UUID) -> dict[str, Any]:
        key = self.period_key()
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """
                    INSERT INTO distrokid_wav_usage (id, user_id, period_key, used_count)
                    VALUES ($1, $2, $3, 1)
                    ON CONFLICT (user_id, period_key) DO UPDATE
                    SET used_count = distrokid_wav_usage.used_count + 1
                    WHERE distrokid_wav_usage.used_count < $4
                    RETURNING used_count
                    """,
                    uuid4(), user_id, key, DISTROKID_MONTHLY_WAV_LIMIT,
                )
                if row is None:
                    raise QuotaExceededError(
                        "DistroKid WAV monthly limit reached.",
                        details={"limit": DISTROKID_MONTHLY_WAV_LIMIT, "period_key": key},
                    )
        return {"used": int(row["used_count"]), "limit": DISTROKID_MONTHLY_WAV_LIMIT, "period_key": key}

    async def convert(self, *, user_id: UUID, suno_task_id: str, audio_id: str | None,
                      role: str, song_id: UUID | None, batch_id: UUID | None) -> dict[str, Any]:
        await self._require_entitlement(user_id)
        role = str(role or "primary").lower()
        if role not in {"primary", "secondary"}:
            raise ValidationError("role must be primary or secondary.")
        source = await self._pool.fetchrow(
            """
            SELECT audio_id_ok, audio_id_alt, song_id, batch_id
            FROM suno_tasks WHERE external_task_id = $1 AND user_id = $2
            """,
            suno_task_id, user_id,
        )
        if source is None:
            raise NotFoundError("Suno task not found.")
        resolved_audio_id = str(audio_id or (source["audio_id_ok"] if role == "primary" else source["audio_id_alt"]) or "").strip()
        if not resolved_audio_id:
            raise ValidationError("No Suno audio ID is available for the selected role.")
        usage = await self._reserve_usage(user_id)
        job_id = uuid4()
        try:
            async def submit_and_persist() -> Any:
                submitted = await self._suno_keys.execute(
                    lambda api_key: self._suno_client.submit_wav_convert(
                        suno_task_id, resolved_audio_id, api_key=api_key
                    )
                )
                return await self._pool.fetchrow(
                    """
                    INSERT INTO distrokid_wav_jobs
                      (id, user_id, suno_task_id, audio_id, role, wav_task_id, status, song_id, batch_id)
                    VALUES ($1,$2,$3,$4,$5,$6,'pending',$7,$8)
                    RETURNING *
                    """,
                    job_id, user_id, suno_task_id, resolved_audio_id, role, str(submitted["taskId"]),
                    song_id or source["song_id"], batch_id or source["batch_id"],
                )
            row, charged = await self._credit_service.execute_with_credits(
                user_id, "suno", "wav", submit_and_persist
            )
            return self._job(row, charged_credits=charged, usage=usage)
        except Exception:
            await self._pool.execute(
                "UPDATE distrokid_wav_usage SET used_count = GREATEST(used_count - 1, 0) WHERE user_id=$1 AND period_key=$2",
                user_id, usage["period_key"],
            )
            raise

    async def get_job(self, *, user_id: UUID, job_id: UUID, refresh: bool = True) -> dict[str, Any]:
        row = await self._pool.fetchrow(
            "SELECT * FROM distrokid_wav_jobs WHERE id = $1 AND user_id = $2", job_id, user_id
        )
        if row is None:
            raise NotFoundError("WAV job not found.")
        if refresh and str(row["status"]).lower() in {"pending", "running"}:
            payload = await self._suno_keys.execute(
                lambda api_key: self._suno_client.check_wav_status(str(row["wav_task_id"]), api_key=api_key)
            )
            parsed = parse_suno_wav_poll(payload)
            if parsed.state != "pending":
                row = await self._pool.fetchrow(
                    """
                    UPDATE distrokid_wav_jobs
                    SET status=$3, audio_wav_url=$4, error_message=$5, updated_at=NOW()
                    WHERE id=$1 AND user_id=$2 RETURNING *
                    """,
                    job_id, user_id, parsed.state, parsed.audio_wav_url or None, parsed.error or None,
                )
        return self._job(row)

    async def check_history(self, *, user_id: UUID, album_name: str, tracks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        matches: list[dict[str, Any]] = []
        for track in tracks:
            rows = await self._pool.fetch(
                """
                SELECT * FROM distrokid_upload_history
                WHERE user_id=$1 AND album_name=$2
                  AND (($3::text IS NOT NULL AND wav_sha256=$3)
                    OR ($3::text IS NULL AND track_title=$4 AND wav_byte_size IS NOT DISTINCT FROM $5))
                ORDER BY uploaded_at DESC
                """,
                user_id, album_name, track.get("wav_sha256") or None,
                track.get("title", ""), track.get("wav_byte_size"),
            )
            matches.extend(dict(row) for row in rows)
        return matches

    async def record_history(self, *, user_id: UUID, album_name: str, directory_path: str | None,
                             batch_id: str | None, tracks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        created = []
        for track in tracks:
            row = await self._pool.fetchrow(
                """
                INSERT INTO distrokid_upload_history
                  (id,user_id,album_name,directory_path,batch_id,track_title,track_role,wav_byte_size,wav_sha256,status,uploaded_at)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,NOW()) RETURNING *
                """,
                uuid4(), user_id, album_name, directory_path, batch_id, track["title"],
                track.get("track_role"), track.get("wav_byte_size"), track.get("wav_sha256"),
                track.get("status", "success"),
            )
            created.append(dict(row))
        return created

    async def get_batch_context(self, *, user_id: UUID, batch_id: UUID) -> dict[str, Any]:
        """Return DistroKid snapshot flags + role artist names for a batch."""
        row = await self._pool.fetchrow(
            """
            SELECT
              COALESCE(b.auto_distrokid, false) AS auto_distrokid,
              COALESCE(b.auto_reel_after_video, false) AS auto_reel_after_video,
              b.ok_profile_id,
              b.alt_profile_id,
              COALESCE(ok.name, '') AS primary_artist_name,
              COALESCE(alt.name, '') AS secondary_artist_name,
              COALESCE(b.ok_album, '') AS primary_album_name,
              COALESCE(b.alt_album, b.ok_album, '') AS secondary_album_name
            FROM batches b
            LEFT JOIN channel_profiles ok ON ok.id = b.ok_profile_id
            LEFT JOIN channel_profiles alt ON alt.id = b.alt_profile_id
            WHERE b.id = $1 AND b.user_id = $2
            """,
            batch_id,
            user_id,
        )
        if row is None:
            raise NotFoundError("Batch not found.")
        return {
            "batch_id": str(batch_id),
            "auto_distrokid": bool(row["auto_distrokid"]),
            "auto_reel_after_video": bool(row["auto_reel_after_video"]),
            "ok_profile_id": str(row["ok_profile_id"] or "").strip(),
            "alt_profile_id": str(row["alt_profile_id"] or "").strip(),
            "primary_artist_name": str(row["primary_artist_name"] or "").strip(),
            "secondary_artist_name": str(row["secondary_artist_name"] or "").strip(),
            "primary_album_name": str(row["primary_album_name"] or "").strip(),
            "secondary_album_name": str(row["secondary_album_name"] or "").strip(),
        }

    async def list_history(self, *, user_id: UUID, limit: int) -> list[dict[str, Any]]:
        rows = await self._pool.fetch(
            "SELECT * FROM distrokid_upload_history WHERE user_id=$1 ORDER BY uploaded_at DESC LIMIT $2",
            user_id, max(1, min(limit, 200)),
        )
        return [dict(row) for row in rows]

    async def list_wav_sources(self, *, user_id: UUID, batch_id: UUID) -> list[dict[str, Any]]:
        """Return completed Suno clips for a batch (primary + secondary audio ids)."""
        await self._require_entitlement(user_id)
        rows = await self._pool.fetch(
            """
            SELECT
              st.external_task_id AS suno_task_id,
              st.audio_id_ok,
              st.audio_id_alt,
              st.song_id,
              st.batch_id,
              COALESCE(st.title, s.title, '') AS title,
              s.batch_index AS track_number,
              b.ok_run_dir,
              b.alt_run_dir,
              COALESCE(b.ok_album, b.alt_album, s.album, '') AS album_name
            FROM suno_tasks st
            LEFT JOIN songs s ON s.id = st.song_id
            LEFT JOIN batches b ON b.id = st.batch_id
            WHERE st.user_id = $1
              AND st.batch_id = $2
              AND st.external_task_id IS NOT NULL
              AND BTRIM(st.external_task_id) <> ''
              AND (
                (st.audio_id_ok IS NOT NULL AND BTRIM(st.audio_id_ok) <> '')
                OR (st.audio_id_alt IS NOT NULL AND BTRIM(st.audio_id_alt) <> '')
              )
            ORDER BY COALESCE(s.batch_index, 0), st.created_at
            """,
            user_id,
            batch_id,
        )
        items: list[dict[str, Any]] = []
        for row in rows:
            base = {
                "suno_task_id": str(row["suno_task_id"] or "").strip(),
                "song_id": str(row["song_id"]) if row["song_id"] else None,
                "batch_id": str(row["batch_id"]) if row["batch_id"] else None,
                "title": str(row["title"] or "").strip(),
                "track_number": int(row["track_number"]) if row["track_number"] is not None else None,
                "album_name": str(row["album_name"] or "").strip(),
                "ok_run_dir": str(row["ok_run_dir"] or "").strip() or None,
                "alt_run_dir": str(row["alt_run_dir"] or "").strip() or None,
            }
            if str(row["audio_id_ok"] or "").strip():
                items.append({**base, "role": "primary", "audio_id": str(row["audio_id_ok"]).strip()})
            if str(row["audio_id_alt"] or "").strip():
                items.append({**base, "role": "secondary", "audio_id": str(row["audio_id_alt"]).strip()})
        return items

    @staticmethod
    def _job(row: Any, **extra: Any) -> dict[str, Any]:
        payload = dict(row)
        payload.update(extra)
        return payload
