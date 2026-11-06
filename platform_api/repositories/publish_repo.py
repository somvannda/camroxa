"""Repository for Post for Me publishing accounts and jobs.

Jobs live in the existing ``youtube_upload_jobs`` table so the Progress,
Music History, and Admin Pipeline read paths keep working. Post for Me rows
use ``provider='postforme'`` and never the legacy ``pending`` status.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol


class DatabaseProtocol(Protocol):
    async def fetch(self, query: str, *args: Any) -> list[dict[str, Any]]: ...

    async def fetchrow(self, query: str, *args: Any) -> dict[str, Any] | None: ...

    async def execute(self, query: str, *args: Any) -> str: ...


@dataclass(frozen=True, slots=True)
class PublishAccountRecord:
    id: str
    user_id: str
    profile_id: str
    provider: str
    platform: str
    postforme_account_id: str
    external_id: str | None
    username: str | None
    display_name: str | None
    avatar_url: str | None
    status: str
    metadata: dict[str, Any]
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class PublishJobRecord:
    id: str
    user_id: str
    song_id: str | None
    job_uid: str
    batch_id: str | None
    profile_id: str | None
    role: str
    file_path: str | None
    title: str
    description: str | None
    tags: str | None
    privacy_status: str
    youtube_video_id: str | None
    youtube_url: str | None
    status: str
    attempt_count: int
    error_message: str | None
    provider: str
    platform: str
    social_account_id: str | None
    postforme_post_id: str | None
    postforme_result_id: str | None
    media_url: str | None
    upload_url: str | None
    upload_expires_at: datetime | None
    file_size_bytes: int | None
    file_checksum: str | None
    thumbnail_path: str | None
    thumbnail_media_url: str | None
    profile_config: dict[str, Any]
    credits_charged_units: int
    credit_ref_id: str | None
    error_code: str | None
    scheduled_at: datetime | None
    result_payload: dict[str, Any]
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class PublishConnectSessionRecord:
    id: str
    user_id: str
    profile_id: str
    platform: str
    status: str
    account_ids: list[str]
    error_message: str | None
    expires_at: datetime
    created_at: datetime | None = None
    updated_at: datetime | None = None


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def _as_str_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except Exception:
            return []
        if isinstance(parsed, list):
            return [str(item) for item in parsed if str(item).strip()]
    return []


def _row_to_account(row: dict[str, Any]) -> PublishAccountRecord:
    return PublishAccountRecord(
        id=str(row["id"]),
        user_id=str(row["user_id"]),
        profile_id=str(row["profile_id"]),
        provider=str(row.get("provider") or "postforme"),
        platform=str(row.get("platform") or "youtube"),
        postforme_account_id=str(row.get("postforme_account_id") or ""),
        external_id=str(row["external_id"]) if row.get("external_id") else None,
        username=str(row["username"]) if row.get("username") else None,
        display_name=str(row["display_name"]) if row.get("display_name") else None,
        avatar_url=str(row["avatar_url"]) if row.get("avatar_url") else None,
        status=str(row.get("status") or "connected"),
        metadata=_as_dict(row.get("metadata")),
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
    )


def _row_to_job(row: dict[str, Any]) -> PublishJobRecord:
    return PublishJobRecord(
        id=str(row["id"]),
        user_id=str(row["user_id"]),
        song_id=str(row["song_id"]) if row.get("song_id") else None,
        job_uid=str(row.get("job_uid") or ""),
        batch_id=str(row["batch_id"]) if row.get("batch_id") else None,
        profile_id=str(row["profile_id"]) if row.get("profile_id") else None,
        role=str(row.get("role") or "OK"),
        file_path=str(row["file_path"]) if row.get("file_path") else None,
        title=str(row.get("title") or ""),
        description=str(row["description"]) if row.get("description") else None,
        tags=str(row["tags"]) if row.get("tags") else None,
        privacy_status=str(row.get("privacy_status") or "private"),
        youtube_video_id=str(row["youtube_video_id"]) if row.get("youtube_video_id") else None,
        youtube_url=str(row["youtube_url"]) if row.get("youtube_url") else None,
        status=str(row.get("status") or "pending_upload"),
        attempt_count=int(row.get("attempt_count") or 0),
        error_message=str(row["error_message"]) if row.get("error_message") else None,
        provider=str(row.get("provider") or "youtube_direct"),
        platform=str(row.get("platform") or "youtube"),
        social_account_id=str(row["social_account_id"]) if row.get("social_account_id") else None,
        postforme_post_id=str(row["postforme_post_id"]) if row.get("postforme_post_id") else None,
        postforme_result_id=str(row["postforme_result_id"]) if row.get("postforme_result_id") else None,
        media_url=str(row["media_url"]) if row.get("media_url") else None,
        upload_url=str(row["upload_url"]) if row.get("upload_url") else None,
        upload_expires_at=row.get("upload_expires_at"),
        file_size_bytes=int(row["file_size_bytes"]) if row.get("file_size_bytes") is not None else None,
        file_checksum=str(row["file_checksum"]) if row.get("file_checksum") else None,
        thumbnail_path=str(row["thumbnail_path"]) if row.get("thumbnail_path") else None,
        thumbnail_media_url=str(row["thumbnail_media_url"]) if row.get("thumbnail_media_url") else None,
        profile_config=_as_dict(row.get("profile_config")),
        credits_charged_units=int(row.get("credits_charged_units") or 0),
        credit_ref_id=str(row["credit_ref_id"]) if row.get("credit_ref_id") else None,
        error_code=str(row["error_code"]) if row.get("error_code") else None,
        scheduled_at=row.get("scheduled_at"),
        result_payload=_as_dict(row.get("result_payload")),
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
    )


def _row_to_session(row: dict[str, Any]) -> PublishConnectSessionRecord:
    return PublishConnectSessionRecord(
        id=str(row["id"]),
        user_id=str(row["user_id"]),
        profile_id=str(row["profile_id"]),
        platform=str(row.get("platform") or "youtube"),
        status=str(row.get("status") or "pending_browser"),
        account_ids=_as_str_list(row.get("account_ids")),
        error_message=str(row["error_message"]) if row.get("error_message") else None,
        expires_at=row["expires_at"],
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
    )


_JOB_COLUMNS = """
    id, user_id, song_id, job_uid, batch_id, profile_id, role, file_path,
    title, description, tags, privacy_status, youtube_video_id, youtube_url,
    status, attempt_count, error_message, provider, platform,
    social_account_id, postforme_post_id, postforme_result_id, media_url,
    upload_url, upload_expires_at, file_size_bytes, file_checksum,
    thumbnail_path, thumbnail_media_url, profile_config, credits_charged_units,
    credit_ref_id, error_code, scheduled_at, result_payload, created_at, updated_at
