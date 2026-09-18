"""Pydantic request/response models for the Platform API.

These schemas handle HTTP-layer validation and serialization.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


# ---------------------------------------------------------------------------
# Auth Schemas
# ---------------------------------------------------------------------------

_PASSWORD_PATTERN = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,128}$")


class LoginRequest(BaseModel):
    """Credentials for email/password authentication."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    cf_turnstile_response: str | None = Field(default=None, description="Cloudflare Turnstile token")


class TokenResponse(BaseModel):
    """JWT token pair returned on successful authentication."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds until access_token expiry


class RegisterRequest(BaseModel):
    """New user registration payload."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=2, max_length=50)

    @field_validator("password")
    @classmethod
    def password_complexity(cls, v: str) -> str:
        """Validate password has at least one uppercase, one lowercase, and one digit."""
        if not _PASSWORD_PATTERN.match(v):
            raise ValueError(
                "Password must contain at least one uppercase letter, "
                "one lowercase letter, and one digit"
            )
        return v


# ---------------------------------------------------------------------------
# Generation Schemas
# ---------------------------------------------------------------------------


class SunoGenerationRequest(BaseModel):
    """Submit a music generation request to Suno."""

    model: str = Field(pattern=r"^(V5|V5_5)$")
    title: str = Field(min_length=1, max_length=255)
    lyrics: str = Field(min_length=1)
    style: str = Field(min_length=1, max_length=1000)
    instrumental: bool = False


class ImageGenerationRequest(BaseModel):
    """Submit an image generation request (background or thumbnail)."""

    kind: str = Field(pattern=r"^(background|thumbnail)$")
    prompt: str = Field(min_length=1, max_length=5000)
    image_base64: str  # PNG bytes as base64
    resolution: str = Field(pattern=r"^\d+x\d+$")
    style_strength: float = Field(ge=0.0, le=1.0, default=0.6)


class DraftGenerationRequest(BaseModel):
    """Submit a song draft generation request to the LLM provider."""

    language: str = Field(default="en", max_length=20)
    secondary_language: str | None = Field(default=None, max_length=20)
    creativity_level: int = Field(ge=0, le=100, default=50)
    description_id: str | None = None
    structure_id: str | None = None
    mood_id: str | None = None
    structure_mode: str = Field(default="template", pattern=r"^(template|ai_free|suno)$")
    avoid_titles: list[str] = Field(default_factory=list, max_length=200)
    avoid_albums: list[str] = Field(default_factory=list, max_length=200)
    avoid_openings: list[str] = Field(default_factory=list, max_length=200)
    forced_title: str | None = None
    forced_album: str | None = None
    forced_opening: str | None = None
    title_seed: str | None = None
    album_seed: str | None = None


# ---------------------------------------------------------------------------
# Batch Schemas
# ---------------------------------------------------------------------------


class BatchCreateRequest(BaseModel):
    """Create a new batch generation run."""

    ok_profile_id: str
    alt_profile_id: str
    description_id: str | None = None
    structure_id: str | None = None
    mood_id: str | None = None
    structure_mode: str = Field(default="template", pattern=r"^(template|ai_free|suno)$")
    shuffle_structure: bool = False
    shuffle_mood: bool = False
    auto_gen_image: bool = False
    auto_gsuno: bool = False
    song_count: int = Field(ge=1, le=50)
    language: str = Field(default="en")
    secondary_language: str | None = Field(default=None, max_length=20)
    creativity_level: int = Field(ge=0, le=100, default=50)
    pairing_mode: str = Field(default="match_key")
    from_date: date
    to_date: date
    ok_run_dir: str | None = None
    alt_run_dir: str | None = None
    album: str | None = Field(default=None, max_length=120)

    @field_validator("to_date")
    @classmethod
    def validate_date_range(cls, value: date, info) -> date:
        from_date = info.data.get("from_date")
        if from_date is not None and value < from_date:
            raise ValueError("to_date must be on or after from_date")
        return value


