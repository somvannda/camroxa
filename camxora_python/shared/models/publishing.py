"""Models for Post for Me publishing (desktop client)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PublishAccount(BaseModel):
    id: str
    profile_id: str
    platform: str = "youtube"
    provider: str = "postforme"
    postforme_account_id: str = ""
    username: str | None = None
    display_name: str | None = None
    avatar_url: str | None = None
    status: str = "connected"


class PublishAccountsResponse(BaseModel):
    accounts: list[PublishAccount] = Field(default_factory=list)


class StartPublishConnectionResponse(BaseModel):
    session_id: str
    auth_url: str
    status: str = "pending_browser"


class PublishConnectSession(BaseModel):
    session_id: str
    status: str = "pending_browser"
    account_ids: list[str] = Field(default_factory=list)
    error_message: str | None = None


class PublishQuote(BaseModel):
    op: str = "publish"
    credits_per_upload: float = 5.0
    amount_units: int = 0
    balance: float = 0.0
    available: bool = False
    platforms: list[str] = Field(default_factory=list)


class CreatePublishJobRequest(BaseModel):
    profile_id: str
    platform: str = "youtube"
    batch_id: str | None = None
    role: str = "OK"
    title: str
    description: str | None = None
    tags: list[str] | str | None = None
    privacy_status: str = "private"
    publish_at: str | None = None
    made_for_kids: bool = False
    contains_synthetic_media: bool = True
    file_name: str = ""
    file_size_bytes: int | None = None
    file_checksum: str | None = None
    file_path: str | None = None
    thumbnail_path: str | None = None


class CreatePublishJobResponse(BaseModel):
    job_uid: str
    status: str
    upload_url: str | None = None
    upload_expires_at: str | None = None
    media_url: str | None = None
    thumbnail_upload_url: str | None = None
    thumbnail_media_url: str | None = None
    file_name: str = ""
    credits_per_upload: float = 5.0
    platforms: list[str] = Field(default_factory=list)
    existing: bool = False


class PublishJob(BaseModel):
    job_uid: str
    status: str
    platform: str = "youtube"
    provider: str = "postforme"
    batch_id: str | None = None
    profile_id: str | None = None
    role: str = "OK"
    title: str = ""
    description: str | None = None
    privacy_status: str = "private"
    scheduled_at: str | None = None
    youtube_video_id: str | None = None
    youtube_url: str | None = None
    postforme_post_id: str | None = None
    credits_charged: float = 0.0
    error_code: str | None = None
    error_message: str | None = None
    attempt_count: int = 0
    created_at: str | None = None
    updated_at: str | None = None


class PublishJobsResponse(BaseModel):
    jobs: list[PublishJob] = Field(default_factory=list)


class RetryPublishJobResponse(BaseModel):
    job_uid: str
    status: str
    upload_url: str | None = None
    media_url: str | None = None
