"""Domain dataclasses for the Platform API.

These represent the core business entities persisted in PostgreSQL.
All entities use UUID primary keys and track creation/update timestamps.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from platform_api.models.enums import (
    ChannelRole,
    ImageKind,
    KeyStatus,
    LicenseStatus,
    PlanType,
    SelectionStrategy,
    TaskStatus,
    TransactionDirection,
    UserRole,
    UserStatus,
)


# ---------------------------------------------------------------------------
# User & Authentication
# ---------------------------------------------------------------------------


@dataclass
class User:
    """A registered platform user."""

    id: UUID = field(default_factory=uuid4)
    email: str = ""
    password_hash: str = ""
    display_name: str = ""
    role: UserRole = UserRole.USER
    status: UserStatus = UserStatus.ACTIVE
    email_confirmed: bool = False
    suspension_reason: str | None = None
    deleted_at: datetime | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Plans & Licenses
# ---------------------------------------------------------------------------


@dataclass
class Plan:
    """A subscription plan configuration (Admin-managed)."""

    id: UUID = field(default_factory=uuid4)
    name: str = ""
    price_cents: int = 0
    billing_cycle_days: int | None = None
    profile_allowance: int = 0
    monthly_song_limit: int | None = None
    monthly_image_limit: int | None = None
    daily_song_limit_per_channel: int = 7
    daily_image_limit_per_channel: int = 7
    is_active: bool = True
    effective_from: datetime = field(default_factory=datetime.utcnow)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class License:
    """A software license key tied to a plan and optionally to a user."""

    id: UUID = field(default_factory=uuid4)
    license_key: str = ""
    plan_id: UUID = field(default_factory=uuid4)
    user_id: UUID | None = None
    status: LicenseStatus = LicenseStatus.UNASSIGNED
    activated_at: datetime | None = None
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Credit System
# ---------------------------------------------------------------------------


@dataclass
class CreditWallet:
    """Per-user credit balance (one wallet per user)."""

    user_id: UUID = field(default_factory=uuid4)
    balance: int = 0
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def try_deduct(self, amount: int) -> bool:
        """Attempt to deduct credits. Returns True on success, False if insufficient."""
        if amount <= 0:
            return False
        if self.balance >= amount:
            self.balance -= amount
            return True
        return False

    def add(self, amount: int) -> None:
        """Add credits to the wallet."""
        if amount > 0:
            self.balance += amount


@dataclass
class CreditTransaction:
    """Record of a credit wallet transaction."""

    id: UUID = field(default_factory=uuid4)
    user_id: UUID = field(default_factory=uuid4)
    amount: int = 0
    direction: TransactionDirection = TransactionDirection.DEBIT
    reason: str = ""
    ref_id: str | None = None
    pack_id: UUID | None = None
    payment_ref: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Channel Profiles
# ---------------------------------------------------------------------------


@dataclass
class ChannelProfile:
    """A music generation configuration for a specific channel."""

    id: UUID = field(default_factory=uuid4)
    user_id: UUID = field(default_factory=uuid4)
    name: str = ""
    folder_name: str | None = None
    run_prefix: str | None = None
    logo_path: str | None = None
    video_template_id: str | None = None
    reel_template_id: str | None = None
    output_resolution: str = "1920x1080"
    image_config: dict[str, Any] = field(default_factory=dict)
    youtube_config: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Music Prompts (Admin-managed)
# ---------------------------------------------------------------------------


@dataclass
class MusicDescription:
    """An admin-managed song description (genre/mood/energy)."""

    id: UUID = field(default_factory=uuid4)
    name: str = ""
    content: str = ""
    match_key: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class MusicStructure:
    """An admin-managed song structure (section headers)."""

    id: UUID = field(default_factory=uuid4)
    name: str = ""
    content: str = ""
    match_key: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Channel Prompts (Admin-managed)
# ---------------------------------------------------------------------------


@dataclass
class ChannelPrompt:
    """An admin-managed prompt for channel setup wizard.

    Categories: title, logo, cover, description, keyword, tag
    match_key links to music_descriptions.match_key for genre-based prompt selection.
    """

    id: UUID = field(default_factory=uuid4)
    name: str = ""
    content: str = ""
    category: str = ""
    genre: str = ""
    match_key: str | None = None
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Generation Pipeline
# ---------------------------------------------------------------------------


@dataclass
class Song:
    """A song generated within a batch."""

    id: UUID = field(default_factory=uuid4)
    batch_id: UUID = field(default_factory=uuid4)
    batch_index: int = 0
    user_id: UUID = field(default_factory=uuid4)
    title: str | None = None
    album: str | None = None
    lyrics: str | None = None
    description_id: UUID | None = None
    structure_id: UUID | None = None
    status: str = "pending"
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class SunoTask:
    """Tracks a music generation request submitted to the Suno API."""

    id: UUID = field(default_factory=uuid4)
    song_id: UUID | None = None
    user_id: UUID = field(default_factory=uuid4)
    batch_id: UUID | None = None
    request_hash: str = ""
    model: str = "V5"
    title: str = ""
    lyrics: str | None = None
    style: str | None = None
    instrumental: bool = False
    external_task_id: str | None = None
    status: TaskStatus = TaskStatus.PENDING
    audio_url_ok: str | None = None
    audio_url_alt: str | None = None
    output_dir_ok: str | None = None
    output_dir_alt: str | None = None
    downloaded_ok: bool = False
    downloaded_alt: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ImageJob:
    """Tracks a background/thumbnail image generation request."""

    id: UUID = field(default_factory=uuid4)
    song_id: UUID | None = None
    user_id: UUID = field(default_factory=uuid4)
    batch_id: UUID | None = None
    profile_id: UUID | None = None
    kind: ImageKind = ImageKind.BACKGROUND
    channel_role: ChannelRole = ChannelRole.OK
    prompt: str | None = None
    provider: str | None = None
    resolution: str = "1920x1080"
    style_strength: float = 0.6
    status: TaskStatus = TaskStatus.PENDING
    attempt_count: int = 0
    output_image_path: str | None = None
    error: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Batch:
    """A group of songs generated together in a single run."""

    id: UUID = field(default_factory=uuid4)
    user_id: UUID = field(default_factory=uuid4)
    ok_profile_id: UUID | None = None
    alt_profile_id: UUID | None = None
    song_count: int = 1
    language: str = "en"
    creativity_level: int = 50
    pairing_mode: str = "match_key"
    status: str = "pending"
    ok_run_dir: str | None = None
    alt_run_dir: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------


@dataclass
class AuditLog:
    """Immutable record of a state-changing or security-relevant operation."""

    id: UUID = field(default_factory=uuid4)
    actor_id: UUID | None = None
    action_type: str = ""
    target_resource: str | None = None
    outcome: str = "success"
    credit_impact: int = 0
    source_ip: str | None = None
    client_id: str | None = None
    endpoint_path: str | None = None
    metadata: dict[str, Any] | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# API Key Pool
# ---------------------------------------------------------------------------


@dataclass
class ApiKeyEntry:
    """A single API key within a provider's pool."""

    id: UUID = field(default_factory=uuid4)
    provider: str = ""
    label: str = ""
    encrypted_key_value: bytes = b""
    priority: int = 50
    status: KeyStatus = KeyStatus.ACTIVE
    total_requests: int = 0
    daily_requests: int = 0
    success_count: int = 0
    failure_count: int = 0
    rate_limit_hits: int = 0
    last_used_at: datetime | None = None
    last_failure_at: datetime | None = None
    rate_limited_at: datetime | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class KeyPoolConfig:
    """Per-provider pool configuration."""

    id: UUID = field(default_factory=uuid4)
    provider: str = ""
    selection_strategy: SelectionStrategy = SelectionStrategy.PRIORITY
    cooldown_seconds: int = 60
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class KeyStatusEvent:
    """Immutable log of a key status transition."""

    id: UUID = field(default_factory=uuid4)
    key_id: UUID = field(default_factory=uuid4)
    provider: str = ""
    key_label: str = ""
    previous_status: KeyStatus = KeyStatus.ACTIVE
    new_status: KeyStatus = KeyStatus.ACTIVE
    trigger_reason: str = ""
    http_status_code: int | None = None
    response_summary: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)



# ---------------------------------------------------------------------------
# Usage Tracking (Credit Pricing Redesign)
# ---------------------------------------------------------------------------


@dataclass
class UsageRecord:
    """Tracks daily and monthly usage per user/channel/operation."""

    id: UUID = field(default_factory=uuid4)
    user_id: UUID = field(default_factory=uuid4)
    channel_profile_id: UUID | None = None
    operation_type: str = ""
    usage_date: Any = None  # date
    daily_count: int = 0
    monthly_count: int = 0
    period_start_date: Any = None  # date
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass(frozen=True)
class MarginDetails:
    """Computed margin details for a credit pricing entry."""

    sell_price_cents: int
    profit_margin_cents: int
    profit_margin_percent: float
