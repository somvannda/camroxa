"""Credit service implementing CreditServicePort.

Manages credit wallet operations including balance queries, atomic deductions,
refunds, credit pack purchases, quota consumption order, admin adjustments,
and lifetime bonus crediting.

Requirements: 6.1, 6.2, 6.3, 6.6, 6.7, 6.10, 6.11, 6.12, 6.13
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any, Protocol
from uuid import UUID

from platform_api.exceptions import (
    InsufficientCreditsError,
    NotFoundError,
    ValidationError,
)
from platform_api.models.domain import License, Plan
from platform_api.models.enums import LicenseStatus, PlanType

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_WALLET_BALANCE = 10_000_000
LIFETIME_BONUS_CREDITS = 1_000


# ---------------------------------------------------------------------------
# Repository Protocols (dependencies)
# ---------------------------------------------------------------------------


class CreditRepository(Protocol):
    """Minimal protocol for credit wallet repository operations."""

    async def get_balance(self, user_id: UUID | str) -> int:
        """Return current wallet balance for a user."""
        ...

    async def atomic_deduct(
        self,
        user_id: UUID,
        amount: int,
        reason: str,
        ref_id: str | None = None,
    ) -> bool:
        """Atomically deduct credits. Returns True on success."""
        ...

    async def add_credits(
        self,
        user_id: UUID,
        amount: int,
        reason: str,
        ref_id: str | None = None,
        pack_id: UUID | None = None,
        payment_ref: str | None = None,
    ) -> int:
        """Add credits and return new balance."""
        ...

    async def refund(
        self,
        user_id: UUID,
        amount: int,
        reason: str,
        ref_id: str | None = None,
    ) -> int:
        """Refund credits and return new balance."""
        ...


class LicenseRepository(Protocol):
    """Minimal protocol for license repository operations needed by credit service."""

    async def get_active_for_user(self, user_id: UUID) -> License | None:
        """Return the active non-expired license for a user, or None."""
        ...


class PlanRepository(Protocol):
    """Minimal protocol for plan repository operations needed by credit service."""

    async def get_by_id(self, plan_id: UUID) -> Plan | None:
        """Return the plan with the given ID, or None."""
        ...

    async def get_or_create_usage(
        self,
        user_id: UUID,
        license_id: UUID,
        period_start: date,
        period_end: date,
    ) -> dict[str, Any]:
        """Get or create a plan usage record for the given period."""
        ...

    async def increment_usage(
        self, user_id: UUID, license_id: UUID, period_start: date
    ) -> int:
        """Increment songs_used for the current period. Returns new count."""
        ...

    async def get_current_usage(self, user_id: UUID, license_id: UUID) -> int:
        """Get the songs_used count for the current billing period."""
        ...


class CreditPackRepository(Protocol):
    """Minimal protocol for credit pack lookups."""

    async def get_by_id(self, pack_id: UUID) -> dict[str, Any] | None:
        """Return the pack record or None. Expected keys: id, name, song_credits, is_active."""
        ...


# ---------------------------------------------------------------------------
# Credit Service
# ---------------------------------------------------------------------------


class CreditService:
    """Credit wallet management service.

    Implements CreditServicePort with quota consumption order:
    - Monthly/Yearly users consume plan quota first, then wallet.
    - Lifetime users always deduct from wallet.

    Constructor Parameters:
        credit_repo: Repository for wallet balance and transaction operations.
        license_repo: Repository for looking up active licenses.
        plan_repo: Repository for plan details and usage tracking.
        pack_repo: Optional repository for credit pack lookups.
    """

    def __init__(
        self,
        credit_repo: CreditRepository,
        license_repo: LicenseRepository,
        plan_repo: PlanRepository,
        pack_repo: CreditPackRepository | None = None,
    ) -> None:
        self._credit_repo = credit_repo
        self._license_repo = license_repo
        self._plan_repo = plan_repo
        self._pack_repo = pack_repo

    # ------------------------------------------------------------------
    # CreditServicePort Implementation
    # ------------------------------------------------------------------

    async def get_balance(self, user_id: str) -> int:
        """Return the current credit wallet balance for a user.

        Args:
            user_id: The string UUID of the user.

        Returns:
            A non-negative integer representing available credits.
        """
        return await self._credit_repo.get_balance(UUID(user_id))

    async def deduct(self, user_id: str, amount: int, reason: str, ref_id: str) -> bool:
        """Atomically deduct credits from a user's wallet.

        Args:
            user_id: The string UUID of the user.
            amount: The number of credits to deduct (must be positive).
            reason: Description of the deduction reason.
            ref_id: Reference identifier for the operation.

        Returns:
            True if the deduction succeeded (sufficient balance).
            False if the balance is insufficient (no partial deduction).
        """
        if amount <= 0:
            raise ValidationError(
                "Deduction amount must be a positive integer.",
                details={"amount": amount},
            )
        return await self._credit_repo.atomic_deduct(
            user_id=UUID(user_id),
            amount=amount,
            reason=reason,
            ref_id=ref_id,
        )

    async def refund(self, user_id: str, amount: int, reason: str, ref_id: str) -> None:
        """Refund credits to a user's wallet.

        Used when an external service call fails after credits were deducted.
        Records a refund transaction for audit purposes.

        Args:
            user_id: The string UUID of the user.
            amount: The number of credits to refund (must be positive).
            reason: Description of the refund reason.
            ref_id: Reference identifier for the failed operation.

        Raises:
            ValidationError: If amount is not positive.
        """
        if amount <= 0:
            raise ValidationError(
                "Refund amount must be a positive integer.",
                details={"amount": amount},
            )
        await self._credit_repo.refund(
            user_id=UUID(user_id),
            amount=amount,
            reason=reason,
            ref_id=ref_id,
        )
        logger.info(
            "Refunded %d credits to user %s (reason=%s, ref=%s)",
            amount,
            user_id,
            reason,
            ref_id,
        )

    async def purchase_pack(
        self, user_id: str, pack_id: str, payment_ref: str
    ) -> int:
        """Purchase a credit pack and add credits to the user's wallet.

        Validates that the pack exists and is active, then adds the pack's
        song credits to the wallet. Records the transaction with payment ref.

        Args:
            user_id: The string UUID of the user.
            pack_id: The string UUID of the credit pack to purchase.
            payment_ref: Payment reference from payment processor.

        Returns:
            The new wallet balance after the purchase.

        Raises:
            NotFoundError: If the pack does not exist or is inactive.
            InsufficientCreditsError: If the purchase would exceed the
                maximum wallet balance (10,000,000 credits).
            ValidationError: If pack_repo is not configured.
        """
        if self._pack_repo is None:
            raise ValidationError(
                "Credit pack repository is not configured.",
                details={"pack_id": pack_id},
            )

        pack_uuid = UUID(pack_id)
        user_uuid = UUID(user_id)

        # Validate pack exists and is active
        pack = await self._pack_repo.get_by_id(pack_uuid)
        if pack is None:
            raise NotFoundError(
                f"Credit pack '{pack_id}' not found.",
                details={"pack_id": pack_id},
            )
        if not pack.get("is_active", False):
            raise NotFoundError(
                f"Credit pack '{pack_id}' is no longer available.",
                details={"pack_id": pack_id},
            )

        credits_to_add = pack["song_credits"]

        # Check overflow before adding
        current_balance = await self._credit_repo.get_balance(user_uuid)
        if current_balance + credits_to_add > MAX_WALLET_BALANCE:
            raise InsufficientCreditsError(
                f"Purchasing this pack would exceed the maximum wallet balance "
                f"of {MAX_WALLET_BALANCE:,}. Current balance: {current_balance:,}, "
                f"pack credits: {credits_to_add:,}.",
                details={
                    "current_balance": current_balance,
                    "pack_credits": credits_to_add,
                    "max_balance": MAX_WALLET_BALANCE,
                },
            )

        # Add credits to wallet and record transaction
        new_balance = await self._credit_repo.add_credits(
            user_id=user_uuid,
            amount=credits_to_add,
            reason="credit_pack_purchase",
            ref_id=pack_id,
            pack_id=pack_uuid,
            payment_ref=payment_ref,
        )

        logger.info(
            "User %s purchased pack %s (%d credits). New balance: %d",
            user_id,
            pack_id,
            credits_to_add,
            new_balance,
        )
        return new_balance

    # ------------------------------------------------------------------
    # Quota Consumption Order (Requirement 6.12, 6.13)
    # ------------------------------------------------------------------

    async def consume_generation_credit(
        self, user_id: str, operation_cost: int
    ) -> None:
        """Consume credits following the quota consumption order.

        For Monthly/Yearly users:
            1. Check plan's monthly_song_quota. If quota remaining > 0,
               increment plan usage (no wallet deduction).
            2. If quota exhausted, fall through to wallet deduction.

        For Lifetime users:
            Always deduct from wallet.

        Args:
            user_id: The string UUID of the user.
            operation_cost: The number of credits to consume for this operation.

        Raises:
            InsufficientCreditsError: If wallet balance is insufficient after
                plan quota is exhausted (or for Lifetime users with no balance).
        """
        if operation_cost <= 0:
            raise ValidationError(
                "Operation cost must be a positive integer.",
                details={"operation_cost": operation_cost},
            )

        user_uuid = UUID(user_id)

        # Look up active license and plan
        license_record = await self._license_repo.get_active_for_user(user_uuid)

        if license_record is not None:
            plan = await self._plan_repo.get_by_id(license_record.plan_id)
        else:
            plan = None

        # Determine plan type
        plan_type = PlanType(plan.name) if plan else None

        # Monthly/Yearly users: try plan quota first
        if (
            plan_type in (PlanType.MONTHLY, PlanType.YEARLY)
            and plan is not None
            and license_record is not None
        ):
            if plan.monthly_song_quota is not None and plan.monthly_song_quota > 0:
                # Compute current billing period
                period_start, period_end = self._compute_billing_period(
                    license_record
                )

                # Ensure usage record exists
                await self._plan_repo.get_or_create_usage(
                    user_id=user_uuid,
                    license_id=license_record.id,
                    period_start=period_start,
                    period_end=period_end,
                )

                # Check current usage
                current_usage = await self._plan_repo.get_current_usage(
                    user_id=user_uuid,
                    license_id=license_record.id,
                )

                remaining_quota = plan.monthly_song_quota - current_usage

                if remaining_quota > 0:
                    # Consume from plan quota (no wallet deduction)
                    await self._plan_repo.increment_usage(
                        user_id=user_uuid,
                        license_id=license_record.id,
                        period_start=period_start,
                    )
                    logger.info(
                        "User %s consumed 1 plan quota credit. "
                        "Remaining: %d/%d",
                        user_id,
                        remaining_quota - 1,
                        plan.monthly_song_quota,
                    )
                    return

        # Lifetime users OR plan quota exhausted: deduct from wallet
        success = await self._credit_repo.atomic_deduct(
            user_id=user_uuid,
            amount=operation_cost,
            reason="generation",
            ref_id=None,
        )
        if not success:
            current_balance = await self._credit_repo.get_balance(user_uuid)
            raise InsufficientCreditsError(
                f"Insufficient credits for this operation. "
                f"Required: {operation_cost}, available: {current_balance}.",
                details={
                    "required": operation_cost,
                    "available": current_balance,
                },
            )

        logger.info(
            "User %s consumed %d wallet credits for generation.",
            user_id,
            operation_cost,
        )

    # ------------------------------------------------------------------
    # Admin Adjustment (Requirement 6.7)
    # ------------------------------------------------------------------

    async def admin_adjust(self, user_id: str, amount: int, reason: str) -> int:
        """Manually adjust a user's wallet balance (Admin operation).

        Supports both positive (add credits) and negative (subtract credits)
        adjustments. Enforces bounds: resulting balance must be within
        [0, 10,000,000].

        Args:
            user_id: The string UUID of the user.
            amount: The adjustment amount (positive to add, negative to subtract).
            reason: Admin-provided reason for the adjustment.

        Returns:
            The new wallet balance after adjustment.

        Raises:
            ValidationError: If amount is zero or reason is empty.
            InsufficientCreditsError: If the adjustment would cause the balance
                to go below 0 or exceed 10,000,000.
        """
        if amount == 0:
            raise ValidationError(
                "Adjustment amount must be non-zero.",
                details={"amount": amount},
            )
        if not reason or not reason.strip():
            raise ValidationError(
                "Adjustment reason is required.",
                details={"reason": reason},
            )

        user_uuid = UUID(user_id)
        current_balance = await self._credit_repo.get_balance(user_uuid)
        new_balance = current_balance + amount

        # Enforce bounds [0, MAX_WALLET_BALANCE]
        if new_balance < 0:
            raise InsufficientCreditsError(
                f"Adjustment would cause balance to go below zero. "
                f"Current: {current_balance}, adjustment: {amount}.",
                details={
                    "current_balance": current_balance,
                    "adjustment": amount,
                    "resulting_balance": new_balance,
                },
            )
        if new_balance > MAX_WALLET_BALANCE:
            raise InsufficientCreditsError(
                f"Adjustment would exceed maximum wallet balance of "
                f"{MAX_WALLET_BALANCE:,}. Current: {current_balance:,}, "
                f"adjustment: {amount:,}.",
                details={
                    "current_balance": current_balance,
                    "adjustment": amount,
                    "max_balance": MAX_WALLET_BALANCE,
                },
            )

        # Apply the adjustment
        if amount > 0:
            new_balance = await self._credit_repo.add_credits(
                user_id=user_uuid,
                amount=amount,
                reason=f"admin_adjustment: {reason}",
            )
        else:
            # Negative adjustment — use atomic_deduct with the absolute value
            abs_amount = abs(amount)
            success = await self._credit_repo.atomic_deduct(
                user_id=user_uuid,
                amount=abs_amount,
                reason=f"admin_adjustment: {reason}",
            )
            if not success:
                raise InsufficientCreditsError(
                    f"Failed to deduct {abs_amount} credits from user {user_id}. "
                    f"Balance may have changed concurrently.",
                    details={
                        "current_balance": current_balance,
                        "adjustment": amount,
                    },
                )
            new_balance = await self._credit_repo.get_balance(user_uuid)

        logger.info(
            "Admin adjusted user %s wallet by %d credits (reason=%s). "
            "New balance: %d",
            user_id,
            amount,
            reason,
            new_balance,
        )
        return new_balance

    # ------------------------------------------------------------------
    # Lifetime Bonus (Requirement 6.11)
    # ------------------------------------------------------------------

    async def credit_lifetime_bonus(
        self, user_id: str, license_id: str
    ) -> None:
        """Credit 1,000 bonus song credits on lifetime plan activation.

        Called when a Lifetime plan license is activated for a user.
        Records the bonus as a "lifetime_bonus" transaction.

        Args:
            user_id: The string UUID of the user.
            license_id: The string UUID of the license that triggered the bonus.

        Raises:
            InsufficientCreditsError: If the bonus would exceed max wallet balance.
        """
        user_uuid = UUID(user_id)

        new_balance = await self._credit_repo.add_credits(
            user_id=user_uuid,
            amount=LIFETIME_BONUS_CREDITS,
            reason="lifetime_bonus",
            ref_id=license_id,
        )

        logger.info(
            "Credited %d lifetime bonus credits to user %s (license=%s). "
            "New balance: %d",
            LIFETIME_BONUS_CREDITS,
            user_id,
            license_id,
            new_balance,
        )

    # ------------------------------------------------------------------
    # Internal Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_billing_period(license_record: License) -> tuple[date, date]:
        """Compute the current billing period start and end dates.

        Based on the license's activated_at date and the plan's billing cycle.
        For simplicity, uses 30-day periods from activation date.

        Args:
            license_record: The active license for the user.

        Returns:
            Tuple of (period_start, period_end) as date objects.
        """
        if license_record.activated_at is None:
            # Fallback: use today as period start
            today = date.today()
            return today, today

        activation = license_record.activated_at
        if isinstance(activation, datetime):
            activation_date = activation.date()
        else:
            activation_date = activation

        today = date.today()

        # Calculate how many full periods have elapsed since activation
        days_since_activation = (today - activation_date).days
        # Default to 30-day billing period
        period_length = 30
        periods_elapsed = days_since_activation // period_length

        period_start = activation_date
        for _ in range(periods_elapsed):
            period_start = _add_days(period_start, period_length)

        period_end = _add_days(period_start, period_length - 1)

        return period_start, period_end


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------


def _add_days(d: date, days: int) -> date:
    """Add days to a date, returning a new date."""
    from datetime import timedelta

    return d + timedelta(days=days)
