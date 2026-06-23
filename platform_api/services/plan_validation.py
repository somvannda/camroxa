"""Plan limit validation utilities.

Pure validation functions for plan limit fields, callable from the Plans router
before creating or updating plans.

Requirements: 1.2, 1.3, 1.5
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
