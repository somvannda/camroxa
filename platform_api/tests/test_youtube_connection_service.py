from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from platform_api.exceptions import ValidationError
from platform_api.repositories.youtube_connection_repo import YouTubeConnectSessionRecord
from platform_api.services.youtube_connection_service import (
    YouTubeConnectionService,
    _is_local_oauth_callback,
    _oauth_transport_context,
    _validate_oauth_callback_url,
)
from platform_api.services.youtube_upload_runtime import (
    UploadResult,
    VideoProcessingStatus,
)


def test_local_loopback_http_callback_is_allowed() -> None:
    _validate_oauth_callback_url("http://127.0.0.1:8000/api/v1/youtube/oauth/callback")
    assert _is_local_oauth_callback("http://localhost:8000/api/v1/youtube/oauth/callback") is True


def test_remote_http_callback_is_rejected() -> None:
    with pytest.raises(ValidationError):
        _validate_oauth_callback_url("http://example.com/api/v1/youtube/oauth/callback")


def test_oauth_transport_context_enables_insecure_transport_only_temporarily() -> None:
    os.environ.pop("OAUTHLIB_INSECURE_TRANSPORT", None)

    with _oauth_transport_context("http://127.0.0.1:8000/api/v1/youtube/oauth/callback"):
        assert os.environ.get("OAUTHLIB_INSECURE_TRANSPORT") == "1"

    assert "OAUTHLIB_INSECURE_TRANSPORT" not in os.environ


class FakeDb:
    async def fetch(self, query: str, *args):
        return []

    async def fetchrow(self, query: str, *args):
        sql = " ".join(str(query).split()).lower()
        if "from channel_profiles" in sql and "where id = $1 and user_id = $2" in sql:
            return {"id": args[0], "user_id": args[1]}
        if "select name from channel_profiles where id = $1" in sql:
            return {"name": "Boss Profile"}
        return None


class FakeOAuthAppRepo:
    def __init__(self) -> None:
        self.default = SimpleNamespace(
            id=str(uuid4()),
            client_id="client-id",
            encrypted_client_secret=b"secret-bytes",
        )

    async def get_default(self):
        return self.default

    async def get_by_id(self, oauth_app_id: str):
        if oauth_app_id == self.default.id:
            return self.default
        return None


