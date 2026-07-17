"""Plan limit validation utilities.

Pure validation functions for plan limit fields, callable from the Plans router
before creating or updating plans.

Requirements: 1.2, 1.3, 1.5; Phase 3 / H6 paid recurring finite meters.
"""

from __future__ import annotations

from platform_api.exceptions import ValidationError


def validate_plan_limits(
    monthly_song_limit: int | None,
    monthly_image_limit: int | None,
    daily_song_limit_per_channel: int,
    daily_image_limit_per_channel: int,
) -> None:
    """Validate plan limit fields according to business rules.

    Raises ValidationError if any field is outside its allowed range:
    - monthly_song_limit: None (unlimited) or integer in [0, 100_000]
    - monthly_image_limit: None (unlimited) or integer in [0, 100_000]
    - daily_song_limit_per_channel: integer in [1, 1_000]
    - daily_image_limit_per_channel: integer in [1, 1_000]

    A monthly limit of 0 means the operation type is effectively disabled
    (plan-limit-zero). This is valid — the enforcement service will reject
    requests for that operation.
    """
    errors: dict[str, str] = {}

    if monthly_song_limit is not None:
        if not (0 <= monthly_song_limit <= 100_000):
            errors["monthly_song_limit"] = (
                "Must be between 0 and 100,000 inclusive (or null for unlimited)."
            )

    if monthly_image_limit is not None:
        if not (0 <= monthly_image_limit <= 100_000):
            errors["monthly_image_limit"] = (
                "Must be between 0 and 100,000 inclusive (or null for unlimited)."
            )

    if not (1 <= daily_song_limit_per_channel <= 1_000):
        errors["daily_song_limit_per_channel"] = (
            "Must be between 1 and 1,000 inclusive."
        )

    if not (1 <= daily_image_limit_per_channel <= 1_000):
        errors["daily_image_limit_per_channel"] = (
            "Must be between 1 and 1,000 inclusive."
        )

    if errors:
        raise ValidationError(
            message="Plan limit validation failed.",
            details=errors,
        )


def validate_paid_recurring_finite_meters(
    *,
    price_cents: int,
    billing_cycle_days: int | None,
    monthly_song_limit: int | None,
    monthly_image_limit: int | None,
    monthly_draft_limit: int | None,
    monthly_video_limit: int | None = None,
    monthly_merge_limit: int | None = None,
    is_active: bool = True,
) -> None:
    """Forbid null monthly meters on active paid recurring plans (H6).

    Lifetime plans (``billing_cycle_days is None``) may keep null/unlimited meters.
    Free or inactive plans are also exempt.
    """
    if not is_active or price_cents <= 0 or billing_cycle_days is None:
        return

    missing: list[str] = []
    if monthly_song_limit is None:
        missing.append("monthly_song_limit")
    if monthly_image_limit is None:
        missing.append("monthly_image_limit")
    if monthly_draft_limit is None:
        missing.append("monthly_draft_limit")
    if monthly_video_limit is None:
        missing.append("monthly_video_limit")
    if monthly_merge_limit is None:
        missing.append("monthly_merge_limit")

    if missing:
        raise ValidationError(
            message=(
                "Active paid recurring plans must set finite monthly song, draft, "
                "image, video, and merge limits (null/unlimited is not allowed)."
            ),
            details={"missing_limits": missing, "error_code": "PAID_PLAN_UNLIMITED_FORBIDDEN"},
        )
