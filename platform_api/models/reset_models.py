"""Pydantic request/response models and domain dataclasses for the admin user data reset feature.

Handles validation, serialization, and domain types for reset, backup, and restore operations.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Pydantic Request/Response Schemas
# ---------------------------------------------------------------------------


class ResetRequest(BaseModel):
    """Password confirmation payload for triggering a user data reset."""

    password: str = Field(..., min_length=1, max_length=200)


class RestoreRequest(BaseModel):
    """Payload for restoring user data from a backup file."""

    backup_filename: str = Field(
        ...,
        min_length=1,
        max_length=300,
        pattern=r"^backup_\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}Z\.json$",
    )
    password: str = Field(..., min_length=1, max_length=200)


class ResetResponse(BaseModel):
    """Response returned after a user data reset operation."""

    status: str  # "success" or "partial"
    backup_filename: str
    tables_cleared: list[str]
    record_counts: dict[str, int]
    total_records_deleted: int
    redis_flushed: bool
    redis_error: str | None = None


class BackupMetadataResponse(BaseModel):
    """Metadata for a single backup file in API responses."""

    filename: str
    created_at: str  # ISO 8601
    file_size_bytes: int
    total_records: int
    tables: list[str]
    actor_id: str | None = None


class BackupListResponse(BaseModel):
    """List of available backup files."""

    backups: list[BackupMetadataResponse]


class RestoreResponse(BaseModel):
    """Response returned after a successful data restore operation."""

    status: str  # "success"
    backup_filename: str
    records_restored: int
    records_skipped: int


# ---------------------------------------------------------------------------
# Domain Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BackupMetadata:
    """Immutable metadata for a backup file on the filesystem."""

    filename: str
    created_at: datetime
    file_size_bytes: int
    total_records: int
    tables: list[str]
    actor_id: str | None = None


@dataclass(frozen=True)
class ResetResult:
    """Immutable result of a user data reset operation."""

    backup_filename: str
    tables_cleared: list[str]
    record_counts: dict[str, int]
    total_records_deleted: int
    redis_flushed: bool
    redis_error: str | None = None


@dataclass(frozen=True)
class RestoreResult:
    """Immutable result of a data restore operation."""

    backup_filename: str
    records_restored: int
    records_skipped: int


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DELETION_ORDER: list[str] = [
    # Leaf tables (no dependents)
    "batch_channel_assets",
    "profile_video_templates",
    "image_jobs",
    "suno_tasks",
    "songs",
    "batches",
    "youtube_connected_accounts",
    "youtube_connect_sessions",
    "credit_transactions",
    "credit_wallets",
    "notification_queue",
    "user_settings",
    "refresh_tokens",
    "usage_tracking",
    "plan_usage",
    "onboarding_ai_usage",
    "onboarding_drafts",
    "billing_payments",
    "redeem_code_redemptions",
    "invitation_code_redemptions",
    "licenses",
    "client_log_batches",
    "audit_logs",
    "channel_profiles",
    # Parent table last
    "users",  # WHERE email != 'admin@mgfaceless.com'
]

REDIS_FLUSH_PATTERNS: list[str] = [
    "token_blocklist:*",
    "rate_limit:*",
    "session:*",
]
