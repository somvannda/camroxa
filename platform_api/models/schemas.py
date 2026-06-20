"""Pydantic request/response models for the Platform API.

These schemas handle HTTP-layer validation and serialization.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any
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
    style: str = Field(min_length=1, max_length=255)
    instrumental: bool = False


class ImageGenerationRequest(BaseModel):
    """Submit an image generation request (background or thumbnail)."""

    kind: str = Field(pattern=r"^(background|thumbnail)$")
    prompt: str = Field(min_length=1, max_length=2000)
    image_base64: str  # PNG bytes as base64
    resolution: str = Field(pattern=r"^\d+x\d+$")
    style_strength: float = Field(ge=0.0, le=1.0, default=0.6)


class DraftGenerationRequest(BaseModel):
    """Submit a song draft generation request to the LLM provider."""

    language: str = Field(default="en", max_length=20)
    creativity_level: int = Field(ge=0, le=100, default=50)
    description_id: str | None = None
    structure_id: str | None = None
    avoid_titles: list[str] = Field(default_factory=list, max_length=200)
    avoid_albums: list[str] = Field(default_factory=list, max_length=200)
    avoid_openings: list[str] = Field(default_factory=list, max_length=200)
    forced_title: str | None = None
    forced_album: str | None = None
    forced_opening: str | None = None


# ---------------------------------------------------------------------------
# Batch Schemas
# ---------------------------------------------------------------------------


class BatchCreateRequest(BaseModel):
    """Create a new batch generation run."""

    ok_profile_id: str
    alt_profile_id: str
    song_count: int = Field(ge=1, le=50)
    language: str = Field(default="en")
    creativity_level: int = Field(ge=0, le=100, default=50)
    pairing_mode: str = Field(default="match_key")


class BatchCreateResponse(BaseModel):
    """Response returned after creating a batch."""

    batch_id: str
    status: str
    song_count: int


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


class RecentActivity(BaseModel):
    """A single recent activity event."""

    timestamp: datetime
    kind: str
    detail: str
    status: str


class DashboardStatsResponse(BaseModel):
    """Aggregated dashboard statistics for the current user."""

    credits_spent: int = 0
    credits_remaining: int = 0
    credits_total: int = 0
    songs_generated: int = 0
    songs_remaining: int | None = None
    songs_quota: int | None = None
    images_generated: int = 0
    videos_generated: int = 0
    usage_by_day: list[DailyUsage] = []
    recent_activity: list[RecentActivity] = []
