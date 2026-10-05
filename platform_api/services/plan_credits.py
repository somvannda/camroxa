"""Credit-cadence validation for plan configuration.

A plan grants **either** daily **or** monthly credits, never both, so the two
grant paths (``ensure_daily_grant`` / ``ensure_period_grant``) cannot both fire
and double-credit. One helper, used by every admin editor path, keeps the rule
in a single place (mirrored by a DB CHECK in migration 131).
"""

from __future__ import annotations

from platform_api.exceptions import ValidationError


def validate_credit_cadence(
    *,
    monthly_credits: int | None,
    daily_credits: int | None,
) -> None:
    """Reject a plan that would grant both daily and monthly credits."""
    monthly = int(monthly_credits or 0)
    daily = int(daily_credits or 0)
    if monthly > 0 and daily > 0:
        raise ValidationError(
            "A plan may grant daily or monthly credits, not both.",
            details={"monthly_credits": monthly, "daily_credits": daily},
        )