class FakeConnectionRepo:
    def __init__(self) -> None:
        self.session: YouTubeConnectSessionRecord | None = None
        self.claimed_jobs = []
        self.status_updates = []

    async def mark_profile_sessions_expired(self, user_id: str, profile_id: str) -> None:
        return None

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
        self.session = YouTubeConnectSessionRecord(
            id=str(uuid4()),
            user_id=user_id,
            profile_id=profile_id,
            oauth_app_id=oauth_app_id,
            state_token=state_token,
            code_verifier=code_verifier,
            status="pending_browser",
            encrypted_refresh_token=None,
            scopes=[],
            channels=[],
            error_message=None,
            expires_at=expires_at,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        return self.session

    async def get_session_by_state(self, state_token: str) -> YouTubeConnectSessionRecord | None:
        if self.session and self.session.state_token == state_token:
            return self.session
        return None

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
        assert self.session is not None
        self.session = YouTubeConnectSessionRecord(
            id=self.session.id,
            user_id=self.session.user_id,
            profile_id=self.session.profile_id,
            oauth_app_id=self.session.oauth_app_id,
            state_token=self.session.state_token,
            code_verifier=self.session.code_verifier,
            status=status or self.session.status,
            encrypted_refresh_token=encrypted_refresh_token or self.session.encrypted_refresh_token,
            scopes=scopes or self.session.scopes,
            channels=channels or self.session.channels,
            error_message=error_message,
            expires_at=self.session.expires_at,
            created_at=self.session.created_at,
            updated_at=datetime.now(timezone.utc),
        )
        return self.session

    async def upsert_connected_account(self, **kwargs):
        return SimpleNamespace(**kwargs)

    async def get_account_for_user_profile(self, user_id: str, profile_id: str):
        return None

    async def claim_upload_jobs_for_run(self, user_id: str, *, batch_id: str | None, statuses: list[str], limit: int):
        return list(self.claimed_jobs)

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
        self.status_updates.append(
            {
                "job_id": job_id,
                "user_id": user_id,
                "status": status,
                "error_message": error_message,
                "youtube_video_id": youtube_video_id,
                "youtube_url": youtube_url,
            }
        )


class FakeEncryption:
    def decrypt(self, value: bytes) -> str:
        return "client-secret"

    def encrypt(self, value: str) -> bytes:
        return f"enc:{value}".encode("utf-8")


class FakeFlow:
    def __init__(self) -> None:
        self.code_verifier: str | None = None
        self.fetch_token_code_verifier: str | None = None
        self.credentials = SimpleNamespace(
            refresh_token="refresh-token",
            scopes=[
                "https://www.googleapis.com/auth/youtube.upload",
                "https://www.googleapis.com/auth/youtube.readonly",
            ],
        )

    def authorization_url(self, **kwargs):
        return "https://accounts.google.com/o/oauth2/auth", "state-token"

    def fetch_token(self, *, authorization_response: str):
        self.fetch_token_code_verifier = self.code_verifier


@pytest.mark.asyncio
async def test_youtube_oauth_roundtrip_persists_pkce_code_verifier(monkeypatch: pytest.MonkeyPatch) -> None:
    db = FakeDb()
    oauth_app_repo = FakeOAuthAppRepo()
    connection_repo = FakeConnectionRepo()
    service = YouTubeConnectionService(
        db=db,
        oauth_app_repo=oauth_app_repo,
        connection_repo=connection_repo,
        encryption=FakeEncryption(),
    )

    auth_flow = FakeFlow()
    callback_flow = FakeFlow()
    flow_queue = [auth_flow, callback_flow]
    monkeypatch.setattr(service, "_build_google_flow", lambda **kwargs: flow_queue.pop(0))
    monkeypatch.setattr(
        service,
        "_fetch_channels",
        lambda credentials: [{"id": "channel-1", "title": "Boss Channel"}],
    )

    user_id = uuid4()
    profile_id = uuid4()
    callback_url = "http://127.0.0.1:8000/api/v1/youtube/oauth/callback"

    start = await service.start_connection(
        user_id=user_id,
        profile_id=profile_id,
        callback_url=callback_url,
    )

    assert start.auth_url == "https://accounts.google.com/o/oauth2/auth"
    assert connection_repo.session is not None
    assert connection_repo.session.code_verifier

    result = await service.finalize_callback(
        callback_url=callback_url,
        callback_request_url=f"{callback_url}?state={start.session_id}&code=oauth-code",
        state_token="state-token",
        error_message=None,
    )

    assert result.status == "connected"
    assert callback_flow.fetch_token_code_verifier == connection_repo.session.code_verifier


@pytest.mark.asyncio
async def test_run_pending_upload_jobs_marks_success(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    user_id = uuid4()
    profile_id = uuid4()
    batch_id = uuid4()
    merged_path = tmp_path / "MERGED_PRIMARY.mp4"
    merged_path.write_bytes(b"0" * 300_000)
    thumbnail_path = tmp_path / "thumbnail-16x9.png"
    thumbnail_path.write_bytes(b"thumb")

    class UploadDb(FakeDb):
        async def fetchrow(self, query: str, *args):
            sql = " ".join(str(query).split()).lower()
            if "from channel_profiles" in sql and "where id = $1 and user_id = $2" in sql:
                return {"id": args[0], "user_id": args[1]}
            if "select name from channel_profiles where id = $1" in sql:
                return {"name": "Boss Profile"}
            if "select name, youtube_config" in sql:
                return {
                    "name": "Boss Profile",
                    "youtube_config": {
                        "visibility": "private",
                        "category": "10",
                        "playlist": "playlist-1",
                        "made_for_kids": False,
                        "ai_use": True,
                    },
                }
            if "from batches" in sql and "planned_from_date" in sql:
                return {
                    "id": batch_id,
                    "created_at": datetime.now(timezone.utc),
                    "planned_from_date": None,
                    "planned_to_date": None,
                    "ok_run_dir": str(tmp_path),
                    "alt_run_dir": None,
                }
            if "from batch_channel_assets" in sql:
                return {
                    "thumbnail_16x9_path": str(thumbnail_path),
                    "run_dir": str(tmp_path),
                }
            return await super().fetchrow(query, *args)

    db = UploadDb()
    oauth_app_repo = FakeOAuthAppRepo()
    connection_repo = FakeConnectionRepo()
    connection_repo.claimed_jobs = [
        SimpleNamespace(
            id=str(uuid4()),
            user_id=str(user_id),
            song_id=None,
            job_uid="yt-job-1",
            batch_id=str(batch_id),
            profile_id=str(profile_id),
            role="OK",
            file_path=str(merged_path),
            title="Boss Upload",
            description="Boss Description",
            tags="boss,upload",
            privacy_status="private",
            youtube_video_id=None,
            youtube_url=None,
            status="running",
            attempt_count=1,
            error_message=None,
        )
    ]
    service = YouTubeConnectionService(
        db=db,
        oauth_app_repo=oauth_app_repo,
        connection_repo=connection_repo,
        encryption=FakeEncryption(),
        settings_service=AsyncMock(
            get_merged_settings=AsyncMock(
                return_value={"perfYouTubeWorkers": 1, "youtubeUploadChunkSizeMb": 64}
            )
        ),
    )

    monkeypatch.setattr(
        service,
        "build_refreshed_credentials_for_profile",
        AsyncMock(return_value=object()),
    )
    monkeypatch.setattr(
        "platform_api.services.youtube_connection_service.upload_video",
        lambda **kwargs: UploadResult(
            video_id="video-1",
            url="https://www.youtube.com/watch?v=video-1",
            thumbnail_error="",
            playlist_error="",
        ),
    )
    monkeypatch.setattr(
        "platform_api.services.youtube_connection_service.get_video_processing_status",
        lambda **kwargs: VideoProcessingStatus(
            processing_status="processed",
            upload_status="uploaded",
        ),
    )

    completed = await service.run_pending_upload_jobs(str(user_id), batch_id=str(batch_id), limit=1)

    assert completed == 1
    assert connection_repo.status_updates[-1]["status"] == "success"
    assert connection_repo.status_updates[-1]["youtube_video_id"] == "video-1"