class BatchCreateResponse(BaseModel):
    """Response returned after creating a batch."""

    batch_id: str
    status: str
    song_count: int
    from_date: date
    to_date: date
    planned_days: int
    ok_run_dir: str | None = None
    alt_run_dir: str | None = None


class MusicPlanPreflightRequest(BaseModel):
    """Validate an entire music automation plan before creating batches."""

    ok_profile_ids: list[str] = Field(min_length=1)
    alt_profile_ids: list[str] = Field(min_length=1)
    from_date: date
    to_date: date
    song_count: int = Field(ge=1, le=50)
    auto_gen_image: bool = False
    auto_gsuno: bool = False

    @field_validator("to_date")
    @classmethod
    def validate_plan_date_range(cls, value: date, info) -> date:
        from_date = info.data.get("from_date")
        if from_date is not None and value < from_date:
            raise ValueError("to_date must be on or after from_date")
        return value


class MusicPlanPreflightResponse(BaseModel):
    """Whether the user can run the requested music automation plan."""

    can_generate: bool
    reason: str | None = None
    batch_count: int = 0
    total_songs: int = 0
    total_wallet_cost: int = 0
    wallet_balance: int = 0
    covered_by_subscription: bool = False
    songs_remaining: int | None = None
    images_remaining: int | None = None
    drafts_remaining: int | None = None
    credit_shortfall: int | None = None


class ChannelDailyQuotaResponse(BaseModel):
    """Per-channel daily quota usage for one profile."""

    profile_id: str
    profile_name: str
    daily_songs_used: int
    daily_songs_limit: int
    daily_songs_remaining: int
    daily_images_used: int
    daily_images_limit: int
    daily_images_remaining: int
    daily_drafts_used: int = 0
    daily_drafts_limit: int = 0
    daily_drafts_remaining: int = 0


class QuotaStatusResponse(BaseModel):
    """Monthly and per-channel daily quota snapshot."""

    songs_remaining: int | None = None
    songs_quota: int | None = None
    images_remaining: int | None = None
    images_quota: int | None = None
    drafts_remaining: int | None = None
    drafts_quota: int | None = None
    videos_remaining: int | None = None
    videos_quota: int | None = None
    merges_remaining: int | None = None
    merges_quota: int | None = None
    daily_videos_remaining: int | None = None
    daily_videos_limit: int | None = None
    daily_merges_remaining: int | None = None
    daily_merges_limit: int | None = None
    wallet_balance: int = 0
    renewal_alert: str = "none"
    channels: list[ChannelDailyQuotaResponse] = Field(default_factory=list)


class BatchStatusResponse(BaseModel):
    """Status summary of a batch run."""

    batch_id: str
    status: str
    total_songs: int
    drafts_completed: int
    drafts_failed: int
    suno_submitted: int
    suno_completed: int
    suno_failed: int
    audio_downloaded: int
    images_completed: int
    ok_run_dir: str | None = None
    alt_run_dir: str | None = None


class SongRetryResponse(BaseModel):
    """Response returned after retrying a failed song step."""

    batch_id: str
    song_id: str
    status: str
    title: str | None = None
    album: str | None = None


class SongSunoRetryRequest(BaseModel):
    """Optional draft overrides applied before Suno resubmission."""

    title: str | None = None
    album: str | None = None
    lyrics: str | None = None


class AlbumRewriteRequest(BaseModel):
    """Regenerate Primary (ok) or Secondary (alt) batch album name."""

    role: Literal["ok", "alt"] = "ok"


class AlbumRewriteResponse(BaseModel):
    """Result of rewriting a batch channel album."""

    batch_id: str
    role: str
    album: str


class TitleRewriteResponse(BaseModel):
    """Result of rewriting one song title."""

    batch_id: str
    song_id: str
    title: str


class BatchDeleteResponse(BaseModel):
    """Result of deleting a failed / non-audio batch."""

    batch_id: str
    deleted: bool = True
    songs_deleted: int = 0
    draft_quota_released: int = 0


