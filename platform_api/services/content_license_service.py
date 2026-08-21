"""User/device content licenses, short-lived session keys, and play/export policy."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Literal
from uuid import UUID

from platform_api.config import get_settings
from platform_api.exceptions import ForbiddenError, NotFoundError, ValidationError
from platform_api.services.audio_packager import derive_kek, unwrap_content_key

logger = logging.getLogger(__name__)

DEVICE_CAP = 5
SESSION_TTL_SECONDS = 120
REDIS_PREFIX = "web_music:content_session:"
DECRYPT_MODULE_VERSION = "camxora-decrypt-webcrypto-v1"
Purpose = Literal["play", "export", "admin_play", "admin_export", "studio_redownload"]
PLAY_SOURCES = frozenset(
    {
        "home",
        "explore",
        "search",
        "genre",
        "artist",
        "album",
        "playlist",
        "library",
        "create",
        "share",
        "unknown",
    }
)
CLIENT_TRACE_EVENTS = frozenset(
    {
        "play_start",
        "play_session",
        "play_path",
        "play_chunks",
        "play_decode",
        "play_ok",
        "play_error",
    }
)


def decrypt_module_hash() -> str:
    return hashlib.sha256(DECRYPT_MODULE_VERSION.encode("utf-8")).hexdigest()


def _peppered_ip_hash(ip: str | None) -> str:
    raw = (ip or "unknown").encode("utf-8")
    secret = (get_settings().encryption_master_key or get_settings().jwt_secret or "camxora-dev").encode(
        "utf-8"
    )
    return hmac.new(secret, raw, hashlib.sha256).hexdigest()[:32]


def _session_bind_token(*, user_id: UUID, subject_id: UUID, session_id: UUID) -> str:
    secret = (get_settings().encryption_master_key or get_settings().jwt_secret or "camxora-dev").encode(
        "utf-8"
    )
    msg = f"{user_id}:{subject_id}:{session_id}".encode("utf-8")
    return hmac.new(secret, msg, hashlib.sha256).hexdigest()[:40]


def resolve_audio_kek() -> bytes:
    settings = get_settings()
    secret = (settings.content_audio_kek or settings.encryption_master_key or "").strip()
    if not secret:
        secret = (settings.jwt_secret or "camxora-dev-content-kek") + "::content-audio"
        logger.warning("CONTENT_AUDIO_KEK unset; using derived local fallback.")
    return derive_kek(secret)


def _ip_hash(ip: str | None) -> str:
    return _peppered_ip_hash(ip)


class ContentLicenseService:
    def __init__(self, pool: Any, redis: Any | None = None) -> None:
        self._pool = pool
        self._redis = redis

    async def register_device(
        self,
        user_id: UUID,
        *,
        device_public_id: str,
        platform: str = "music_web",
        user_agent: str | None = None,
        webcrypto_spki: bytes | None = None,
    ) -> dict[str, Any]:
        public_id = str(device_public_id or "").strip()[:128]
        if len(public_id) < 8:
            raise ValidationError("device_public_id is required.", details={"field": "device_public_id"})
        platform_key = str(platform or "music_web").strip()[:32] or "music_web"
        ua_hash = hashlib.sha256((user_agent or "").encode("utf-8")).hexdigest()[:32]
        row = await self._pool.fetchrow(
            """
            INSERT INTO playback_devices (
                user_id, device_public_id, platform, ua_hash, webcrypto_spki, status, last_seen_at
            )
            VALUES ($1, $2, $3, $4, $5, 'active', NOW())
            ON CONFLICT (user_id, device_public_id) DO UPDATE SET
                platform = EXCLUDED.platform,
                ua_hash = EXCLUDED.ua_hash,
                webcrypto_spki = COALESCE(EXCLUDED.webcrypto_spki, playback_devices.webcrypto_spki),
                last_seen_at = NOW(),
                status = 'active'
            RETURNING id, device_public_id, platform, status, created_at
            """,
            user_id,
            public_id,
            platform_key,
            ua_hash,
            webcrypto_spki,
        )
        await self._enforce_device_cap(user_id)
        return {
            "id": str(row["id"]),
            "device_public_id": row["device_public_id"],
            "platform": row["platform"],
            "status": row["status"],
            "decrypt_module_hash": decrypt_module_hash(),
        }

    async def _enforce_device_cap(self, user_id: UUID) -> None:
        rows = await self._pool.fetch(
            """
            SELECT id FROM playback_devices
            WHERE user_id = $1 AND status = 'active'
            ORDER BY last_seen_at ASC
            """,
            user_id,
        )
        extra = len(rows) - DEVICE_CAP
        if extra <= 0:
            return
        for row in rows[:extra]:
            await self._pool.execute(
                "UPDATE playback_devices SET status = 'revoked' WHERE id = $1",
                row["id"],
            )

    async def _get_device(self, user_id: UUID, device_public_id: str) -> Any:
        row = await self._pool.fetchrow(
            """
            SELECT id, status FROM playback_devices
            WHERE user_id = $1 AND device_public_id = $2
            """,
            user_id,
            device_public_id,
        )
        if row is None or str(row["status"]) != "active":
            raise ForbiddenError("Register this device before requesting a license.")
        await self._pool.execute(
            "UPDATE playback_devices SET last_seen_at = NOW() WHERE id = $1",
            row["id"],
        )
        return row

    async def _active_paid(self, user_id: UUID) -> bool:
        row = await self._pool.fetchrow(
            """
            SELECT 1
            FROM web_subscriptions
            WHERE user_id = $1
              AND status = 'active'
              AND (cancel_at_period_end = false OR current_period_end > NOW())
            LIMIT 1
            """,
            user_id,
        )
        if row is not None:
            return True
        desktop = await self._pool.fetchrow(
            """
            SELECT 1 FROM licenses
            WHERE user_id = $1
              AND status = 'active'
              AND (expires_at IS NULL OR expires_at > NOW())
            LIMIT 1
            """,
            user_id,
        )
        return desktop is not None

    async def assert_play_access(
        self,
        user_id: UUID,
        *,
        subject_type: str,
        subject_id: UUID,
        variant: str,
        is_admin: bool = False,
    ) -> dict[str, Any]:
        if is_admin:
            return {"access": "admin"}
        if subject_type == "stream_track":
            track = await self._pool.fetchrow(
                """
                SELECT id, user_id, publish_status, package_status, content_key_id,
                       packaged_storage_key, packaged_storage_key_b, variant
                FROM stream_tracks
                WHERE id = $1
                """,
                subject_id,
            )
            if track is None:
                raise NotFoundError("Track not found.")
            published = str(track["publish_status"] or "") == "published"
            owner = str(track["user_id"]) == str(user_id)
            if not published and not owner:
                raise ForbiddenError("This track is private.")
            return {"access": "play", "row": track, "owner": owner}
        if subject_type == "suno_task":
            task = await self._pool.fetchrow(
                """
                SELECT id, user_id, source,
                       package_status_ok, package_status_alt,
                       content_key_id_ok, content_key_id_alt,
                       packaged_storage_key_ok, packaged_storage_key_alt,
                       packaged_storage_key_ok_b, packaged_storage_key_alt_b,
                       encrypted_original_key_ok, encrypted_original_key_alt,
                       b2_storage_key_ok, b2_storage_key_alt
                FROM suno_tasks
                WHERE id = $1
                """,
                subject_id,
            )
            if task is None:
                raise NotFoundError("Generation not found.")
            owner = str(task["user_id"]) == str(user_id)
            if not owner:
                public = await self._pool.fetchrow(
                    """
                    SELECT 1
                    FROM web_music_playlist_items i
                    JOIN web_music_playlists p ON p.id = i.playlist_id AND p.is_public = TRUE
                    WHERE i.suno_task_id = $1 AND i.variant = $2
                    LIMIT 1
                    """,
                    subject_id,
                    variant,
                )
                if public is None:
                    raise ForbiddenError("This track is private.")
            return {"access": "play", "row": task, "owner": owner}
        raise ValidationError("Unknown subject_type.", details={"field": "subject_type"})

    async def assert_export_access(
        self,
        user_id: UUID,
        task_id: UUID,
        *,
        is_admin: bool = False,
    ) -> Any:
        task = await self._pool.fetchrow(
            "SELECT id, user_id, source FROM suno_tasks WHERE id = $1",
            task_id,
        )
        if task is None:
            raise NotFoundError("Generation not found.")
        if is_admin:
            return task
        if str(task["user_id"]) != str(user_id):
            raise ForbiddenError("You can only download your own tracks.")
        if not await self._active_paid(user_id):
            raise ForbiddenError(
                "Downloads require a paid subscription. Upgrade to download MP3, WAV, LRC, and SRT files.",
                details={"code": "download_requires_subscription"},
            )
        return task

    async def create_session(
        self,
        user_id: UUID,
        *,
        device_public_id: str,
        subject_type: str,
        subject_id: UUID,
        variant: str = "ok",
        purpose: Purpose = "play",
        wasm_hash: str | None = None,
        ip: str | None = None,
        is_admin: bool = False,
        user_agent: str | None = None,
        play_source: str | None = None,
        search_query: str | None = None,
        country: str | None = None,
    ) -> dict[str, Any]:
        variant_key = str(variant or "ok").strip().lower()
        if variant_key not in {"ok", "alt"}:
            raise ValidationError("variant must be ok or alt.")
        if purpose in {"export", "admin_export", "studio_redownload"}:
            await self.assert_export_access(user_id, subject_id, is_admin=is_admin or purpose.startswith("admin"))
        else:
            await self.assert_play_access(
                user_id,
                subject_type=subject_type,
                subject_id=subject_id,
                variant=variant_key,
                is_admin=is_admin,
            )
        device = await self._get_device(user_id, device_public_id)
        expected_hash = decrypt_module_hash()
        if wasm_hash and wasm_hash != expected_hash:
            await self.record_playback_event(
                user_id=user_id,
                device_id=device["id"],
                subject_type=subject_type,
                subject_id=subject_id,
                variant=variant_key,
                event="tamper",
            )
            raise ForbiddenError("Player integrity check failed.")

        key_row, package_status, packaged_key, packaged_key_b = await self._resolve_content_key(
            subject_type, subject_id, variant_key
        )
        lane = "b" if (user_id.int & 1) and packaged_key_b else "a"
        selected_package = packaged_key_b if lane == "b" and packaged_key_b else packaged_key

        expires_at = datetime.now(timezone.utc) + timedelta(seconds=SESSION_TTL_SECONDS)
        session_row = await self._pool.fetchrow(
            """
            INSERT INTO content_license_sessions (
                user_id, device_id, purpose, subject_type, subject_id, variant,
                content_key_id, expires_at, wasm_hash, ip_hash
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            RETURNING id
            """,
            user_id,
            device["id"],
            purpose,
            subject_type,
            subject_id,
            variant_key,
            None if key_row is None else key_row["id"],
            expires_at,
            wasm_hash or expected_hash,
            _ip_hash(ip),
        )
        bind = _session_bind_token(
            user_id=user_id, subject_id=subject_id, session_id=session_row["id"]
        )
        source = (play_source or "unknown").strip().lower()
        if source not in PLAY_SOURCES:
            source = "unknown"
        query = (search_query or "").strip()[:200] if source == "search" else None
        country_code = (country or "").strip().upper()[:8] or None
        await self._pool.execute(
            """
            UPDATE content_license_sessions
            SET play_source = $2, search_query = $3, country = $4, session_bind = $5
            WHERE id = $1
            """,
            session_row["id"],
            source,
            query,
            country_code,
            bind,
        )
        token = secrets.token_urlsafe(32)
        content_key_b64 = None
        if key_row is not None:
            try:
                kek = resolve_audio_kek()
                raw = unwrap_content_key(kek, bytes(key_row["wrapped_key"]))
                content_key_b64 = raw.hex()
            except Exception as exc:
                logger.warning("Failed to unwrap content key: %s", exc)
                content_key_b64 = None
        payload = {
            "session_id": str(session_row["id"]),
            "user_id": str(user_id),
            "device_id": str(device["id"]),
            "purpose": purpose,
            "subject_type": subject_type,
            "subject_id": str(subject_id),
            "variant": variant_key,
            "content_key_id": None if key_row is None else str(key_row["id"]),
            "package_status": package_status,
            "packaged_storage_key": selected_package,
            "lane": lane,
            "session_bind": bind,
        }
        if self._redis is not None:
            await self._redis.setex(
                f"{REDIS_PREFIX}{token}",
                SESSION_TTL_SECONDS,
                json.dumps(payload),
            )
        await self.record_playback_event(
            user_id=user_id,
            device_id=device["id"],
            session_id=session_row["id"],
            subject_type=subject_type,
            subject_id=subject_id,
            variant=variant_key,
            event="start",
            package_status=package_status,
        )
        del user_agent
        ready = package_status == "ready" and bool(selected_package) and bool(content_key_b64)
        segment_url = f"/api/v1/web-music/licenses/segments/{token}" if ready else ""
        return {
            "token": token,
            "expires_at": expires_at.isoformat(),
            "package_status": package_status,
            "ready": ready,
            "content_key": content_key_b64,
            "content_key_id": None if key_row is None else str(key_row["id"]),
            "segment_url": segment_url,
            "lane": lane,
            "decrypt_module_hash": expected_hash,
            "ttl_seconds": SESSION_TTL_SECONDS,
            "subject_type": subject_type,
            "subject_id": str(subject_id),
            "variant": variant_key,
            "session_bind": bind,
        }

    async def _resolve_content_key(
        self, subject_type: str, subject_id: UUID, variant: str
    ) -> tuple[Any | None, str, str | None, str | None]:
        if subject_type == "stream_track":
            row = await self._pool.fetchrow(
                """
                SELECT package_status, content_key_id, packaged_storage_key, packaged_storage_key_b
                FROM stream_tracks WHERE id = $1
                """,
                subject_id,
            )
            if row is None:
                return None, "none", None, None
            key = None
            if row["content_key_id"]:
                key = await self._pool.fetchrow(
                    "SELECT id, wrapped_key FROM content_keys WHERE id = $1 AND status = 'active'",
                    row["content_key_id"],
                )
            return (
                key,
                str(row["package_status"] or "none"),
                str(row["packaged_storage_key"] or "") or None,
                str(row["packaged_storage_key_b"] or "") or None,
            )
        status_col = "package_status_ok" if variant == "ok" else "package_status_alt"
        key_col = "content_key_id_ok" if variant == "ok" else "content_key_id_alt"
        pkg_col = "packaged_storage_key_ok" if variant == "ok" else "packaged_storage_key_alt"
        pkg_b_col = "packaged_storage_key_ok_b" if variant == "ok" else "packaged_storage_key_alt_b"
        row = await self._pool.fetchrow(
            f"""
            SELECT {status_col} AS package_status, {key_col} AS content_key_id,
                   {pkg_col} AS packaged_storage_key, {pkg_b_col} AS packaged_storage_key_b
            FROM suno_tasks WHERE id = $1
            """,
            subject_id,
        )
        if row is None:
            return None, "none", None, None
        key = None
        if row["content_key_id"]:
            key = await self._pool.fetchrow(
                "SELECT id, wrapped_key FROM content_keys WHERE id = $1 AND status = 'active'",
                row["content_key_id"],
            )
        return (
            key,
            str(row["package_status"] or "none"),
            str(row["packaged_storage_key"] or "") or None,
            str(row["packaged_storage_key_b"] or "") or None,
        )

    async def resolve_session(self, token: str) -> dict[str, Any] | None:
        if self._redis is None:
            return None
        raw = await self._redis.get(f"{REDIS_PREFIX}{token}")
        if not raw:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        try:
            data = json.loads(str(raw))
        except (TypeError, ValueError, json.JSONDecodeError):
            return None
        return data if isinstance(data, dict) else None

    async def heartbeat(
        self,
        user_id: UUID,
        token: str,
        *,
        event: str = "heartbeat",
        bytes_served: int = 0,
        position_seconds: float = 0,
        playback_rate: float = 1.0,
        seq: int = 0,
        session_bind: str | None = None,
        is_admin: bool = False,
        user_agent: str | None = None,
        ip: str | None = None,
    ) -> dict[str, Any]:
        session = await self.resolve_session(token)
        if session is None or str(session.get("user_id")) != str(user_id):
            raise NotFoundError("License session expired or invalid.")
        if session_bind and str(session.get("session_bind") or "") and str(session.get("session_bind")) != str(session_bind):
            raise ForbiddenError("License session bind mismatch.")
        if self._redis is not None:
            await self._redis.expire(f"{REDIS_PREFIX}{token}", SESSION_TTL_SECONDS)
        await self.record_playback_event(
            user_id=user_id,
            device_id=UUID(str(session["device_id"])) if session.get("device_id") else None,
            session_id=UUID(str(session["session_id"])) if session.get("session_id") else None,
            subject_type=str(session.get("subject_type") or ""),
            subject_id=UUID(str(session["subject_id"])) if session.get("subject_id") else None,
            variant=str(session.get("variant") or "ok"),
            event=event,
            bytes_served=bytes_served,
            package_status=str(session.get("package_status") or ""),
        )
        del position_seconds, playback_rate, seq, is_admin, user_agent, ip
        return {"ok": True, "ttl_seconds": SESSION_TTL_SECONDS, "accepted": True}

    async def record_client_trace(
        self,
        user_id: UUID,
        *,
        token: str | None,
        event: str,
        detail: str | None,
        user_agent: str | None = None,
        ip: str | None = None,
    ) -> dict[str, Any]:
        name = (event or "").strip()[:64]
        if name not in CLIENT_TRACE_EVENTS:
            name = "play_error"
        note = (detail or "").strip()[:500] or None
        session = await self.resolve_session(token) if token else None
        if session is not None and str(session.get("user_id")) != str(user_id):
            session = None
        logger.info(
            "music_web_play_trace user=%s event=%s detail=%s ua=%s ip=%s subject=%s/%s package=%s",
            user_id,
            name,
            note or "-",
            (user_agent or "")[:180],
            ip or "-",
            session.get("subject_type") if session else "-",
            session.get("subject_id") if session else "-",
            session.get("package_status") if session else "-",
        )
        await self.record_playback_event(
            user_id=user_id,
            device_id=UUID(str(session["device_id"])) if session and session.get("device_id") else None,
            session_id=UUID(str(session["session_id"])) if session and session.get("session_id") else None,
            subject_type=str(session.get("subject_type") or "") if session else None,
            subject_id=UUID(str(session["subject_id"])) if session and session.get("subject_id") else None,
            variant=str(session.get("variant") or "ok") if session else None,
            event=name,
            package_status=str(session.get("package_status") or "") if session else None,
            detail=note,
        )
        return {"ok": True}

    async def record_playback_event(
        self,
        *,
        user_id: UUID | None,
        device_id: UUID | None = None,
        session_id: UUID | None = None,
        subject_type: str | None = None,
        subject_id: UUID | None = None,
        variant: str | None = None,
        event: str,
        bytes_served: int = 0,
        package_status: str | None = None,
        detail: str | None = None,
    ) -> None:
        try:
            await self._pool.execute(
                """
                INSERT INTO playback_events (
                    user_id, device_id, session_id, subject_type, subject_id,
                    variant, event, bytes_served, package_status, detail
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                """,
                user_id,
                device_id,
                session_id,
                subject_type,
                subject_id,
                variant,
                event,
                int(bytes_served or 0),
                package_status,
                detail,
            )
        except Exception as exc:
            logger.warning("playback_events insert failed: %s", exc)

    async def record_export_event(
        self,
        *,
        user_id: UUID,
        suno_task_id: UUID | None,
        variant: str,
        format: str,
        actor: str,
        ip: str | None = None,
        device_id: UUID | None = None,
        watermark_id: UUID | None = None,
    ) -> UUID | None:
        try:
            row = await self._pool.fetchrow(
                """
                INSERT INTO export_events (
                    user_id, device_id, suno_task_id, variant, format, watermark_id, actor, ip_hash
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                RETURNING id
                """,
                user_id,
                device_id,
                suno_task_id,
                variant,
                format,
                watermark_id,
                actor,
                _ip_hash(ip),
            )
            return row["id"] if row else None
        except Exception as exc:
            logger.warning("export_events insert failed: %s", exc)
            return None

    async def list_playback_events(
        self, *, user_id: str | None = None, limit: int = 50, offset: int = 0
    ) -> dict[str, Any]:
        limit = max(1, min(int(limit or 50), 200))
        offset = max(0, int(offset or 0))
        if user_id:
            rows = await self._pool.fetch(
                """
                SELECT id, user_id, device_id, session_id, subject_type, subject_id,
                       variant, event, bytes_served, package_status, detail, created_at
                FROM playback_events
                WHERE user_id = $1
                ORDER BY created_at DESC
                LIMIT $2 OFFSET $3
                """,
                UUID(str(user_id)),
                limit,
                offset,
            )
            total = await self._pool.fetchval(
                "SELECT COUNT(*) FROM playback_events WHERE user_id = $1",
                UUID(str(user_id)),
            )
        else:
            rows = await self._pool.fetch(
                """
                SELECT id, user_id, device_id, session_id, subject_type, subject_id,
                       variant, event, bytes_served, package_status, detail, created_at
                FROM playback_events
                ORDER BY created_at DESC
                LIMIT $1 OFFSET $2
                """,
                limit,
                offset,
            )
            total = await self._pool.fetchval("SELECT COUNT(*) FROM playback_events")
        return {
            "items": [
                {
                    "id": int(r["id"]),
                    "user_id": str(r["user_id"]) if r["user_id"] else None,
                    "device_id": str(r["device_id"]) if r["device_id"] else None,
                    "subject_type": r["subject_type"],
                    "subject_id": str(r["subject_id"]) if r["subject_id"] else None,
                    "variant": r["variant"],
                    "event": r["event"],
                    "bytes_served": int(r["bytes_served"] or 0),
                    "package_status": r["package_status"],
                    "detail": r["detail"],
                    "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                }
                for r in rows
            ],
            "total": int(total or 0),
            "limit": limit,
            "offset": offset,
        }

    async def list_export_events(
        self, *, user_id: str | None = None, limit: int = 50, offset: int = 0
    ) -> dict[str, Any]:
        limit = max(1, min(int(limit or 50), 200))
        offset = max(0, int(offset or 0))
        if user_id:
            rows = await self._pool.fetch(
                """
                SELECT id, user_id, suno_task_id, variant, format, actor, watermark_id, created_at
                FROM export_events
                WHERE user_id = $1
                ORDER BY created_at DESC
                LIMIT $2 OFFSET $3
                """,
                UUID(str(user_id)),
                limit,
                offset,
            )
            total = await self._pool.fetchval(
                "SELECT COUNT(*) FROM export_events WHERE user_id = $1",
                UUID(str(user_id)),
            )
        else:
            rows = await self._pool.fetch(
                """
                SELECT id, user_id, suno_task_id, variant, format, actor, watermark_id, created_at
                FROM export_events
                ORDER BY created_at DESC
                LIMIT $1 OFFSET $2
                """,
                limit,
                offset,
            )
            total = await self._pool.fetchval("SELECT COUNT(*) FROM export_events")
        return {
            "items": [
                {
                    "id": str(r["id"]),
                    "user_id": str(r["user_id"]) if r["user_id"] else None,
                    "suno_task_id": str(r["suno_task_id"]) if r["suno_task_id"] else None,
                    "variant": r["variant"],
                    "format": r["format"],
                    "actor": r["actor"],
                    "watermark_id": str(r["watermark_id"]) if r["watermark_id"] else None,
                    "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                }
                for r in rows
            ],
            "total": int(total or 0),
            "limit": limit,
            "offset": offset,
        }
