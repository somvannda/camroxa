"""Backend-mediated YouTube OAuth connection flow for desktop clients."""

from __future__ import annotations

import asyncio
import os
import base64
import hashlib
import json
import logging
import mimetypes
import shlex
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from secrets import token_urlsafe
from typing import Any
from urllib.parse import urlparse
from pathlib import Path
from uuid import UUID

from platform_api.exceptions import NotFoundError, ValidationError
from platform_api.repositories.youtube_connection_repo import (
    YouTubeConnectedAccountRecord,
    YouTubeConnectSessionRecord,
    YouTubeConnectionRepository,
    YouTubeUploadJobRecord,
)
from platform_api.repositories.youtube_oauth_app_repo import YouTubeOAuthAppRepository
from platform_api.services.key_encryption import KeyEncryption
from platform_api.services.youtube_upload_runtime import (
    VideoProcessingStatus,
    get_video_processing_status,
    upload_video,
)

YOUTUBE_UPLOAD_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]

LOCAL_OAUTH_CALLBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}
logger = logging.getLogger(__name__)


def _generate_pkce_code_verifier() -> str:
    verifier = token_urlsafe(64)
    return verifier[:128]


def _build_pkce_code_challenge(code_verifier: str) -> str:
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value or "{}")
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def _is_local_oauth_callback(callback_url: str) -> bool:
    parsed = urlparse(str(callback_url or "").strip())
    return parsed.scheme.lower() == "http" and str(parsed.hostname or "").lower() in LOCAL_OAUTH_CALLBACK_HOSTS


def _validate_oauth_callback_url(callback_url: str) -> None:
    parsed = urlparse(str(callback_url or "").strip())
    scheme = parsed.scheme.lower()
    hostname = str(parsed.hostname or "").lower()
    if scheme == "https":
        return
    if scheme == "http" and hostname in LOCAL_OAUTH_CALLBACK_HOSTS:
        return
    raise ValidationError(
        "YouTube OAuth callback URLs must use HTTPS, except for localhost loopback during desktop development."
    )


@contextmanager
def _oauth_transport_context(callback_url: str):
    _validate_oauth_callback_url(callback_url)
    previous = os.environ.get("OAUTHLIB_INSECURE_TRANSPORT")
    enable_insecure_transport = _is_local_oauth_callback(callback_url)
    if enable_insecure_transport:
        os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
    try:
        yield
    finally:
        if not enable_insecure_transport:
            return
        if previous is None:
            os.environ.pop("OAUTHLIB_INSECURE_TRANSPORT", None)
        else:
            os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = previous


@dataclass(frozen=True, slots=True)
class YouTubeConnectionState:
    profile_id: str
    profile_name: str
    status: str
    channel_id: str | None = None
    channel_title: str | None = None
    session_id: str | None = None
    channels: list[dict[str, str]] | None = None
    message: str | None = None


@dataclass(frozen=True, slots=True)
class YouTubeConnectionStartResult:
    session_id: str
    auth_url: str
    status: str


@dataclass(frozen=True, slots=True)
class YouTubeCallbackResult:
    title: str
    message: str
    status: str


@dataclass(frozen=True, slots=True)
class YouTubeMergeUploadEnqueueResult:
    job_uid: str
    status: str
    profile_id: str
    batch_id: str
    role: str
    file_path: str
    message: str
    blocked_reason: str | None = None


