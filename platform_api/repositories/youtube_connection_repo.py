"""Repository for YouTube connection sessions and connected accounts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class YouTubeConnectedAccountRecord:
    id: str
    user_id: str
    profile_id: str
    oauth_app_id: str | None
    channel_id: str
    channel_title: str
    encrypted_refresh_token: bytes
    scopes: list[str]
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class YouTubeConnectSessionRecord:
    id: str
    user_id: str
    profile_id: str
    oauth_app_id: str
    state_token: str
    code_verifier: str | None
    status: str
    encrypted_refresh_token: bytes | None
    scopes: list[str]
    channels: list[dict[str, str]]
    error_message: str | None
    expires_at: datetime
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class YouTubeUploadJobRecord:
    id: str
    user_id: str
    song_id: str | None
    job_uid: str | None
    batch_id: str | None
    profile_id: str | None
    role: str | None
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
    created_at: datetime | None = None
    updated_at: datetime | None = None


class DatabaseProtocol(Protocol):
    async def fetch(self, query: str, *args: Any) -> list[dict[str, Any]]: ...

    async def fetchrow(self, query: str, *args: Any) -> dict[str, Any] | None: ...

    async def execute(self, query: str, *args: Any) -> str: ...


def _parse_string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return []
        if isinstance(parsed, list):
            return [str(item) for item in parsed if str(item).strip()]
    return []


def _parse_channels(value: Any) -> list[dict[str, str]]:
    raw_items: Any = value
    if isinstance(value, str):
        try:
            raw_items = json.loads(value)
        except json.JSONDecodeError:
            raw_items = []
    if not isinstance(raw_items, list):
        return []
    channels: list[dict[str, str]] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        channel_id = str(item.get("id", "")).strip()
        channel_title = str(item.get("title", "")).strip()
        if channel_id:
            normalized = {
                str(key): str(val).strip()
                for key, val in item.items()
                if str(key).strip() and str(val).strip()
            }
            normalized["id"] = channel_id
            normalized["title"] = channel_title
            channels.append(normalized)
    return channels


class YouTubeConnectionRepository:
    def __init__(self, db: DatabaseProtocol) -> None:
        self._db = db

    async def list_accounts_for_user(self, user_id: str) -> list[YouTubeConnectedAccountRecord]:
        rows = await self._db.fetch(
            """
            SELECT id, user_id, profile_id, oauth_app_id, channel_id, channel_title,
                   encrypted_refresh_token, scopes, created_at, updated_at
            FROM youtube_connected_accounts
            WHERE user_id = $1::uuid
            ORDER BY updated_at DESC, created_at DESC
            """,
            user_id,
        )
        return [self._row_to_account(row) for row in rows]

    async def get_account_for_user_profile(
        self, user_id: str, profile_id: str
    ) -> YouTubeConnectedAccountRecord | None:
        row = await self._db.fetchrow(
            """
            SELECT id, user_id, profile_id, oauth_app_id, channel_id, channel_title,
                   encrypted_refresh_token, scopes, created_at, updated_at
            FROM youtube_connected_accounts
            WHERE user_id = $1::uuid AND profile_id = $2::uuid
            """,
            user_id,
            profile_id,
        )
        return self._row_to_account(row) if row else None

    async def upsert_connected_account(
        self,
        *,
        user_id: str,
        profile_id: str,
        oauth_app_id: str | None,
        channel_id: str,
        channel_title: str,
        encrypted_refresh_token: bytes,
        scopes: list[str],
    ) -> YouTubeConnectedAccountRecord | None:
        row = await self._db.fetchrow(
            """
            INSERT INTO youtube_connected_accounts (
                user_id,
                profile_id,
                oauth_app_id,
                channel_id,
                channel_title,
                encrypted_refresh_token,
                scopes,
                created_at,
                updated_at
            )
            VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5, $6, $7::jsonb, NOW(), NOW())
            ON CONFLICT (profile_id)
            DO UPDATE SET
                oauth_app_id = EXCLUDED.oauth_app_id,
                channel_id = EXCLUDED.channel_id,
                channel_title = EXCLUDED.channel_title,
                encrypted_refresh_token = EXCLUDED.encrypted_refresh_token,
                scopes = EXCLUDED.scopes,
                updated_at = NOW()
            RETURNING id, user_id, profile_id, oauth_app_id, channel_id, channel_title,
                      encrypted_refresh_token, scopes, created_at, updated_at
            """,
            user_id,
            profile_id,
            oauth_app_id,
            channel_id,
            channel_title,
            encrypted_refresh_token,
            json.dumps(scopes),
        )
        return self._row_to_account(row) if row else None

    async def delete_connected_account(self, user_id: str, profile_id: str) -> bool:
        result = await self._db.execute(
            """
            DELETE FROM youtube_connected_accounts
            WHERE user_id = $1::uuid AND profile_id = $2::uuid
            """,
            user_id,
            profile_id,
        )
        return result.upper() != "DELETE 0"

    async def list_recent_sessions_for_user(self, user_id: str) -> list[YouTubeConnectSessionRecord]:
        rows = await self._db.fetch(
            """
            SELECT DISTINCT ON (profile_id)
                id, user_id, profile_id, oauth_app_id, state_token, code_verifier, status,
                encrypted_refresh_token, scopes, channels, error_message,
                expires_at, created_at, updated_at
            FROM youtube_connect_sessions
            WHERE user_id = $1::uuid
              AND expires_at > NOW()
              AND status IN ('pending_browser', 'awaiting_channel_selection', 'error')
            ORDER BY profile_id, updated_at DESC, created_at DESC
            """,
            user_id,
        )
        return [self._row_to_session(row) for row in rows]

    async def create_session(
        self,
        *,
        user_id: str,
        profile_id: str,
        oauth_app_id: str,
        state_token: str,
        code_verifier: str | None,
        expires_at: datetime,
    ) -> YouTubeConnectSessionRecord | None:
        row = await self._db.fetchrow(
            """
            INSERT INTO youtube_connect_sessions (
                user_id,
                profile_id,
                oauth_app_id,
                state_token,
                code_verifier,
                status,
                scopes,
                channels,
                expires_at,
                created_at,
                updated_at
            )
            VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5, 'pending_browser', '[]'::jsonb, '[]'::jsonb, $6, NOW(), NOW())
            RETURNING id, user_id, profile_id, oauth_app_id, state_token, code_verifier, status,
                      encrypted_refresh_token, scopes, channels, error_message,
                      expires_at, created_at, updated_at
            """,
            user_id,
            profile_id,
            oauth_app_id,
            state_token,
            code_verifier,
            expires_at,
        )
        return self._row_to_session(row) if row else None

    async def get_session_by_state(self, state_token: str) -> YouTubeConnectSessionRecord | None:
        row = await self._db.fetchrow(
            """
            SELECT id, user_id, profile_id, oauth_app_id, state_token, code_verifier, status,
                   encrypted_refresh_token, scopes, channels, error_message,
                   expires_at, created_at, updated_at
            FROM youtube_connect_sessions
            WHERE state_token = $1
            """,
            state_token,
        )
        return self._row_to_session(row) if row else None

    async def get_session_for_user(
        self, session_id: str, user_id: str
    ) -> YouTubeConnectSessionRecord | None:
        row = await self._db.fetchrow(
            """
            SELECT id, user_id, profile_id, oauth_app_id, state_token, code_verifier, status,
                   encrypted_refresh_token, scopes, channels, error_message,
                   expires_at, created_at, updated_at
            FROM youtube_connect_sessions
            WHERE id = $1::uuid AND user_id = $2::uuid
            """,
            session_id,
            user_id,
        )
        return self._row_to_session(row) if row else None

    async def mark_profile_sessions_expired(self, user_id: str, profile_id: str) -> None:
        await self._db.execute(
            """
            UPDATE youtube_connect_sessions
            SET status = 'expired',
                updated_at = NOW()
            WHERE user_id = $1::uuid
              AND profile_id = $2::uuid
              AND status IN ('pending_browser', 'awaiting_channel_selection')
              AND expires_at > NOW()
            """,
            user_id,
            profile_id,
        )

    async def update_session(
        self,
        session_id: str,
        *,
        status: str | None = None,
        encrypted_refresh_token: bytes | None = None,
        scopes: list[str] | None = None,
        channels: list[dict[str, str]] | None = None,
        error_message: str | None = None,
    ) -> YouTubeConnectSessionRecord | None:
        row = await self._db.fetchrow(
            """
            UPDATE youtube_connect_sessions
            SET status = COALESCE($2, status),
                encrypted_refresh_token = COALESCE($3, encrypted_refresh_token),
                scopes = COALESCE($4::jsonb, scopes),
                channels = COALESCE($5::jsonb, channels),
                error_message = $6,
                code_verifier = COALESCE($7, code_verifier),
                updated_at = NOW()
            WHERE id = $1::uuid
            RETURNING id, user_id, profile_id, oauth_app_id, state_token, code_verifier, status,
                      encrypted_refresh_token, scopes, channels, error_message,
                      expires_at, created_at, updated_at
            """,
            session_id,
            status,
            encrypted_refresh_token,
            json.dumps(scopes) if scopes is not None else None,
            json.dumps(channels) if channels is not None else None,
            error_message,
            None,
        )
        return self._row_to_session(row) if row else None

    async def upsert_merge_upload_job(
        self,
        *,
        user_id: str,
        batch_id: str,
        profile_id: str,
        role: str,
        job_uid: str,
        file_path: str,
        title: str,
        description: str | None,
        tags: str | None,
        privacy_status: str,
        status: str,
        error_message: str | None,
    ) -> YouTubeUploadJobRecord | None:
        row = await self._db.fetchrow(
            """
            INSERT INTO youtube_upload_jobs (
                user_id,
                song_id,
                job_uid,
                batch_id,
                profile_id,
                role,
                file_path,
                title,
                description,
                tags,
                privacy_status,
                youtube_video_id,
                youtube_url,
                status,
                attempt_count,
                error_message,
                created_at,
                updated_at
            )
            VALUES (
                $1::uuid,
                NULL,
                $2,
                $3::uuid,
                $4::uuid,
                $5,
                $6,
                $7,
                $8,
                $9,
                $10,
                NULL,
                NULL,
                $11,
                0,
                $12,
                NOW(),
                NOW()
            )
            ON CONFLICT (job_uid)
            DO UPDATE SET
                batch_id = EXCLUDED.batch_id,
                profile_id = EXCLUDED.profile_id,
                role = EXCLUDED.role,
                file_path = EXCLUDED.file_path,
                title = EXCLUDED.title,
                description = EXCLUDED.description,
                tags = EXCLUDED.tags,
                privacy_status = EXCLUDED.privacy_status,
                updated_at = NOW(),
                status = CASE
                    WHEN youtube_upload_jobs.status IN ('failed', 'cancelled', 'blocked')
                         AND EXCLUDED.status = 'pending' THEN 'pending'
                    ELSE youtube_upload_jobs.status
                END,
                error_message = CASE
                    WHEN youtube_upload_jobs.status IN ('failed', 'cancelled', 'blocked')
                         AND EXCLUDED.status = 'pending' THEN NULL
                    ELSE COALESCE(youtube_upload_jobs.error_message, EXCLUDED.error_message)
                END
            RETURNING id, user_id, song_id, job_uid, batch_id, profile_id, role, file_path, title,
                      description, tags, privacy_status, youtube_video_id, youtube_url, status,
                      attempt_count, error_message, created_at, updated_at
            """,
            user_id,
            job_uid,
            batch_id,
            profile_id,
            role,
            file_path,
            title,
            description,
            tags,
            privacy_status,
            status,
            error_message,
        )
        return self._row_to_upload_job(row) if row else None

    async def claim_upload_jobs_for_run(
        self,
        user_id: str,
        *,
        batch_id: str | None = None,
        statuses: list[str],
        limit: int,
    ) -> list[YouTubeUploadJobRecord]:
        rows = await self._db.fetch(
            """
            WITH target AS (
                SELECT id
                FROM youtube_upload_jobs
                WHERE user_id = $1::uuid
                  AND ($2::uuid IS NULL OR batch_id = $2::uuid)
                  AND status = ANY($3::text[])
                ORDER BY updated_at ASC, created_at ASC
                LIMIT $4
                FOR UPDATE SKIP LOCKED
            )
            UPDATE youtube_upload_jobs AS job
            SET status = 'running',
                error_message = NULL,
                attempt_count = GREATEST(0, COALESCE(job.attempt_count, 0)) + 1,
                updated_at = NOW()
            FROM target
            WHERE job.id = target.id
            RETURNING job.id, job.user_id, job.song_id, job.job_uid, job.batch_id,
                      job.profile_id, job.role, job.file_path, job.title, job.description,
                      job.tags, job.privacy_status, job.youtube_video_id, job.youtube_url,
                      job.status, job.attempt_count, job.error_message,
                      job.created_at, job.updated_at
            """,
            user_id,
            batch_id,
            statuses,
            limit,
        )
        return [self._row_to_upload_job(row) for row in rows]

    async def update_upload_job_status(
        self,
        job_id: str,
        user_id: str,
        *,
        status: str,
        error_message: str | None = None,
        youtube_video_id: str | None = None,
        youtube_url: str | None = None,
    ) -> None:
        await self._db.execute(
            """
            UPDATE youtube_upload_jobs
            SET status = $3,
                error_message = $4,
                youtube_video_id = COALESCE($5, youtube_video_id),
                youtube_url = COALESCE($6, youtube_url),
                updated_at = NOW()
            WHERE id = $1::uuid
              AND user_id = $2::uuid
            """,
            job_id,
            user_id,
            status,
            error_message,
            youtube_video_id,
            youtube_url,
        )

    @staticmethod
    def _row_to_account(row: dict[str, Any]) -> YouTubeConnectedAccountRecord:
        return YouTubeConnectedAccountRecord(
            id=str(row["id"]),
            user_id=str(row["user_id"]),
            profile_id=str(row["profile_id"]),
            oauth_app_id=str(row["oauth_app_id"]) if row.get("oauth_app_id") else None,
            channel_id=str(row["channel_id"] or ""),
            channel_title=str(row["channel_title"] or ""),
            encrypted_refresh_token=bytes(row["encrypted_refresh_token"] or b""),
            scopes=_parse_string_list(row.get("scopes")),
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
        )

    @staticmethod
    def _row_to_session(row: dict[str, Any]) -> YouTubeConnectSessionRecord:
        return YouTubeConnectSessionRecord(
            id=str(row["id"]),
            user_id=str(row["user_id"]),
            profile_id=str(row["profile_id"]),
            oauth_app_id=str(row["oauth_app_id"]),
            state_token=str(row["state_token"] or ""),
            code_verifier=str(row["code_verifier"] or "").strip() or None,
            status=str(row["status"] or "pending_browser"),
            encrypted_refresh_token=bytes(row["encrypted_refresh_token"]) if row.get("encrypted_refresh_token") else None,
            scopes=_parse_string_list(row.get("scopes")),
            channels=_parse_channels(row.get("channels")),
            error_message=str(row["error_message"]) if row.get("error_message") else None,
            expires_at=row["expires_at"],
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
        )

    @staticmethod
    def _row_to_upload_job(row: dict[str, Any]) -> YouTubeUploadJobRecord:
        return YouTubeUploadJobRecord(
            id=str(row["id"]),
            user_id=str(row["user_id"]),
            song_id=str(row["song_id"]) if row.get("song_id") else None,
            job_uid=str(row["job_uid"]) if row.get("job_uid") else None,
            batch_id=str(row["batch_id"]) if row.get("batch_id") else None,
            profile_id=str(row["profile_id"]) if row.get("profile_id") else None,
            role=str(row["role"]) if row.get("role") else None,
            file_path=str(row["file_path"]) if row.get("file_path") else None,
            title=str(row["title"] or ""),
            description=str(row["description"]) if row.get("description") else None,
            tags=str(row["tags"]) if row.get("tags") else None,
            privacy_status=str(row["privacy_status"] or "private"),
            youtube_video_id=str(row["youtube_video_id"]) if row.get("youtube_video_id") else None,
            youtube_url=str(row["youtube_url"]) if row.get("youtube_url") else None,
            status=str(row["status"] or "pending"),
            attempt_count=int(row["attempt_count"] or 0),
            error_message=str(row["error_message"]) if row.get("error_message") else None,
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
        )