"""


class PublishRepository:
    def __init__(self, db: DatabaseProtocol) -> None:
        self._db = db

    # --- Accounts -----------------------------------------------------------

    async def list_accounts(
        self, user_id: str, *, profile_id: str | None = None
    ) -> list[PublishAccountRecord]:
        rows = await self._db.fetch(
            """
            SELECT id, user_id, profile_id, provider, platform,
                   postforme_account_id, external_id, username, display_name,
                   avatar_url, status, metadata, created_at, updated_at
            FROM publish_social_accounts
            WHERE user_id = $1::uuid
              AND ($2::uuid IS NULL OR profile_id = $2::uuid)
              AND status = 'connected'
            ORDER BY created_at ASC
            """,
            user_id,
            profile_id,
        )
        return [_row_to_account(row) for row in rows]

    async def get_account(
        self, user_id: str, account_id: str
    ) -> PublishAccountRecord | None:
        row = await self._db.fetchrow(
            """
            SELECT id, user_id, profile_id, provider, platform,
                   postforme_account_id, external_id, username, display_name,
                   avatar_url, status, metadata, created_at, updated_at
            FROM publish_social_accounts
            WHERE user_id = $1::uuid AND id = $2::uuid
            """,
            user_id,
            account_id,
        )
        return _row_to_account(row) if row else None

    async def get_account_by_postforme_id(
        self, user_id: str, postforme_account_id: str
    ) -> PublishAccountRecord | None:
        row = await self._db.fetchrow(
            """
            SELECT id, user_id, profile_id, provider, platform,
                   postforme_account_id, external_id, username, display_name,
                   avatar_url, status, metadata, created_at, updated_at
            FROM publish_social_accounts
            WHERE user_id = $1::uuid
              AND postforme_account_id = $2
              AND status = 'connected'
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            user_id,
            postforme_account_id,
        )
        return _row_to_account(row) if row else None

    async def upsert_account(
        self,
        *,
        user_id: str,
        profile_id: str,
        platform: str,
        postforme_account_id: str,
        external_id: str | None,
        username: str | None,
        display_name: str | None,
        avatar_url: str | None,
        metadata: dict[str, Any] | None = None,
    ) -> PublishAccountRecord:
        row = await self._db.fetchrow(
            """
            INSERT INTO publish_social_accounts (
                user_id, profile_id, provider, platform, postforme_account_id,
                external_id, username, display_name, avatar_url, status, metadata
            )
            VALUES ($1::uuid, $2::uuid, 'postforme', $3, $4, $5, $6, $7, $8, 'connected', $9::jsonb)
            ON CONFLICT (user_id, profile_id, postforme_account_id)
            DO UPDATE SET
                external_id = EXCLUDED.external_id,
                username = EXCLUDED.username,
                display_name = EXCLUDED.display_name,
                avatar_url = EXCLUDED.avatar_url,
                status = 'connected',
                metadata = EXCLUDED.metadata,
                updated_at = NOW()
            RETURNING id, user_id, profile_id, provider, platform,
                      postforme_account_id, external_id, username, display_name,
                      avatar_url, status, metadata, created_at, updated_at
            """,
            user_id,
            profile_id,
            platform,
            postforme_account_id,
            external_id,
            username,
            display_name,
            avatar_url,
            json.dumps(metadata or {}),
        )
        if row is None:
            raise RuntimeError("Unable to save the Post for Me account link.")
        return _row_to_account(row)

    async def disconnect_account(self, user_id: str, account_id: str) -> bool:
        result = await self._db.execute(
            """
            UPDATE publish_social_accounts
            SET status = 'disconnected', updated_at = NOW()
            WHERE user_id = $1::uuid AND id = $2::uuid
            """,
            user_id,
            account_id,
        )
        return result.endswith("1")

    # --- Connect sessions ---------------------------------------------------

    async def create_connect_session(
        self,
        *,
        user_id: str,
        profile_id: str,
        platform: str,
        expires_at: datetime,
    ) -> PublishConnectSessionRecord:
        row = await self._db.fetchrow(
            """
            INSERT INTO publish_connect_sessions (user_id, profile_id, platform, expires_at)
            VALUES ($1::uuid, $2::uuid, $3, $4)
            RETURNING id, user_id, profile_id, platform, status, account_ids,
                      error_message, expires_at, created_at, updated_at
            """,
            user_id,
            profile_id,
            platform,
            expires_at,
        )
        if row is None:
            raise RuntimeError("Unable to create the Post for Me connect session.")
        return _row_to_session(row)

    async def latest_connect_session(
        self, user_id: str, profile_id: str
    ) -> PublishConnectSessionRecord | None:
        row = await self._db.fetchrow(
            """
            SELECT id, user_id, profile_id, platform, status, account_ids,
                   error_message, expires_at, created_at, updated_at
            FROM publish_connect_sessions
            WHERE user_id = $1::uuid AND profile_id = $2::uuid
            ORDER BY created_at DESC
            LIMIT 1
            """,
            user_id,
            profile_id,
        )
        return _row_to_session(row) if row else None

    async def list_pending_connect_sessions(
        self, platform: str, *, limit: int = 20
    ) -> list[PublishConnectSessionRecord]:
        rows = await self._db.fetch(
            """
            SELECT id, user_id, profile_id, platform, status, account_ids,
                   error_message, expires_at, created_at, updated_at
            FROM publish_connect_sessions
            WHERE platform = $1
              AND status = 'pending_browser'
              AND expires_at > NOW()
            ORDER BY created_at DESC
            LIMIT $2
            """,
            platform,
            max(1, min(50, int(limit))),
        )
        return [_row_to_session(row) for row in rows]

    async def finish_connect_session(
        self,
        session_id: str,
        *,
        status: str,
        account_ids: list[str] | None = None,
        error_message: str | None = None,
    ) -> None:
        await self._db.execute(
            """
            UPDATE publish_connect_sessions
            SET status = $2,
                account_ids = $3::jsonb,
                error_message = $4,
                updated_at = NOW()
            WHERE id = $1::uuid
            """,
            session_id,
            status,
            json.dumps(account_ids or []),
            error_message,
        )

    # --- Jobs ---------------------------------------------------------------

    async def create_job(
        self,
        *,
        user_id: str,
        job_uid: str,
        batch_id: str | None,
        profile_id: str,
        role: str,
        title: str,
        description: str | None,
        tags: list[str],
        privacy_status: str,
        social_account_id: str,
        platform: str,
        media_url: str,
        upload_url: str,
        upload_expires_at: datetime | None,
        file_path: str | None,
        file_size_bytes: int | None,
        file_checksum: str | None,
        thumbnail_path: str | None,
        thumbnail_media_url: str | None,
        profile_config: dict[str, Any] | None,
        scheduled_at: datetime | None,
    ) -> PublishJobRecord:
        row = await self._db.fetchrow(
            f"""
            INSERT INTO youtube_upload_jobs (
                user_id, job_uid, batch_id, profile_id, role, title, description,
                tags, privacy_status, status, provider, platform,
                social_account_id, media_url, upload_url, upload_expires_at,
                file_path, file_size_bytes, file_checksum, thumbnail_path,
                thumbnail_media_url, profile_config, scheduled_at
            )
            VALUES (
                $1::uuid, $2, $3::uuid, $4::uuid, $5, $6, $7, $8, $9,
                'pending_upload', 'postforme', $10, $11, $12, $13, $14,
                $15, $16, $17, $18, $19, $20::jsonb, $21
            )
            RETURNING {_JOB_COLUMNS}
            """,
            user_id,
            job_uid,
            batch_id,
            profile_id,
            role,
            title,
            description,
            ",".join(tags) if tags else None,
            privacy_status,
            platform,
            social_account_id,
            media_url,
            upload_url,
            upload_expires_at,
            file_path,
            file_size_bytes,
            file_checksum,
            thumbnail_path,
            thumbnail_media_url,
            json.dumps(profile_config or {}),
            scheduled_at,
        )
        if row is None:
            raise RuntimeError("Unable to create the Post for Me publish job.")
        return _row_to_job(row)

    async def get_job(self, user_id: str, job_uid: str) -> PublishJobRecord | None:
        row = await self._db.fetchrow(
            f"""
            SELECT {_JOB_COLUMNS}
            FROM youtube_upload_jobs
            WHERE user_id = $1::uuid AND job_uid = $2
            """,
            user_id,
            job_uid,
        )
        return _row_to_job(row) if row else None

    async def get_job_by_post_id(self, postforme_post_id: str) -> PublishJobRecord | None:
        row = await self._db.fetchrow(
            f"""
            SELECT {_JOB_COLUMNS}
            FROM youtube_upload_jobs
            WHERE provider = 'postforme' AND postforme_post_id = $1
            ORDER BY created_at DESC
            LIMIT 1
            """,
            postforme_post_id,
        )
        return _row_to_job(row) if row else None

    async def latest_media_job(
        self,
        *,
        user_id: str,
        batch_id: str,
        role: str,
        size_bytes: int,
        max_age_days: int = 6,
    ) -> PublishJobRecord | None:
        """Newest job for this slot whose original is still hosted and readable."""
        row = await self._db.fetchrow(
            f"""
            SELECT {_JOB_COLUMNS}
            FROM youtube_upload_jobs
            WHERE user_id = $1::uuid
              AND batch_id = $2::uuid
              AND role = $3
              AND media_url IS NOT NULL
              AND file_size_bytes = $4
              AND created_at > NOW() - make_interval(days => $5)
            ORDER BY created_at DESC
            LIMIT 1
            """,
            user_id,
            batch_id,
            role,
            int(size_bytes),
            int(max_age_days),
        )
        return _row_to_job(row) if row else None

    async def latest_job_for_slot(
        self,
        *,
        user_id: str,
        batch_id: str,
        profile_id: str,
        role: str,
    ) -> PublishJobRecord | None:
        """Newest job for one batch/channel/role — the unit a publish covers."""
        row = await self._db.fetchrow(
            f"""
            SELECT {_JOB_COLUMNS}
            FROM youtube_upload_jobs
            WHERE user_id = $1::uuid
              AND batch_id = $2::uuid
              AND profile_id = $3::uuid
              AND role = $4
            ORDER BY created_at DESC
            LIMIT 1
            """,
            user_id,
            batch_id,
            profile_id,
            role,
        )
        return _row_to_job(row) if row else None

    async def list_jobs(
        self,
        user_id: str,
        *,
        batch_id: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[PublishJobRecord]:
        rows = await self._db.fetch(
            f"""
            SELECT {_JOB_COLUMNS}
            FROM youtube_upload_jobs
            WHERE user_id = $1::uuid
              AND provider = 'postforme'
              AND ($2::uuid IS NULL OR batch_id = $2::uuid)
              AND ($3::text IS NULL OR status = $3)
            ORDER BY created_at DESC
            LIMIT $4
            """,
            user_id,
            batch_id,
            status,
            max(1, min(200, int(limit))),
        )
        return [_row_to_job(row) for row in rows]

    async def list_processing_jobs(self, *, older_than_seconds: int = 600) -> list[PublishJobRecord]:
        rows = await self._db.fetch(
            f"""
            SELECT {_JOB_COLUMNS}
            FROM youtube_upload_jobs
            WHERE provider = 'postforme'
              AND status IN ('queued', 'processing')
              AND updated_at <= NOW() - make_interval(secs => $1::int)
            ORDER BY updated_at ASC
            LIMIT 100
            """,
            max(60, int(older_than_seconds)),
        )
        return [_row_to_job(row) for row in rows]

    async def expire_pending_uploads(self) -> int:
        """Fail jobs whose presigned upload URL expired before the file arrived.

        Without this, an abandoned or failed direct upload leaves
        ``pending_upload`` forever, so Progress keeps showing "Uploading 0/1".
        """
        rows = await self._db.fetch(
            """
            UPDATE youtube_upload_jobs
            SET status = 'failed',
                error_code = 'UPLOAD_EXPIRED',
                error_message = 'Upload URL expired before the file arrived.',
                updated_at = NOW()
            WHERE status = 'pending_upload'
              AND upload_expires_at IS NOT NULL
              AND upload_expires_at < NOW()
            RETURNING id
            """
        )
        return len(rows or [])

    async def set_job_status(
        self,
        job_id: str,
        *,
        status: str,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> None:
        await self._db.execute(
            """
            UPDATE youtube_upload_jobs
            SET status = $2,
                error_code = $3,
                error_message = $4,
                updated_at = NOW()
            WHERE id = $1::uuid
            """,
            job_id,
            status,
            error_code,
            error_message,
        )

    async def mark_job_charged(
        self,
        job_id: str,
        *,
        credits_charged_units: int,
        credit_ref_id: str,
        status: str,
    ) -> None:
        await self._db.execute(
            """
            UPDATE youtube_upload_jobs
            SET credits_charged_units = $2,
                credit_ref_id = $3,
                status = $4,
                error_code = NULL,
                error_message = NULL,
                updated_at = NOW()
            WHERE id = $1::uuid
            """,
            job_id,
            int(credits_charged_units),
            credit_ref_id,
            status,
        )

    async def mark_job_posted(
        self,
        job_id: str,
        *,
        postforme_post_id: str,
        status: str = "processing",
        attempt_count: int | None = None,
    ) -> None:
        await self._db.execute(
            """
            UPDATE youtube_upload_jobs
            SET postforme_post_id = $2,
                status = $3,
                attempt_count = COALESCE($4, attempt_count),
                error_code = NULL,
                error_message = NULL,
                updated_at = NOW()
            WHERE id = $1::uuid
            """,
            job_id,
            postforme_post_id,
            status,
            attempt_count,
        )

    async def mark_job_success(
        self,
        job_id: str,
        *,
        platform_post_id: str | None,
        platform_url: str | None,
        result_payload: dict[str, Any] | None = None,
    ) -> None:
        await self._db.execute(
            """
            UPDATE youtube_upload_jobs
            SET status = 'success',
                youtube_video_id = COALESCE($2, youtube_video_id),
                youtube_url = COALESCE($3, youtube_url),
                error_code = NULL,
                error_message = NULL,
                result_payload = $4::jsonb,
                updated_at = NOW()
            WHERE id = $1::uuid
            """,
            job_id,
            platform_post_id,
            platform_url,
            json.dumps(result_payload or {}),
        )

    async def mark_job_refunded(
        self,
        job_id: str,
        *,
        credits_charged_units: int,
        error_code: str | None,
        error_message: str | None,
        status: str = "failed",
    ) -> None:
        await self._db.execute(
            """
            UPDATE youtube_upload_jobs
            SET status = $2,
                credits_charged_units = $3,
                error_code = $4,
                error_message = $5,
                updated_at = NOW()
            WHERE id = $1::uuid
            """,
            job_id,
            status,
            int(credits_charged_units),
            error_code,
            error_message,
        )

    async def reset_job_for_retry(
        self,
        job_id: str,
        *,
        media_url: str,
        upload_url: str,
        upload_expires_at: datetime | None,
    ) -> None:
        await self._db.execute(
            """
            UPDATE youtube_upload_jobs
            SET status = 'pending_upload',
                media_url = $2,
                upload_url = $3,
                upload_expires_at = $4,
                postforme_post_id = NULL,
                postforme_result_id = NULL,
                error_code = NULL,
                error_message = NULL,
                attempt_count = COALESCE(attempt_count, 0) + 1,
                updated_at = NOW()
            WHERE id = $1::uuid
            """,
            job_id,
            media_url,
            upload_url,
            upload_expires_at,
        )

    # --- Results ------------------------------------------------------------

    async def upsert_result(
        self,
        *,
        job_id: str,
        platform: str,
        social_account_id: str,
        postforme_result_id: str | None,
        success: bool,
        platform_post_id: str | None,
        platform_url: str | None,
        error_message: str | None,
        details: dict[str, Any] | None = None,
    ) -> None:
        await self._db.execute(
            """
            INSERT INTO publish_job_results (
                job_id, platform, social_account_id, postforme_result_id,
                success, platform_post_id, platform_url, error_message, details
            )
            VALUES ($1::uuid, $2, $3, $4, $5, $6, $7, $8, $9::jsonb)
            ON CONFLICT (postforme_result_id) DO UPDATE SET
                success = EXCLUDED.success,
                platform_post_id = EXCLUDED.platform_post_id,
                platform_url = EXCLUDED.platform_url,
                error_message = EXCLUDED.error_message,
                details = EXCLUDED.details,
                updated_at = NOW()
            """,
            job_id,
            platform,
            social_account_id,
            postforme_result_id,
            bool(success),
            platform_post_id,
            platform_url,
            error_message,
            json.dumps(details or {}),
        )

    async def count_results(self, job_id: str) -> tuple[int, int]:
        row = await self._db.fetchrow(
            """
            SELECT COUNT(*)::int AS total,
                   COUNT(*) FILTER (WHERE success)::int AS succeeded
            FROM publish_job_results
            WHERE job_id = $1::uuid
            """,
            job_id,
        )
        if row is None:
            return (0, 0)
        return (int(row.get("total") or 0), int(row.get("succeeded") or 0))

    # --- Webhook ledger -----------------------------------------------------

    async def insert_webhook_event(
        self,
        *,
        event_type: str,
        postforme_post_id: str | None,
        payload: dict[str, Any],
    ) -> str:
        row = await self._db.fetchrow(
            """
            INSERT INTO publish_webhook_events (event_type, postforme_post_id, payload)
            VALUES ($1, $2, $3::jsonb)
            RETURNING id
            """,
            event_type,
            postforme_post_id,
            json.dumps(payload or {}),
        )
        return str(row["id"]) if row else ""

    async def mark_webhook_processed(
        self, event_id: str, *, error_message: str | None = None
    ) -> None:
        await self._db.execute(
            """
            UPDATE publish_webhook_events
            SET processed_at = NOW(), error_message = $2
            WHERE id = $1::uuid
            """,
            event_id,
            error_message,
        )