class YouTubeConnectionService:
    def __init__(
        self,
        *,
        db: Any,
        oauth_app_repo: YouTubeOAuthAppRepository,
        connection_repo: YouTubeConnectionRepository,
        encryption: KeyEncryption | None,
        settings_service: Any | None = None,
    ) -> None:
        self._db = db
        self._oauth_app_repo = oauth_app_repo
        self._connection_repo = connection_repo
        self._encryption = encryption
        self._settings_service = settings_service

    async def list_connections(self, user_id: UUID) -> list[YouTubeConnectionState]:
        profiles = await self._db.fetch(
            """
            SELECT id, name
            FROM channel_profiles
            WHERE user_id = $1
            ORDER BY lower(name) ASC
            """,
            user_id,
        )
        accounts = {
            account.profile_id: account
            for account in await self._connection_repo.list_accounts_for_user(str(user_id))
        }
        sessions = {
            session.profile_id: session
            for session in await self._connection_repo.list_recent_sessions_for_user(str(user_id))
        }

        states: list[YouTubeConnectionState] = []
        for row in profiles:
            profile_id = str(row["id"])
            profile_name = str(row["name"] or "Profile")
            session = sessions.get(profile_id)
            account = accounts.get(profile_id)
            states.append(self._build_connection_state(profile_id, profile_name, account, session))
        return states

    async def start_connection(
        self,
        *,
        user_id: UUID,
        profile_id: UUID,
        callback_url: str,
    ) -> YouTubeConnectionStartResult:
        await self._ensure_profile_owned(user_id, profile_id)
        oauth_app = await self._oauth_app_repo.get_default()
        if oauth_app is None:
            raise ValidationError("No default YouTube OAuth app is configured yet.")

        await self._connection_repo.mark_profile_sessions_expired(str(user_id), str(profile_id))

        code_verifier = _generate_pkce_code_verifier()
        code_challenge = _build_pkce_code_challenge(code_verifier)
        with _oauth_transport_context(callback_url):
            flow = self._build_google_flow(
                client_id=oauth_app.client_id,
                client_secret=self._decrypt_client_secret(oauth_app.encrypted_client_secret),
                callback_url=callback_url,
            )
            auth_url, state_token = flow.authorization_url(
                access_type="offline",
                include_granted_scopes="true",
                prompt="consent",
                code_challenge=code_challenge,
                code_challenge_method="S256",
            )
        session = await self._connection_repo.create_session(
            user_id=str(user_id),
            profile_id=str(profile_id),
            oauth_app_id=oauth_app.id,
            state_token=state_token,
            code_verifier=code_verifier,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
        )
        if session is None:
            raise RuntimeError("Unable to create YouTube connection session.")
        return YouTubeConnectionStartResult(
            session_id=session.id,
            auth_url=auth_url,
            status=session.status,
        )

    async def finalize_callback(
        self,
        *,
        callback_url: str,
        callback_request_url: str,
        state_token: str,
        error_message: str | None,
    ) -> YouTubeCallbackResult:
        session = await self._connection_repo.get_session_by_state(state_token)
        if session is None:
            return YouTubeCallbackResult(
                title="Connection expired",
                message="This YouTube connection request is no longer valid. Return to CAMXORA and try again.",
                status="error",
            )
        if session.expires_at <= datetime.now(timezone.utc):
            await self._connection_repo.update_session(session.id, status="expired", error_message="Connection request expired.")
            return YouTubeCallbackResult(
                title="Connection expired",
                message="This YouTube connection request expired. Return to CAMXORA and start the connection again.",
                status="expired",
            )
        if error_message:
            await self._connection_repo.update_session(session.id, status="error", error_message=error_message)
            return YouTubeCallbackResult(
                title="Connection failed",
                message="Google sign-in did not complete. Return to CAMXORA and try again.",
                status="error",
            )

        oauth_app = await self._oauth_app_repo.get_by_id(session.oauth_app_id)
        if oauth_app is None:
            await self._connection_repo.update_session(session.id, status="error", error_message="OAuth app is missing.")
            return YouTubeCallbackResult(
                title="Connection failed",
                message="The configured YouTube OAuth app is missing. Contact the administrator.",
                status="error",
            )

        try:
            with _oauth_transport_context(callback_url):
                flow = self._build_google_flow(
                    client_id=oauth_app.client_id,
                    client_secret=self._decrypt_client_secret(oauth_app.encrypted_client_secret),
                    callback_url=callback_url,
                )
                if not session.code_verifier:
                    raise RuntimeError("Connection session is missing its code verifier. Start again.")
                flow.code_verifier = session.code_verifier
                flow.fetch_token(authorization_response=callback_request_url)
                credentials = flow.credentials
            refresh_token = str(getattr(credentials, "refresh_token", "") or "").strip()
            if not refresh_token:
                raise RuntimeError("Google did not return a refresh token.")
            channels = self._fetch_channels(credentials)
            if not channels:
                raise RuntimeError("No YouTube channels were returned for this account.")

            encrypted_refresh_token = self._encrypt_refresh_token(refresh_token)
            scopes = [str(scope) for scope in getattr(credentials, "scopes", []) or YOUTUBE_UPLOAD_SCOPES if str(scope).strip()]

            if len(channels) == 1:
                await self._sync_profile_from_channel(
                    user_id=session.user_id,
                    profile_id=session.profile_id,
                    channel=channels[0],
                )
                await self._connection_repo.upsert_connected_account(
                    user_id=session.user_id,
                    profile_id=session.profile_id,
                    oauth_app_id=session.oauth_app_id,
                    channel_id=channels[0]["id"],
                    channel_title=channels[0]["title"],
                    encrypted_refresh_token=encrypted_refresh_token,
                    scopes=scopes,
                )
                await self._connection_repo.update_session(session.id, status="connected", scopes=scopes, channels=channels, error_message=None)
                return YouTubeCallbackResult(
                    title="YouTube connected",
                    message=f'Connected channel "{channels[0]["title"]}". Return to CAMXORA.',
                    status="connected",
                )

            await self._connection_repo.update_session(
                session.id,
                status="awaiting_channel_selection",
                encrypted_refresh_token=encrypted_refresh_token,
                scopes=scopes,
                channels=channels,
                error_message=None,
            )
            return YouTubeCallbackResult(
                title="Select a channel in CAMXORA",
                message="Google returned multiple channels. Return to CAMXORA and choose which channel to connect.",
                status="awaiting_channel_selection",
            )
        except Exception as exc:
            await self._connection_repo.update_session(session.id, status="error", error_message=str(exc))
            return YouTubeCallbackResult(
                title="Connection failed",
                message="YouTube sign-in could not be completed. Return to CAMXORA and try again.",
                status="error",
            )

    async def select_channel(
        self, *, user_id: UUID, session_id: str, channel_id: str
    ) -> YouTubeConnectionState:
        session = await self._connection_repo.get_session_for_user(session_id, str(user_id))
        if session is None:
            raise NotFoundError("YouTube connection session not found.")
        if session.status != "awaiting_channel_selection":
            raise ValidationError("This session is not waiting for channel selection.")
        selected = next((channel for channel in session.channels if channel["id"] == channel_id), None)
        if selected is None:
            raise ValidationError("Selected channel is invalid.")
        if not session.encrypted_refresh_token:
            raise ValidationError("Connection session is missing its refresh token. Start again.")

        await self._sync_profile_from_channel(
            user_id=session.user_id,
            profile_id=session.profile_id,
            channel=selected,
        )
        await self._connection_repo.upsert_connected_account(
            user_id=session.user_id,
            profile_id=session.profile_id,
            oauth_app_id=session.oauth_app_id,
            channel_id=selected["id"],
            channel_title=selected["title"],
            encrypted_refresh_token=session.encrypted_refresh_token,
            scopes=session.scopes,
        )
        updated = await self._connection_repo.update_session(
            session.id,
            status="connected",
            channels=session.channels,
            scopes=session.scopes,
            error_message=None,
        )
        profile_name = await self._get_profile_name(UUID(session.profile_id))
        return self._build_connection_state(
            session.profile_id,
            profile_name,
            await self._connection_repo.get_account_for_user_profile(session.user_id, session.profile_id),
            updated,
        )

    async def disconnect(self, *, user_id: UUID, profile_id: UUID) -> None:
        await self._ensure_profile_owned(user_id, profile_id)
        await self._connection_repo.mark_profile_sessions_expired(str(user_id), str(profile_id))
        await self._connection_repo.delete_connected_account(str(user_id), str(profile_id))

    async def resync_connected_profile(
        self, *, user_id: UUID, profile_id: UUID
    ) -> YouTubeConnectionState:
        await self._ensure_profile_owned(user_id, profile_id)
        account = await self._connection_repo.get_account_for_user_profile(
            str(user_id), str(profile_id)
        )
        if account is None:
            raise ValidationError("No connected YouTube channel was found for this profile.")

        channel = await self._fetch_connected_channel(account)
        await self._sync_profile_from_channel(
            user_id=str(user_id),
            profile_id=str(profile_id),
            channel=channel,
        )
        profile_name = await self._get_profile_name(profile_id)
        return self._build_connection_state(
            str(profile_id),
            profile_name,
            account,
            None,
        )

    async def list_connected_playlists(
        self, *, user_id: UUID, profile_id: UUID
    ) -> list[dict[str, str]]:
        await self._ensure_profile_owned(user_id, profile_id)
        account = await self._connection_repo.get_account_for_user_profile(
            str(user_id), str(profile_id)
        )
        if account is None:
            return []
        credentials = await self._build_refreshed_credentials(account)
        return self._fetch_playlists(credentials)

    async def enqueue_upload_for_merge(
        self,
        *,
        user_id: UUID,
        batch_id: UUID,
        profile_id: UUID,
        role: str,
        merged_mp4_path: str,
    ) -> YouTubeMergeUploadEnqueueResult:
        normalized_role = self._normalize_upload_role(role)
        file_path = str(merged_mp4_path or "").strip()
        if not file_path:
            raise ValidationError("Merged output path is required.")
        if not file_path.lower().endswith(".mp4"):
            raise ValidationError("Merged output path must point to an MP4 file.")

        batch = await self._ensure_batch_profile_lane(
            user_id=user_id,
            batch_id=batch_id,
            profile_id=profile_id,
            role=normalized_role,
        )
        account = await self._connection_repo.get_account_for_user_profile(
            str(user_id), str(profile_id)
        )
        status = "pending"
        blocked_reason: str | None = None
        if account is None or not bytes(account.encrypted_refresh_token or b""):
            status = "blocked"
            blocked_reason = "YouTube is not connected for this profile yet."

        profile_row = await self._db.fetchrow(
            """
            SELECT name, youtube_config
            FROM channel_profiles
            WHERE id = $1
            """,
            profile_id,
        )
        profile_name = (
            str(profile_row["name"] or "Profile")
            if profile_row is not None
            else "Profile"
        )
        youtube_config = _as_dict(profile_row.get("youtube_config") if profile_row else {})
        title = self._build_upload_title(
            batch_id=str(batch_id),
            profile_name=profile_name,
            role=normalized_role,
            file_path=file_path,
            config=youtube_config,
        )
        description = str(youtube_config.get("description") or "").strip() or None
        tags = self._serialize_upload_tags(youtube_config.get("keywords"))
        privacy_status = self._normalize_privacy_status(
            youtube_config.get("visibility") or youtube_config.get("privacyStatus")
        )
        job_uid = self._build_merge_job_uid(
            batch_id=str(batch_id),
            profile_id=str(profile_id),
            role=normalized_role,
        )
        job = await self._connection_repo.upsert_merge_upload_job(
            user_id=str(user_id),
            batch_id=str(batch_id),
            profile_id=str(profile_id),
            role=normalized_role,
            job_uid=job_uid,
            file_path=file_path,
            title=title,
            description=description,
            tags=tags,
            privacy_status=privacy_status,
            status=status,
            error_message=blocked_reason,
        )
        if job is None:
            raise RuntimeError("Unable to enqueue the merged YouTube upload job.")
        return self._to_merge_upload_result(job, blocked_reason)

    async def build_refreshed_credentials_for_profile(
        self, *, user_id: UUID, profile_id: UUID
    ) -> Any:
        await self._ensure_profile_owned(user_id, profile_id)
        account = await self._connection_repo.get_account_for_user_profile(
            str(user_id), str(profile_id)
        )
        if account is None or not bytes(account.encrypted_refresh_token or b""):
            raise ValidationError("YouTube is not connected for this profile yet.")
        return await self._build_refreshed_credentials(account)

    async def run_pending_upload_jobs(
        self,
        user_id: str,
        *,
        batch_id: str | None = None,
        limit: int = 4,
    ) -> int:
        if limit <= 0:
            return 0

        user_uuid = UUID(user_id)
        settings = await self._get_runtime_settings(user_uuid)
        max_workers = max(1, min(5, int(settings.get("perfYouTubeWorkers", 1) or 1)))
        chunk_size_mb = max(
            8, min(512, int(settings.get("youtubeUploadChunkSizeMb", 256) or 256))
        )
        claimed_jobs = await self._connection_repo.claim_upload_jobs_for_run(
            str(user_uuid),
            batch_id=batch_id,
            statuses=["pending"],
            limit=min(100, max(1, limit)),
        )
        if not claimed_jobs:
            return 0

        semaphore = asyncio.Semaphore(max_workers)
        results = await asyncio.gather(
            *[
                self._run_one_upload_job(
                    user_id=user_uuid,
                    job=job,
                    chunk_size_mb=chunk_size_mb,
                    semaphore=semaphore,
                )
                for job in claimed_jobs
            ],
            return_exceptions=True,
        )
        return sum(1 for result in results if result is True)

    async def _run_one_upload_job(
        self,
        *,
        user_id: UUID,
        job: YouTubeUploadJobRecord,
        chunk_size_mb: int,
        semaphore: asyncio.Semaphore,
    ) -> bool:
        async with semaphore:
            try:
                payload = await self._resolve_upload_job_payload(user_id=user_id, job=job)
                if not payload["file_ready"]:
                    await self._connection_repo.update_upload_job_status(
                        job.id,
                        str(user_id),
                        status="pending",
                        error_message=payload["file_reason"],
                    )
                    return False

                credentials = await self.build_refreshed_credentials_for_profile(
                    user_id=user_id,
                    profile_id=UUID(payload["profile_id"]),
                )
                result = await asyncio.to_thread(
                    upload_video,
                    credentials=credentials,
                    file_path=payload["file_path"],
                    title=payload["title"],
                    description=payload["description"],
                    tags=payload["tags"],
                    category_id=payload["category_id"],
                    made_for_kids=payload["made_for_kids"],
                    contains_synthetic_media=payload["contains_synthetic_media"],
                    privacy_status=payload["privacy_status"],
                    publish_at=payload["publish_at"],
                    thumbnail_path=payload["thumbnail_path"],
                    playlist_id=payload["playlist_id"],
                    chunk_size_mb=chunk_size_mb,
                )
                processing = await asyncio.to_thread(
                    get_video_processing_status,
                    credentials=credentials,
                    video_id=result.video_id,
                )
                failed, failure_message = self._is_processing_failed(processing)
                if failed:
                    await self._connection_repo.update_upload_job_status(
                        job.id,
                        str(user_id),
                        status="failed",
                        error_message=failure_message[:500],
                        youtube_video_id=result.video_id,
                        youtube_url=result.url,
                    )
                    return False

                warnings = self._build_upload_warning(
                    thumbnail_error=result.thumbnail_error,
                    playlist_error=result.playlist_error,
                    processing=processing,
                )
                await self._connection_repo.update_upload_job_status(
                    job.id,
                    str(user_id),
                    status="success",
                    error_message=warnings[:500] if warnings else None,
                    youtube_video_id=result.video_id,
                    youtube_url=result.url,
                )
                return True
            except Exception as exc:
                status, message = self._classify_upload_runtime_exception(exc)
                await self._connection_repo.update_upload_job_status(
                    job.id,
                    str(user_id),
                    status=status,
                    error_message=message[:500],
                )
                logger.warning(
                    "YouTube upload job failed: job_uid=%s status=%s error=%s",
                    job.job_uid,
                    status,
                    message[:200],
                )
                return False

    async def _get_runtime_settings(self, user_id: UUID) -> dict[str, Any]:
        if self._settings_service is None:
            return {}
        try:
            return await self._settings_service.get_merged_settings(
                user_id=user_id,
                include_sensitive=False,
            )
        except Exception:
            return {}

    async def _resolve_upload_job_payload(
        self, *, user_id: UUID, job: YouTubeUploadJobRecord
    ) -> dict[str, Any]:
        profile_id = str(job.profile_id or "").strip()
        batch_id = str(job.batch_id or "").strip()
        role = str(job.role or "").strip().upper() or "OK"
        if not profile_id:
            raise ValidationError("Upload job is missing its profile id.")
        if not batch_id:
            raise ValidationError("Upload job is missing its batch id.")
        file_path = str(job.file_path or "").strip()
        if not file_path:
            raise ValidationError("Upload job is missing its merged MP4 path.")

        profile_row = await self._db.fetchrow(
            """
            SELECT name, youtube_config
            FROM channel_profiles
            WHERE id = $1::uuid AND user_id = $2::uuid
            """,
            profile_id,
            user_id,
        )
        if profile_row is None:
            raise NotFoundError("Profile not found for this YouTube upload job.")

        batch_row = await self._db.fetchrow(
            """
            SELECT id, created_at, planned_from_date, planned_to_date, ok_run_dir, alt_run_dir
            FROM batches
            WHERE id = $1::uuid AND user_id = $2::uuid
            """,
            batch_id,
            user_id,
        )
        if batch_row is None:
            raise NotFoundError("Batch not found for this YouTube upload job.")

        config = _as_dict(profile_row.get("youtube_config"))
        visibility = str(config.get("visibility") or job.privacy_status or "private").strip()
        publish_at = self._compute_publish_at(
            visibility=visibility,
            batch_row=batch_row,
            raw_publish_time=str(config.get("publish_at") or "").strip(),
        )
        file_ready, file_reason = self._is_mp4_ready_for_upload(file_path)

        return {
            "profile_id": profile_id,
            "batch_id": batch_id,
            "role": role,
            "file_path": file_path,
            "file_ready": file_ready,
            "file_reason": file_reason,
            "title": str(job.title or "").strip()
            or self._build_upload_title(
                batch_id=batch_id,
                profile_name=str(profile_row.get("name") or "Profile"),
                role=role,
                file_path=file_path,
                config=config,
            ),
            "description": str(job.description or config.get("description") or "").strip(),
            "tags": self._parse_upload_tags(job.tags),
            "privacy_status": self._resolve_privacy_status(visibility),
            "publish_at": publish_at,
            "category_id": str(config.get("category") or "").strip(),
            "made_for_kids": bool(config.get("made_for_kids", False)),
            "contains_synthetic_media": bool(config.get("ai_use", False)),
            "playlist_id": str(config.get("playlist") or "").strip(),
            "thumbnail_path": await self._resolve_thumbnail_path(
                user_id=user_id,
                batch_id=batch_id,
                profile_id=profile_id,
                role=role,
                fallback_run_dir=str(
                    batch_row.get("ok_run_dir")
                    if role == "OK"
                    else (batch_row.get("alt_run_dir") or batch_row.get("ok_run_dir"))
                    or ""
                ).strip(),
            ),
        }

    async def _resolve_thumbnail_path(
        self,
        *,
        user_id: UUID,
        batch_id: str,
        profile_id: str,
        role: str,
        fallback_run_dir: str,
    ) -> str:
        asset_row = await self._db.fetchrow(
            """
            SELECT thumbnail_16x9_path, run_dir
            FROM batch_channel_assets
            WHERE user_id = $1::uuid
              AND batch_id = $2::uuid
              AND profile_id = $3::uuid
              AND role = $4
            """,
            user_id,
            batch_id,
            profile_id,
            role,
        )
        direct_path = str(
            (asset_row.get("thumbnail_16x9_path") if asset_row is not None else "") or ""
        ).strip()
        if direct_path and Path(direct_path).exists():
            return direct_path

        run_dir = str((asset_row.get("run_dir") if asset_row is not None else "") or "").strip()
        run_dir = run_dir or fallback_run_dir
        if not run_dir:
            return ""

        candidates: list[Path] = []
        base = Path(run_dir)
        for stem in ("thumbnail-16x9", "thumbnail_16x9", "thumbnail"):
            for extension in (".png", ".jpg", ".jpeg", ".webp"):
                candidates.append(base / f"{stem}{extension}")
        for candidate in candidates:
            if candidate.exists() and candidate.is_file():
                return str(candidate)
        return ""

    def _compute_publish_at(
        self,
        *,
        visibility: str,
        batch_row: Any,
        raw_publish_time: str,
    ) -> str:
        if str(visibility or "").strip().lower() != "scheduled":
            return ""

        hour: int | None = None
        minute: int | None = None
        raw = str(raw_publish_time or "").strip()
        if raw:
            hhmm = raw.split("T")[-1][:5] if "T" in raw else raw
            match = hhmm.split(":")
            if len(match) >= 2:
                try:
                    hour = max(0, min(23, int(match[0])))
                    minute = max(0, min(59, int(match[1])))
                except Exception:
                    hour = None
                    minute = None
        if hour is None or minute is None:
            raise ValidationError(
                "Scheduled uploads require a publish time in Settings -> Publication."
            )

        batch_date = batch_row.get("planned_from_date") or batch_row.get("planned_to_date")
        if not isinstance(batch_date, date):
            created_at = batch_row.get("created_at")
            if isinstance(created_at, datetime):
                batch_date = created_at.date()
        if not isinstance(batch_date, date):
            raise ValidationError("Scheduled uploads require a batch date.")

        local_tz = datetime.now().astimezone().tzinfo or timezone.utc
        publish_dt = datetime.combine(batch_date, time(hour, minute), tzinfo=local_tz)
        return publish_dt.isoformat(timespec="seconds")

    @staticmethod
    def _resolve_privacy_status(visibility: str) -> str:
        normalized = str(visibility or "").strip().lower()
        if normalized == "scheduled":
            return "private"
        if normalized in {"private", "public", "unlisted"}:
            return normalized
        return "private"

    @staticmethod
    def _parse_upload_tags(value: str | None) -> list[str]:
        raw = str(value or "").strip()
        if not raw:
            return []
        try:
            return [token.strip() for token in shlex.split(raw) if token.strip()]
        except Exception:
            return [token.strip() for token in raw.split(",") if token.strip()]

    @staticmethod
    def _is_mp4_ready_for_upload(file_path: str) -> tuple[bool, str]:
        target = Path(str(file_path or "").strip()).expanduser()
        if not str(target).strip():
            return False, "Merged output path is missing."
        if not target.exists() or not target.is_file():
            return False, "Merged MP4 file is missing."
        try:
            first = target.stat()
        except Exception:
            return False, "Merged MP4 file is unreadable."
        if int(first.st_size or 0) < 200_000:
            return False, "Merged MP4 file is too small or still incomplete."
        try:
            with target.open("rb") as handle:
                handle.read(1)
        except Exception:
            return False, "Merged MP4 file is still locked by another process."
        return True, ""

    @staticmethod
    def _build_upload_warning(
        *,
        thumbnail_error: str,
        playlist_error: str,
        processing: VideoProcessingStatus,
    ) -> str:
        parts: list[str] = []
        thumb = str(thumbnail_error or "").strip()
        if thumb:
            parts.append(f"Thumbnail: {thumb}")
        playlist = str(playlist_error or "").strip()
        if playlist:
            parts.append(f"Playlist: {playlist}")

        processing_status = str(processing.processing_status or "").strip().lower()
        upload_status = str(processing.upload_status or "").strip().lower()
        if processing_status and processing_status not in {"succeeded", "processed"}:
            label = upload_status or "uploaded"
            parts.append(
                f"YouTube processing status: {label} / {processing_status}"
            )
        return " · ".join(parts)

    @staticmethod
    def _is_processing_failed(processing: VideoProcessingStatus) -> tuple[bool, str]:
        processing_status = str(processing.processing_status or "").strip().lower()
        upload_status = str(processing.upload_status or "").strip().lower()
        if processing_status == "failed" or upload_status == "rejected":
            details = str(processing.failure_reason or processing.rejection_reason or "").strip()
            message = (
                f"YouTube processing failed: upload={upload_status or 'unknown'} "
                f"processing={processing_status or 'unknown'}"
            )
            if details:
                message = f"{message} ({details})"
            return True, message
        return False, ""

    @staticmethod
    def _classify_upload_runtime_exception(exc: Exception) -> tuple[str, str]:
        message = str(exc).strip() or exc.__class__.__name__
        lower = message.lower()
        if "not connected" in lower or "refresh token" in lower:
            return "blocked", message
        if "missing mp4" in lower or "still locked" in lower or "too small" in lower:
            return "pending", message
        return "failed", message

    def _build_connection_state(
        self,
        profile_id: str,
        profile_name: str,
        account: YouTubeConnectedAccountRecord | None,
        session: YouTubeConnectSessionRecord | None,
    ) -> YouTubeConnectionState:
        if session and session.status in {"pending_browser", "awaiting_channel_selection"}:
            message = None
            if session.status == "pending_browser":
                message = "Continue the Google sign-in flow in your browser."
            elif session.status == "awaiting_channel_selection":
                message = "Select which returned YouTube channel to attach to this profile."
            return YouTubeConnectionState(
                profile_id=profile_id,
                profile_name=profile_name,
                status=session.status,
                channel_id=account.channel_id if account else None,
                channel_title=account.channel_title if account else None,
                session_id=session.id,
                channels=session.channels if session.status == "awaiting_channel_selection" else None,
                message=message,
            )
        if account:
            message = "Channel connected."
            if session and session.status == "error" and session.error_message:
                message = f"Channel connected. Last reconnect attempt failed: {session.error_message}"
            return YouTubeConnectionState(
                profile_id=profile_id,
                profile_name=profile_name,
                status="connected",
                channel_id=account.channel_id,
                channel_title=account.channel_title,
                message=message,
            )
        if session and session.status == "error":
            return YouTubeConnectionState(
                profile_id=profile_id,
                profile_name=profile_name,
                status="error",
                session_id=session.id,
                message=session.error_message or "The last YouTube connection attempt failed.",
            )
        return YouTubeConnectionState(
            profile_id=profile_id,
            profile_name=profile_name,
            status="not_connected",
            message="No YouTube channel is connected yet.",
        )

    async def _ensure_batch_profile_lane(
        self,
        *,
        user_id: UUID,
        batch_id: UUID,
        profile_id: UUID,
        role: str,
    ) -> dict[str, Any]:
        await self._ensure_profile_owned(user_id, profile_id)
        batch = await self._db.fetchrow(
            """
            SELECT id, ok_profile_id, alt_profile_id
            FROM batches
            WHERE id = $1 AND user_id = $2
            """,
            batch_id,
            user_id,
        )
        if batch is None:
            raise NotFoundError("Batch not found.")
        expected_profile_id = (
            str(batch.get("ok_profile_id") or "").strip()
            if role == "OK"
            else str(batch.get("alt_profile_id") or "").strip()
        )
        if expected_profile_id != str(profile_id):
            raise ValidationError(
                "The selected profile does not match this batch lane."
            )
        return dict(batch)

    async def _ensure_profile_owned(self, user_id: UUID, profile_id: UUID) -> None:
        row = await self._db.fetchrow(
            """
            SELECT id
            FROM channel_profiles
            WHERE id = $1 AND user_id = $2
            """,
            profile_id,
            user_id,
        )
        if row is None:
            raise NotFoundError("Profile not found.")

    async def _get_profile_name(self, profile_id: UUID) -> str:
        row = await self._db.fetchrow(
            "SELECT name FROM channel_profiles WHERE id = $1",
            profile_id,
        )
        return str(row["name"] or "Profile") if row else "Profile"

    @staticmethod
    def _normalize_upload_role(role: str) -> str:
        normalized = str(role or "").strip().lower()
        if normalized in {"ok", "primary"}:
            return "OK"
        if normalized in {"alt", "secondary"}:
            return "ALT"
        raise ValidationError("Role must be one of: ok, alt, primary, secondary.")

    @staticmethod
    def _normalize_privacy_status(value: Any) -> str:
        normalized = str(value or "").strip().lower()
        if normalized in {"public", "private", "unlisted"}:
            return normalized
        return "private"

    @staticmethod
    def _serialize_upload_tags(value: Any) -> str | None:
        if isinstance(value, list):
            tags = [str(item).strip() for item in value if str(item).strip()]
            return ",".join(tags) if tags else None
        raw = str(value or "").strip()
        return raw or None

    @staticmethod
    def _build_merge_job_uid(*, batch_id: str, profile_id: str, role: str) -> str:
        safe = "".join(
            char if char.isalnum() or char in {"-", "_", "."} else "-"
            for char in f"{batch_id}-{profile_id}-{role}"
        ).strip("-")
        return f"yt-{safe}"[-180:]

    @staticmethod
    def _build_upload_title(
        *,
        batch_id: str,
        profile_name: str,
        role: str,
        file_path: str,
        config: dict[str, Any],
    ) -> str:
        configured_title = str(config.get("title") or "").strip()
        if configured_title:
            return configured_title[:500]
        stem = Path(file_path).stem.strip()
        if stem:
            return stem[:500]
        return f"{profile_name} {role} {batch_id}"[:500]

    @staticmethod
    def _to_merge_upload_result(
        job: YouTubeUploadJobRecord, blocked_reason: str | None
    ) -> YouTubeMergeUploadEnqueueResult:
        message = (
            "Merged upload job queued."
            if job.status == "pending"
            else "Merged upload job recorded but blocked until YouTube is connected."
        )
        return YouTubeMergeUploadEnqueueResult(
            job_uid=job.job_uid or "",
            status=job.status,
            profile_id=job.profile_id or "",
            batch_id=job.batch_id or "",
            role=job.role or "",
            file_path=job.file_path or "",
            message=message,
            blocked_reason=blocked_reason,
        )

    def _decrypt_client_secret(self, encrypted_secret: bytes) -> str:
        if self._encryption is None:
            raise RuntimeError("YouTube OAuth secret storage is unavailable.")
        return self._encryption.decrypt(encrypted_secret)

    def _decrypt_refresh_token(self, encrypted_refresh_token: bytes) -> str:
        if self._encryption is None:
            raise RuntimeError("YouTube OAuth secret storage is unavailable.")
        return self._encryption.decrypt(encrypted_refresh_token)

    def _encrypt_refresh_token(self, refresh_token: str) -> bytes:
        if self._encryption is None:
            raise RuntimeError("YouTube OAuth secret storage is unavailable.")
        return self._encryption.encrypt(refresh_token)

    def _build_google_flow(self, *, client_id: str, client_secret: str, callback_url: str):
        try:
            from google_auth_oauthlib.flow import Flow
        except Exception as exc:
            raise RuntimeError(f"Missing Google OAuth libraries: {exc}") from exc

        client_config = {
            "web": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [callback_url],
            }
        }
        return Flow.from_client_config(client_config, scopes=YOUTUBE_UPLOAD_SCOPES, redirect_uri=callback_url)

    async def _build_refreshed_credentials(self, account: YouTubeConnectedAccountRecord):
        oauth_app = None
        if account.oauth_app_id:
            oauth_app = await self._oauth_app_repo.get_by_id(account.oauth_app_id)
        if oauth_app is None:
            oauth_app = await self._oauth_app_repo.get_default()
        if oauth_app is None:
            raise ValidationError("No YouTube OAuth app is configured in the Admin Portal.")

        try:
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request as GoogleAuthRequest
        except Exception as exc:
            raise RuntimeError(f"Missing Google API auth libraries: {exc}") from exc

        credentials = Credentials(
            token=None,
            refresh_token=self._decrypt_refresh_token(account.encrypted_refresh_token),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=oauth_app.client_id,
            client_secret=self._decrypt_client_secret(oauth_app.encrypted_client_secret),
            scopes=account.scopes or YOUTUBE_UPLOAD_SCOPES,
        )
        try:
            credentials.refresh(GoogleAuthRequest())
        except Exception as exc:
            if self._is_revoked_token_error(exc):
                await self._connection_repo.delete_connected_account(
                    account.user_id,
                    account.profile_id,
                )
                raise ValidationError(
                    "YouTube sign-in expired for this profile. Reconnect from the YouTube tab."
                ) from exc
            raise
        return credentials

    @staticmethod
    def _is_revoked_token_error(exc: Exception) -> bool:
        message = str(exc).lower()
        return (
            "invalid_grant" in message
            or "token has been expired" in message
            or "token has been revoked" in message
        )

    async def _fetch_connected_channel(
        self, account: YouTubeConnectedAccountRecord
    ) -> dict[str, str]:
        credentials = await self._build_refreshed_credentials(account)
        channels = self._fetch_channels(credentials)
        matched = next(
            (channel for channel in channels if channel.get("id") == account.channel_id),
            None,
        )
        if matched is None:
            raise ValidationError("The connected YouTube channel could not be found during resync.")
        return matched

    @staticmethod
    def _uploads_root() -> Path:
        return (Path(__file__).resolve().parents[2] / "uploads").resolve()

    @staticmethod
    def _parse_channel_keywords(value: str | None) -> list[str]:
        raw = str(value or "").strip()
        if not raw:
            return []
        try:
            return [token.strip() for token in shlex.split(raw) if token.strip()]
        except Exception:
            return [part.strip() for part in raw.split(",") if part.strip()]

    def _download_remote_image(self, url: str) -> tuple[bytes, str] | None:
        target_url = str(url or "").strip()
        if not target_url:
            return None
        try:
            import httpx
        except Exception:
            return None

        try:
            response = httpx.get(target_url, timeout=20.0, follow_redirects=True)
            response.raise_for_status()
            content_type = str(response.headers.get("content-type") or "").split(";")[0].strip().lower()
            extension = mimetypes.guess_extension(content_type or "") or ".png"
            return response.content, extension
        except Exception:
            return None

    def _save_channel_remote_image(
        self,
        *,
        user_id: str,
        profile_id: str,
        folder: str,
        stem: str,
        url: str | None,
    ) -> str | None:
        downloaded = self._download_remote_image(str(url or "").strip())
        if downloaded is None:
            return None
        image_bytes, extension = downloaded
        safe_extension = extension if extension.startswith(".") else f".{extension}"
        output_dir = (self._uploads_root() / folder / user_id).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{profile_id}-{stem}{safe_extension}"
        output_path.write_bytes(image_bytes)
        return str(Path("uploads") / folder / user_id / f"{profile_id}-{stem}{safe_extension}")

    async def _sync_profile_from_channel(
        self,
        *,
        user_id: str,
        profile_id: str,
        channel: dict[str, Any],
    ) -> None:
        row = await self._db.fetchrow(
            """
            SELECT logo_path, image_config, youtube_config
            FROM channel_profiles
            WHERE id = $1::uuid AND user_id = $2::uuid
            """,
            profile_id,
            user_id,
        )
        if row is None:
            return

        image_config = _as_dict(row.get("image_config"))
        youtube_config = _as_dict(row.get("youtube_config"))

        description = str(channel.get("description") or "").strip()
        keywords = self._parse_channel_keywords(str(channel.get("keywords_raw") or ""))
        logo_path = self._save_channel_remote_image(
            user_id=user_id,
            profile_id=profile_id,
            folder="logos",
            stem="youtube-logo",
            url=str(channel.get("thumbnail_url") or ""),
        )
        banner_path = self._save_channel_remote_image(
            user_id=user_id,
            profile_id=profile_id,
            folder="covers",
            stem="youtube-cover",
            url=str(channel.get("banner_url") or ""),
        )

        if description:
            youtube_config["description"] = description
        if keywords:
            youtube_config["keywords"] = keywords
        if banner_path:
            image_config["cover_paths"] = [banner_path]

        await self._db.execute(
            """
            UPDATE channel_profiles
            SET logo_path = COALESCE($3, logo_path),
                image_config = $4::jsonb,
                youtube_config = $5::jsonb,
                updated_at = NOW()
            WHERE id = $1::uuid AND user_id = $2::uuid
            """,
            profile_id,
            user_id,
            logo_path,
            json.dumps(image_config),
            json.dumps(youtube_config),
        )

    def _fetch_channels(self, credentials: Any) -> list[dict[str, str]]:
        try:
            from googleapiclient.discovery import build
        except Exception as exc:
            raise RuntimeError(f"Missing Google API client libraries: {exc}") from exc

        service = build("youtube", "v3", credentials=credentials, cache_discovery=False)
        response = service.channels().list(
            part="snippet,brandingSettings",
            mine=True,
            maxResults=50,
        ).execute()
        items = response.get("items") if isinstance(response, dict) else []
        channels: list[dict[str, str]] = []
        if isinstance(items, list):
            for item in items:
                if not isinstance(item, dict):
                    continue
                channel_id = str(item.get("id", "")).strip()
                snippet = item.get("snippet") if isinstance(item.get("snippet"), dict) else {}
                branding = item.get("brandingSettings") if isinstance(item.get("brandingSettings"), dict) else {}
                branding_channel = branding.get("channel") if isinstance(branding.get("channel"), dict) else {}
                branding_image = branding.get("image") if isinstance(branding.get("image"), dict) else {}
                thumbnails = snippet.get("thumbnails") if isinstance(snippet.get("thumbnails"), dict) else {}
                thumbnail_url = ""
                for key in ("high", "medium", "default"):
                    value = thumbnails.get(key)
                    if isinstance(value, dict) and str(value.get("url") or "").strip():
                        thumbnail_url = str(value.get("url")).strip()
                        break
                channel_title = str(snippet.get("title", "")).strip()
                description = str(branding_channel.get("description") or snippet.get("description") or "").strip()
                keywords_raw = str(branding_channel.get("keywords") or "").strip()
                banner_url = str(branding_image.get("bannerExternalUrl") or "").strip()
                if channel_id:
                    channels.append(
                        {
                            "id": channel_id,
                            "title": channel_title,
                            "description": description,
                            "keywords_raw": keywords_raw,
                            "thumbnail_url": thumbnail_url,
                            "banner_url": banner_url,
                        }
                    )
        return channels

    def _fetch_playlists(self, credentials: Any) -> list[dict[str, str]]:
        try:
            from googleapiclient.discovery import build
        except Exception as exc:
            raise RuntimeError(f"Missing Google API client libraries: {exc}") from exc

        service = build("youtube", "v3", credentials=credentials, cache_discovery=False)
        response = service.playlists().list(
            part="snippet",
            mine=True,
            maxResults=50,
        ).execute()
        items = response.get("items") if isinstance(response, dict) else []
        playlists: list[dict[str, str]] = []
        if isinstance(items, list):
            for item in items:
                if not isinstance(item, dict):
                    continue
                playlist_id = str(item.get("id", "")).strip()
                snippet = item.get("snippet") if isinstance(item.get("snippet"), dict) else {}
                title = str(snippet.get("title", "")).strip() or "Playlist"
                if playlist_id:
                    playlists.append({"id": playlist_id, "title": title})
        return playlists
