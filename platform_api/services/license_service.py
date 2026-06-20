"""License management service.

Provides license creation, assignment, revocation, validation, quota enforcement,
plan offer logic, and plan deactivation handling.

Requirements: 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.9, 4.10, 4.11, 4.12
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Protocol
from uuid import UUID

from platform_api.exceptions import (
    DuplicateError,
    LicenseExpiredError,
    NotFoundError,
    QuotaExceededError,
    ValidationError,
)
from platform_api.models.domain import License, Plan
from platform_api.models.enums import LicenseStatus

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Protocol interfaces for dependency injection
# ---------------------------------------------------------------------------


class LicenseRepositoryProtocol(Protocol):
    """Protocol for license repository operations."""

    async def create(self, plan_id: UUID) -> License:
        """Create a new unassigned license."""
        ...

    async def get_by_id(self, license_id: UUID) -> License | None:
        """Get a license by its ID."""
        ...

    async def assign_to_user(
        self, license_id: UUID, user_id: UUID, plan: Plan
    ) -> License:
        """Assign a license to a user."""
        ...

    async def revoke(self, license_id: UUID) -> bool:
        """Revoke a license."""
        ...

    async def get_active_for_user(self, user_id: UUID) -> License | None:
        """Get the active license for a user."""
        ...

    async def has_duplicate_plan(self, user_id: UUID, plan_id: UUID) -> bool:
        """Check if user already has an active license for the same plan."""
        ...


class PlanRepositoryProtocol(Protocol):
    """Protocol for plan repository operations."""

    async def get_by_id(self, plan_id: UUID) -> Plan | None:
        """Get a plan by its ID."""
        ...

    async def get_or_create_usage(
        self,
        user_id: UUID,
        license_id: UUID,
        period_start: date,
        period_end: date,
    ) -> dict[str, Any]:
        """Get or create a plan usage record for the current billing period."""
        ...

    async def get_current_usage(self, user_id: UUID, license_id: UUID) -> int:
        """Get the current period's song usage count."""
        ...


class CreditRepositoryProtocol(Protocol):
    """Protocol for credit wallet operations (optional, for lifetime bonus)."""

    async def add_credits(
        self, user_id: UUID, amount: int, reason: str, ref_id: str | None = None
    ) -> int:
        """Add credits to a user's wallet. Returns new balance."""
        ...


class PlanOfferRepositoryProtocol(Protocol):
    """Protocol for plan offer (promotional pricing) operations."""

    async def get_active_offers_for_plan(self, plan_id: UUID) -> list[dict[str, Any]]:
        """Get all active offers for a plan."""
        ...

    async def get_offer_by_id(self, offer_id: UUID) -> dict[str, Any] | None:
        """Get a specific offer by ID."""
        ...

    async def increment_redemption(self, offer_id: UUID) -> dict[str, Any] | None:
        """Increment the redemption count. Returns updated offer or None."""
        ...

    async def deactivate_offer(self, offer_id: UUID) -> None:
        """Deactivate an offer (set is_active=false)."""
        ...


class DailyUsageRepositoryProtocol(Protocol):
    """Protocol for tracking daily song generation per channel."""

    async def get_daily_song_count(self, user_id: UUID, date: date) -> int:
        """Get total songs generated today by a user."""
        ...

    async def get_daily_song_count_per_channel(
        self, user_id: UUID, channel_count: int, date: date
    ) -> int:
        """Get average songs generated today per channel."""
        ...


# ---------------------------------------------------------------------------
# License Service
# ---------------------------------------------------------------------------

# Default constants
LIFETIME_BONUS_CREDITS = 1000
DEFAULT_DAILY_SONG_LIMIT_PER_CHANNEL = 7


