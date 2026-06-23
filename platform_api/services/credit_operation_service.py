"""Centralized credit operation service for AI generation endpoints.

Provides the deduct-execute-refund pattern used by channel_setup and any other
endpoints that need simple credit-gated AI operations (no quota tracking).

For full usage enforcement with daily/monthly quotas, see UsageEnforcementService.
"""

from __future__ import annotations

import logging
from typing import Awaitable, Callable, Protocol, TypeVar
from uuid import UUID

from platform_api.exceptions import InsufficientCreditsError

logger = logging.getLogger(__name__)

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Protocol interfaces for dependency injection / testability
# ---------------------------------------------------------------------------


class CreditRepoProtocol(Protocol):
    """Subset of CreditRepository used by CreditOperationService."""

    async def get_balance(self, user_id: UUID) -> int: ...

    async def atomic_deduct(
        self,
        user_id: UUID,
        amount: int,
        reason: str,
        ref_id: str | None = None,
    ) -> bool: ...

    async def refund(
        self,
        user_id: UUID,
        amount: int,
        reason: str,
        ref_id: str | None = None,
    ) -> int: ...


class PricingServiceProtocol(Protocol):
    """Subset of CreditPricingService used by CreditOperationService."""

    async def get_price(self, ai_service: str, operation_type: str) -> int: ...


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class CreditOperationService:
    """Central credit service for all AI generation operations.

    Provides the deduct-execute-refund pattern:
    1. Resolve pricing (with optional fallback)
    2. Check balance
    3. Deduct credits
    4. Execute the operation (caller provides async callable)
    5. If operation fails → refund credits automatically
    6. Return the operation result + credits charged

    This service does NOT enforce quotas or track usage — it is intentionally
    simpler than UsageEnforcementService. Use it for onboarding and channel
    setup operations where quota tracking is not required.
    """

    def __init__(
        self,
        credit_repo: CreditRepoProtocol,
        pricing_service: PricingServiceProtocol,
    ) -> None:
        self._credit_repo = credit_repo
        self._pricing_service = pricing_service

    async def execute_with_credits(
        self,
        user_id: UUID,
        ai_service: str,
        operation_type: str,
        operation: Callable[[], Awaitable[T]],
        count: int = 1,
        fallback_operation_type: str | None = None,
    ) -> tuple[T, int]:
        """Execute an operation with credit deduction and automatic refund on failure.

        Pricing resolution:
        1. If fallback_operation_type is provided, try (ai_service, "channel_setup") first
        2. Fall back to (ai_service, operation_type)
        3. If no pricing configured at all → skip deduction (graceful degradation)

        Args:
            user_id: The user's UUID.
            ai_service: AI service identifier (e.g., "deepseek", "slai").
            operation_type: The operation type for pricing lookup
                (e.g., "text_generation", "image_generation").
            operation: Async callable that performs the actual AI operation.
            count: Number of operations (multiplier for credits).
            fallback_operation_type: If set, tries "channel_setup" first,
                falls back to this type.

        Returns:
            Tuple of (operation result, credits deducted).

        Raises:
            InsufficientCreditsError: If balance is too low.
            Any exception from the operation (credits are refunded first).
        """
        # Step 1: Resolve pricing
        credits_per_op = await self._resolve_pricing(
            ai_service, operation_type, fallback_operation_type
        )
        if credits_per_op == 0:
            # No pricing configured — execute without charging
            result = await operation()
            return result, 0

        total_credits = credits_per_op * count

        # Step 2: Check balance
        balance = await self._credit_repo.get_balance(user_id)
        if balance < total_credits:
            raise InsufficientCreditsError(
                "Insufficient credits for this operation.",
                details={
                    "required_credits": total_credits,
                    "current_balance": balance,
                },
            )

        # Step 3: Deduct
        success = await self._credit_repo.atomic_deduct(
            user_id=user_id,
            amount=total_credits,
            reason=f"{operation_type} via {ai_service}",
        )
        if not success:
            current = await self._credit_repo.get_balance(user_id)
            raise InsufficientCreditsError(
                "Insufficient credits (concurrent deduction).",
                details={
                    "required_credits": total_credits,
                    "current_balance": current,
                },
            )

        logger.info(
            "Deducted %d credits for %s via %s (user=%s)",
            total_credits,
            operation_type,
            ai_service,
            user_id,
        )

        # Step 4: Execute operation
        try:
            result = await operation()
            return result, total_credits
        except Exception:
            # Step 5: Refund on failure
            await self._safe_refund(
                user_id=user_id,
                amount=total_credits,
                reason=f"{operation_type}_failed",
            )
            raise

    async def _resolve_pricing(
        self,
        ai_service: str,
        operation_type: str,
        fallback_operation_type: str | None,
    ) -> int:
        """Resolve credits_per_operation with optional channel_setup fallback.

        Returns 0 if no pricing is configured (graceful degradation).
        """
        # Try channel_setup pricing first if fallback is specified
        if fallback_operation_type:
            try:
                return await self._pricing_service.get_price(ai_service, "channel_setup")
            except Exception:
                pass

        # Try the standard operation type
        try:
            return await self._pricing_service.get_price(ai_service, operation_type)
        except Exception:
            # No pricing configured — graceful degradation
            logger.warning(
                "No credit pricing configured for ai_service=%s, operation=%s. "
                "Skipping deduction.",
                ai_service,
                operation_type,
            )
            return 0

    async def _safe_refund(
        self, user_id: UUID, amount: int, reason: str
    ) -> None:
        """Attempt a refund, swallowing errors to avoid masking the original exception."""
        if amount <= 0:
            return
        try:
            await self._credit_repo.refund(
                user_id=user_id,
                amount=amount,
                reason=f"refund:{reason}",
            )
            logger.info(
                "Refunded %d credits to user %s (reason=%s)",
                amount,
                user_id,
                reason,
            )
        except Exception as refund_exc:
            logger.error(
                "Failed to refund %d credits to user %s: %s",
                amount,
                user_id,
                refund_exc,
            )