class MusicHistorySongResponse(BaseModel):
    """Read-only song summary used by the music history surface."""

    song_id: str
    batch_index: int
    title: str | None = None
    album: str | None = None
    lyrics: str | None = None
    description_id: str | None = None
    description_name: str | None = None
    structure_id: str | None = None
    structure_name: str | None = None
    mood_id: str | None = None
    mood_name: str | None = None
    output_dir_ok: str | None = None
    output_dir_alt: str | None = None
    status: str
    suno_status: str | None = None
    suno_error_message: str | None = None
    youtube_status: str | None = None
    downloaded_ok: bool = False
    downloaded_alt: bool = False
    image_jobs_completed: int = 0
    image_jobs_total: int = 0
    suno_last_sanitize: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class MusicHistoryBatchResponse(BaseModel):
    """Read-only batch summary with nested songs for music history."""

    batch_id: str
    status: str
    song_count: int
    from_date: date | None = None
    to_date: date | None = None
    planned_days: int
    ok_profile_id: str | None = None
    ok_profile_name: str | None = None
    alt_profile_id: str | None = None
    alt_profile_name: str | None = None
    ok_album: str | None = None
    alt_album: str | None = None
    created_at: datetime
    updated_at: datetime
    songs: list[MusicHistorySongResponse] = Field(default_factory=list)


class MusicHistoryListResponse(BaseModel):
    """Top-level response for the music history endpoint."""

    batches: list[MusicHistoryBatchResponse] = Field(default_factory=list)
    summary: str
    updated_at: datetime


# ---------------------------------------------------------------------------
# Credit / Wallet Schemas
# ---------------------------------------------------------------------------


class WalletBalanceResponse(BaseModel):
    """User's current credit wallet state."""

    balance: int
    plan_quota_remaining: int | None = None
    recent_transactions: list[dict[str, Any]] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Error Schemas
# ---------------------------------------------------------------------------


class ErrorResponse(BaseModel):
    """Structured API error response."""

    code: str
    message: str
    details: dict[str, Any] | None = None
    retry_after: int | None = None


# ---------------------------------------------------------------------------
# Key Pool Schemas
# ---------------------------------------------------------------------------


class AddKeyRequest(BaseModel):
    """Add a new API key to a provider's pool."""

    key_value: str = Field(min_length=1, max_length=500)
    label: str = Field(min_length=1, max_length=100)
    priority: int = Field(ge=1, le=100, default=50)


class UpdateKeyRequest(BaseModel):
    """Update an existing key's metadata (all fields optional)."""

    label: str | None = Field(None, min_length=1, max_length=100)
    priority: int | None = Field(None, ge=1, le=100)
    key_value: str | None = Field(None, min_length=1, max_length=500)


class KeyEntryResponse(BaseModel):
    """Response for a single API key entry (key value masked)."""

    id: UUID
    provider: str
    label: str
    masked_key: str  # e.g. "sk-ab...xy4z"
    priority: int
    status: str
    total_requests: int
    daily_requests: int
    success_count: int
    failure_count: int
    rate_limit_hits: int
    last_used_at: datetime | None
    last_failure_at: datetime | None
    cooldown_remaining_seconds: int | None = None
    created_at: datetime


class ProviderConfigRequest(BaseModel):
    """Update a provider's pool configuration."""

    selection_strategy: str = Field(pattern=r"^(round_robin|priority)$")
    cooldown_seconds: int = Field(ge=10, le=3600)


class ProviderConfigResponse(BaseModel):
    """Current pool configuration for a provider."""

    provider: str
    selection_strategy: str
    cooldown_seconds: int


class ProviderHealthResponse(BaseModel):
    """Health summary for a single provider's key pool."""

    provider: str
    total_keys: int
    active_keys: int
    rate_limited_keys: int
    exhausted_keys: int
    disabled_keys: int
    health_indicator: str  # "healthy", "degraded", "critical"


class AllProvidersHealthResponse(BaseModel):
    """Health summary across all providers."""

    providers: list[ProviderHealthResponse]


class KeyStatusEventResponse(BaseModel):
    """A single key status transition event."""

    id: UUID
    key_label: str
    previous_status: str
    new_status: str
    trigger_reason: str
    http_status_code: int | None
    created_at: datetime