class LicenseService:
    """Service for managing licenses, plans, quotas, and promotional offers.

    Handles the full license lifecycle including creation, assignment,
    revocation, validation, and quota enforcement. Implements plan offer
    logic with promotional pricing and automatic deactivation.

    Args:
        license_repo: Repository for license CRUD operations.
        plan_repo: Repository for plan queries and usage tracking.
        credit_repo: Optional repository for credit wallet operations
            (used for lifetime bonus crediting).
        offer_repo: Optional repository for plan offer management.
        daily_usage_repo: Optional repository for daily usage tracking.
    """

    def __init__(
        self,
        license_repo: LicenseRepositoryProtocol,
        plan_repo: PlanRepositoryProtocol,
        credit_repo: CreditRepositoryProtocol | None = None,
        offer_repo: PlanOfferRepositoryProtocol | None = None,
        daily_usage_repo: DailyUsageRepositoryProtocol | None = None,
    ) -> None:
        self._license_repo = license_repo
        self._plan_repo = plan_repo
        self._credit_repo = credit_repo
        self._offer_repo = offer_repo
        self._daily_usage_repo = daily_usage_repo

    # -----------------------------------------------------------------------
    # License CRUD
    # -----------------------------------------------------------------------

    async def create_license(self, plan_id: UUID) -> License:
        """Create a new unassigned license for the specified plan.

        Validates that the plan exists and is active before creating
        the license. Inactive plans cannot have new licenses created.

        Args:
            plan_id: The UUID of the plan to create a license for.

        Returns:
            The newly created License domain object.

        Raises:
            NotFoundError: If the plan does not exist.
            ValidationError: If the plan is inactive (Req 4.12).
        """
        plan = await self._plan_repo.get_by_id(plan_id)
        if plan is None:
            raise NotFoundError(
                "Plan not found.",
                details={"plan_id": str(plan_id)},
            )

        if not plan.is_active:
            raise ValidationError(
                "Cannot create license for inactive plan.",
                details={"plan_id": str(plan_id), "plan_name": plan.name},
            )

        license = await self._license_repo.create(plan_id)
        logger.info(
            "License created: license_id=%s, plan_id=%s", license.id, plan_id
        )
        return license

    async def assign_license(self, license_id: UUID, user_id: UUID) -> License:
        """Assign an unassigned license to a user.

        Validates:
        - License exists
        - License is unassigned
        - Plan is active
        - User does not already have an active license of the same plan type (Req 4.9)
        - For lifetime plans: credits 1,000 bonus songs to wallet (Req 6.11)

        Args:
            license_id: The UUID of the license to assign.
            user_id: The UUID of the user to assign the license to.

        Returns:
            The updated License domain object with user assignment.

        Raises:
            NotFoundError: If the license or plan does not exist.
            ValidationError: If the license is already assigned or plan is inactive.
            DuplicateError: If the user already has an active license of the same plan type.
        """
        # Fetch the license
        license = await self._license_repo.get_by_id(license_id)
        if license is None:
            raise NotFoundError(
                "License not found.",
                details={"license_id": str(license_id)},
            )

        # Check license is unassigned
        if license.status != LicenseStatus.UNASSIGNED:
            raise ValidationError(
                "License is not in unassigned state.",
                details={
                    "license_id": str(license_id),
                    "current_status": license.status.value,
                },
            )

        # Fetch the plan
        plan = await self._plan_repo.get_by_id(license.plan_id)
        if plan is None:
            raise NotFoundError(
                "Plan not found for license.",
                details={
                    "license_id": str(license_id),
                    "plan_id": str(license.plan_id),
                },
            )

        # Check plan is active (Req 4.12)
        if not plan.is_active:
            raise ValidationError(
                "Cannot assign license for inactive plan.",
                details={"plan_id": str(plan.id), "plan_name": plan.name},
            )

        # Check for duplicate plan type (Req 4.9)
        has_duplicate = await self._license_repo.has_duplicate_plan(
            user_id, license.plan_id
        )
        if has_duplicate:
            raise DuplicateError(
                "User already has an active license of this plan type.",
                details={
                    "user_id": str(user_id),
                    "plan_id": str(license.plan_id),
                    "plan_name": plan.name,
                },
            )

        # Assign the license
        assigned_license = await self._license_repo.assign_to_user(
            license_id, user_id, plan
        )

        # For lifetime plans, credit bonus (Req 6.11)
        if plan.billing_cycle_days is None and self._credit_repo is not None:
            await self._credit_repo.add_credits(
                user_id,
                LIFETIME_BONUS_CREDITS,
                "lifetime_bonus",
                ref_id=str(license_id),
            )
            logger.info(
                "Lifetime bonus credited: user_id=%s, amount=%d",
                user_id,
                LIFETIME_BONUS_CREDITS,
            )

        logger.info(
            "License assigned: license_id=%s, user_id=%s, plan=%s",
            license_id,
            user_id,
            plan.name,
        )
        return assigned_license

    async def revoke_license(self, license_id: UUID) -> License:
        """Revoke a license, deactivating the associated plan for the user.

        After revocation, the user's profile allowance should be recalculated.
        Existing profiles exceeding the new limit are preserved but no new
        profiles may be created until under the limit (Req 4.7).

        Args:
            license_id: The UUID of the license to revoke.

        Returns:
            The updated License domain object with revoked status.

        Raises:
            NotFoundError: If the license does not exist.
        """
        license = await self._license_repo.get_by_id(license_id)
        if license is None:
            raise NotFoundError(
                "License not found.",
                details={"license_id": str(license_id)},
            )

        revoked = await self._license_repo.revoke(license_id)
        if not revoked:
            raise NotFoundError(
                "License not found or already revoked.",
                details={"license_id": str(license_id)},
            )

        # Re-fetch to get updated state
        updated_license = await self._license_repo.get_by_id(license_id)
        if updated_license is None:
            raise NotFoundError(
                "License not found after revocation.",
                details={"license_id": str(license_id)},
            )

        logger.info(
            "License revoked: license_id=%s, user_id=%s",
            license_id,
            license.user_id,
        )
        return updated_license

    async def validate_license(self, user_id: UUID) -> dict[str, Any]:
        """Validate a user's license and return active plan details.

        Returns the active plan details including plan type, profile allowance,
        monthly song quota, songs remaining, credit wallet balance, and
        expiration date (Req 4.5).

        Args:
            user_id: The UUID of the user to validate.

        Returns:
            A dict with active plan details:
            - plan_type: str
            - profile_allowance: int
            - monthly_song_quota: int | None
            - songs_remaining: int | None
            - daily_song_limit_per_channel: int
            - expiration_date: str | None (ISO 8601)
            - license_status: str

        Raises:
            NotFoundError: If the user has no active license.
            LicenseExpiredError: If the license has expired (Req 4.8).
        """
        license = await self._license_repo.get_active_for_user(user_id)
        if license is None:
            raise NotFoundError(
                "No active license found for user.",
                details={"user_id": str(user_id)},
            )

        # Check expiration (Req 4.8)
        if license.expires_at is not None:
            now = datetime.now(timezone.utc)
            if license.expires_at <= now:
                raise LicenseExpiredError(
                    "Your license has expired. Please renew to continue.",
                    details={
                        "license_id": str(license.id),
                        "expired_at": license.expires_at.isoformat(),
                    },
                )

        # Fetch the plan
        plan = await self._plan_repo.get_by_id(license.plan_id)
        if plan is None:
            raise NotFoundError(
                "Plan not found for active license.",
                details={
                    "license_id": str(license.id),
                    "plan_id": str(license.plan_id),
                },
            )

        # Calculate songs remaining for monthly/yearly plans
        songs_remaining: int | None = None
        if plan.monthly_song_quota is not None:
            current_usage = await self._plan_repo.get_current_usage(
                user_id, license.id
            )
            songs_remaining = max(0, plan.monthly_song_quota - current_usage)

        # Format expiration date
        expiration_date: str | None = None
        if license.expires_at is not None:
            expiration_date = license.expires_at.isoformat()

        return {
            "plan_type": plan.name,
            "profile_allowance": plan.profile_allowance,
            "monthly_song_quota": plan.monthly_song_quota,
            "songs_remaining": songs_remaining,
            "daily_song_limit_per_channel": plan.daily_song_limit_per_channel,
            "expiration_date": expiration_date,
            "license_status": license.status.value,
        }

    # -----------------------------------------------------------------------
    # Quota Enforcement
    # -----------------------------------------------------------------------

    async def check_daily_quota(
        self, user_id: UUID, channel_count: int
    ) -> None:
        """Check that daily song generation quota per channel is not exceeded.

        Enforces the plan's daily_song_limit_per_channel limit (Req 4.6).
        Default is 7 songs/day/channel.

        Args:
            user_id: The UUID of the user.
            channel_count: The number of active channels for the user.

        Raises:
            NotFoundError: If user has no active license.
            LicenseExpiredError: If the license has expired.
            QuotaExceededError: If daily limit per channel is exceeded.
        """
        license = await self._license_repo.get_active_for_user(user_id)
        if license is None:
            raise NotFoundError(
                "No active license found for user.",
                details={"user_id": str(user_id)},
            )

        # Check expiration
        if license.expires_at is not None:
            now = datetime.now(timezone.utc)
            if license.expires_at <= now:
                raise LicenseExpiredError(
                    "Your license has expired. Please renew to continue.",
                    details={
                        "license_id": str(license.id),
                        "expired_at": license.expires_at.isoformat(),
                    },
                )

        # Fetch the plan for limits
        plan = await self._plan_repo.get_by_id(license.plan_id)
        if plan is None:
            raise NotFoundError(
                "Plan not found for license.",
                details={"plan_id": str(license.plan_id)},
            )

        daily_limit = plan.daily_song_limit_per_channel
        if daily_limit <= 0:
            # No daily limit configured
            return

        # Calculate max daily songs allowed: limit * channel_count
        # A user with 2 channels and a limit of 7 can generate 14 songs/day total
        max_daily_songs = daily_limit * max(channel_count, 1)

        # Get today's usage
        today = date.today()
        current_daily_usage = 0
        if self._daily_usage_repo is not None:
            current_daily_usage = await self._daily_usage_repo.get_daily_song_count(
                user_id, today
            )
        else:
            # Fallback: use plan usage repo for current period
            current_daily_usage = await self._plan_repo.get_current_usage(
                user_id, license.id
            )

        if current_daily_usage >= max_daily_songs:
            # Calculate reset time (next day midnight UTC)
            now = datetime.now(timezone.utc)
            tomorrow = datetime(
                now.year, now.month, now.day, tzinfo=timezone.utc
            ) + timedelta(days=1)
            reset_seconds = int((tomorrow - now).total_seconds())

            raise QuotaExceededError(
                "Daily song generation quota exceeded.",
                details={
                    "limit": max_daily_songs,
                    "limit_per_channel": daily_limit,
                    "channel_count": channel_count,
                    "current_usage": current_daily_usage,
                    "reset_time": tomorrow.isoformat(),
                    "reset_seconds": reset_seconds,
                },
            )

    async def check_monthly_quota(self, user_id: UUID) -> None:
        """Check that monthly song generation quota is not exceeded.

        Enforces the plan's monthly_song_quota limit (Req 4.6).
        Lifetime plans have no monthly quota (unlimited with wallet credits).

        Args:
            user_id: The UUID of the user.

        Raises:
            NotFoundError: If user has no active license.
            LicenseExpiredError: If the license has expired.
            QuotaExceededError: If monthly quota is exceeded.
        """
        license = await self._license_repo.get_active_for_user(user_id)
        if license is None:
            raise NotFoundError(
                "No active license found for user.",
                details={"user_id": str(user_id)},
            )

        # Check expiration
        if license.expires_at is not None:
            now = datetime.now(timezone.utc)
            if license.expires_at <= now:
                raise LicenseExpiredError(
                    "Your license has expired. Please renew to continue.",
                    details={
                        "license_id": str(license.id),
                        "expired_at": license.expires_at.isoformat(),
                    },
                )

        # Fetch the plan
        plan = await self._plan_repo.get_by_id(license.plan_id)
        if plan is None:
            raise NotFoundError(
                "Plan not found for license.",
                details={"plan_id": str(license.plan_id)},
            )

        # Lifetime plans have no monthly quota
        if plan.monthly_song_quota is None:
            return

        # Get current period usage
        current_usage = await self._plan_repo.get_current_usage(
            user_id, license.id
        )

        if current_usage >= plan.monthly_song_quota:
            # Calculate reset time based on billing period
            now = datetime.now(timezone.utc)
            if license.activated_at is not None and plan.billing_cycle_days:
                # Find the current billing period end
                days_since_activation = (now - license.activated_at).days
                periods_elapsed = days_since_activation // plan.billing_cycle_days
                period_end = license.activated_at + timedelta(
                    days=(periods_elapsed + 1) * plan.billing_cycle_days
                )
                reset_time = period_end.isoformat()
                reset_seconds = int((period_end - now).total_seconds())
            else:
                # Fallback: end of current month
                if now.month == 12:
                    next_month = datetime(
                        now.year + 1, 1, 1, tzinfo=timezone.utc
                    )
                else:
                    next_month = datetime(
                        now.year, now.month + 1, 1, tzinfo=timezone.utc
                    )
                reset_time = next_month.isoformat()
                reset_seconds = int((next_month - now).total_seconds())

            raise QuotaExceededError(
                "Monthly song generation quota exceeded.",
                details={
                    "limit": plan.monthly_song_quota,
                    "current_usage": current_usage,
                    "reset_time": reset_time,
                    "reset_seconds": reset_seconds,
                },
            )

    # -----------------------------------------------------------------------
    # Plan Offers (Promotional Pricing)
    # -----------------------------------------------------------------------

    async def get_plan_offers(self, plan_id: UUID) -> list[dict[str, Any]]:
        """Get active promotional offers for a plan.

        Returns all currently active offers with their pricing, redemption
        status, and remaining slots (Req 4.10).

        Args:
            plan_id: The UUID of the plan to get offers for.

        Returns:
            List of offer dicts with keys: id, plan_id, promo_price_cents,
            max_redemptions, current_redemptions, remaining, is_active.

        Raises:
            NotFoundError: If the plan does not exist.
        """
        plan = await self._plan_repo.get_by_id(plan_id)
        if plan is None:
            raise NotFoundError(
                "Plan not found.",
                details={"plan_id": str(plan_id)},
            )

        if self._offer_repo is None:
            return []

        offers = await self._offer_repo.get_active_offers_for_plan(plan_id)
        result: list[dict[str, Any]] = []
        for offer in offers:
            remaining = offer["max_redemptions"] - offer["current_redemptions"]
            result.append(
                {
                    "id": offer["id"],
                    "plan_id": offer["plan_id"],
                    "promo_price_cents": offer["promo_price_cents"],
                    "max_redemptions": offer["max_redemptions"],
                    "current_redemptions": offer["current_redemptions"],
                    "remaining": max(0, remaining),
                    "is_active": offer["is_active"],
                }
            )
        return result

    async def redeem_offer(self, offer_id: UUID) -> bool:
        """Redeem a promotional offer, incrementing the redemption count.

        When the max redemption count is reached, the offer is automatically
        deactivated and reverts to standard pricing (Req 4.10).

        Args:
            offer_id: The UUID of the offer to redeem.

        Returns:
            True if the offer was successfully redeemed.

        Raises:
            NotFoundError: If the offer does not exist.
            ValidationError: If the offer is inactive or fully redeemed.
        """
        if self._offer_repo is None:
            raise NotFoundError(
                "Offer management not available.",
                details={"offer_id": str(offer_id)},
            )

        offer = await self._offer_repo.get_offer_by_id(offer_id)
        if offer is None:
            raise NotFoundError(
                "Offer not found.",
                details={"offer_id": str(offer_id)},
            )

        if not offer["is_active"]:
            raise ValidationError(
                "Offer is no longer active.",
                details={"offer_id": str(offer_id)},
            )

        if offer["current_redemptions"] >= offer["max_redemptions"]:
            raise ValidationError(
                "Offer has reached maximum redemptions.",
                details={
                    "offer_id": str(offer_id),
                    "max_redemptions": offer["max_redemptions"],
                    "current_redemptions": offer["current_redemptions"],
                },
            )

        # Increment redemption count
        updated_offer = await self._offer_repo.increment_redemption(offer_id)
        if updated_offer is None:
            raise NotFoundError(
                "Offer not found during redemption.",
                details={"offer_id": str(offer_id)},
            )

        # Auto-deactivate when max reached (Req 4.10)
        if updated_offer["current_redemptions"] >= updated_offer["max_redemptions"]:
            await self._offer_repo.deactivate_offer(offer_id)
            logger.info(
                "Offer auto-deactivated (max redemptions reached): offer_id=%s",
                offer_id,
            )

        logger.info(
            "Offer redeemed: offer_id=%s, redemptions=%d/%d",
            offer_id,
            updated_offer["current_redemptions"],
            updated_offer["max_redemptions"],
        )
        return True