# ---------------------------------------------------------------------------
# Dashboard Stats Schemas
# ---------------------------------------------------------------------------


class DailyUsage(BaseModel):
    """Usage count for a single day."""

    date: str
    songs: int = 0
    images: int = 0
    videos: int = 0
    studio_exports: int = 0
    manual_exports: int = 0
    youtube_uploads: int = 0


class RecentActivity(BaseModel):
    """A single recent activity event."""

    timestamp: datetime
    kind: str
    detail: str
    status: str


class DashboardStatsResponse(BaseModel):
    """Aggregated dashboard statistics for the current user."""

    credits_spent: float = 0
    credits_remaining: float = 0
    credits_total: float = 0
    songs_generated: int = 0
    songs_remaining: int | None = None
    songs_quota: int | None = None
    images_remaining: int | None = None
    images_quota: int | None = None
    drafts_remaining: int | None = None
    drafts_quota: int | None = None
    images_generated: int = 0
    # Lifetime local exports (usage_tracking) + YouTube publishes.
    studio_exports: int = 0
    manual_exports: int = 0
    youtube_uploads: int = 0
    # Backward-compatible aliases:
    # videos_generated = studio + manual exports; videos_uploaded = YouTube successes.
    videos_generated: int = 0
    videos_uploaded: int = 0
    # Recent export performance (from video_export_telemetry, last 7 days).
    avg_studio_export_ms: int | None = None
    avg_manual_export_ms: int | None = None
    last_export_at: datetime | None = None
    usage_by_day: list[DailyUsage] = []
    recent_activity: list[RecentActivity] = []


class PublicStatsResponse(BaseModel):
    """Public aggregated platform statistics for marketing surfaces."""

    updated_at: datetime
    users_total: int = 0
    profiles_total: int = 0
    batches_total: int = 0
    songs_total: int = 0
    images_total: int = 0
    videos_total: int = 0
    studio_exports_total: int = 0
    manual_exports_total: int = 0
    youtube_uploads_total: int = 0


# ---------------------------------------------------------------------------
# Progress / Workflow Schemas
# ---------------------------------------------------------------------------


class ProgressRowMeta(BaseModel):
    """Supplemental row metadata for progress/workflow views."""

    batch_id: str
    profile_id: str
    role: str
    run_dir: str | None = None
    source_mode: str | None = None
    background_16x9_path: str | None = None
    background_9x16_path: str | None = None
    thumbnail_16x9_path: str | None = None
    thumbnail_9x16_path: str | None = None
    long_ready: bool = False
    reel_ready: bool = False
    pipeline_complete: bool = False
    expected: int = 0
    saved: int = 0
    download_ready: int = 0
    download_pending: int = 0
    bg_ready: int = 0
    bg_total: int = 0
    th_ready: int = 0
    th_total: int = 0
    bg_status: str = "PENDING"
    th_status: str = "PENDING"
    youtube_status: str = ""
    youtube_url: str | None = None
    youtube_success: int = 0
    youtube_pending: int = 0
    youtube_failed: int = 0
    music_started_at: datetime | None = None
    music_updated_at: datetime | None = None
    image_started_at: datetime | None = None
    image_updated_at: datetime | None = None
    youtube_created_at: datetime | None = None
    youtube_updated_at: datetime | None = None
    updated_at: datetime | None = None
    draft_failed_song_ids: list[str] = Field(default_factory=list)
    suno_failed_song_ids: list[str] = Field(default_factory=list)
    lost_song_ids: list[str] = Field(default_factory=list)


class ProgressRow(BaseModel):
    """Single row shown in the progress/workflow surfaces."""

    batch: str
    run_date: str
    channel: str
    album: str | None = None
    status: str
    music: str
    image: str
    converter: str
    merge: str
    youtube: str
    stage: str
    notes: str
    updated: str
    meta: ProgressRowMeta


class ProgressListResponse(BaseModel):
    """List response for aggregated progress/workflow rows."""

    rows: list[ProgressRow] = []
    summary: str = "Ready"
    updated_at: datetime
