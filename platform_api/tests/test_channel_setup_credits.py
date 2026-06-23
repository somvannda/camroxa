"""Tests for credit operation logic used by channel_setup router.

Validates Requirements 5.1–5.6 via the centralized CreditOperationService:
- Pricing resolution with channel_setup fallback
- Credit balance check before deduction
- 402 InsufficientCreditsError when balance is too low
- Graceful degradation when no pricing is configured
- Per-cover deduction for covers endpoint (count multiplier)
- Automatic refund on operation failure
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock
from uuid import uuid4

from platform_api.exceptions import ExternalServiceError, InsufficientCreditsError
from platform_api.services.credit_operation_service import CreditOperationService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def user_id():
    return uuid4()


@pytest.fixture
def mock_pricing_service():
    return AsyncMock()


@pytest.fixture
def mock_credit_repo():
    return AsyncMock()


@pytest.fixture
def credit_svc(mock_credit_repo, mock_pricing_service):
    return CreditOperationService(
        credit_repo=mock_credit_repo,
        pricing_service=mock_pricing_service,
    )


# ---------------------------------------------------------------------------
# Tests: Pricing Resolution (Requirement 5.5)
# ---------------------------------------------------------------------------


class TestPricingResolution:
    """Test pricing resolution with channel_setup → standard fallback."""

    @pytest.mark.asyncio
    async def test_uses_channel_setup_pricing_when_available(
        self, user_id, mock_pricing_service, mock_credit_repo, credit_svc
    ):
        """If channel_setup pricing exists, use it."""
        mock_pricing_service.get_price = AsyncMock(return_value=5)
        mock_credit_repo.get_balance = AsyncMock(return_value=100)
        mock_credit_repo.atomic_deduct = AsyncMock(return_value=True)

        operation = AsyncMock(return_value="result")

        result, credits = await credit_svc.execute_with_credits(
            user_id=user_id,
            ai_service="deepseek",
            operation_type="text_generation",
            operation=operation,
            fallback_operation_type="text_generation",
        )

        assert result == "result"
        assert credits == 5
        mock_pricing_service.get_price.assert_called_once_with("deepseek", "channel_setup")
        mock_credit_repo.atomic_deduct.assert_called_once_with(
            user_id=user_id, amount=5, reason="text_generation via deepseek"
        )

    @pytest.mark.asyncio
    async def test_falls_back_to_standard_pricing(
        self, user_id, mock_pricing_service, mock_credit_repo, credit_svc
    ):
        """If channel_setup pricing raises, fall back to standard operation type."""

        async def mock_get_price(ai_service, op_type):
            if op_type == "channel_setup":
                raise ExternalServiceError("No pricing configured")
            return 10

        mock_pricing_service.get_price = AsyncMock(side_effect=mock_get_price)
        mock_credit_repo.get_balance = AsyncMock(return_value=100)
        mock_credit_repo.atomic_deduct = AsyncMock(return_value=True)

        operation = AsyncMock(return_value="result")

        result, credits = await credit_svc.execute_with_credits(
            user_id=user_id,
            ai_service="slai",
            operation_type="image_generation",
            operation=operation,
            fallback_operation_type="image_generation",
        )

        assert result == "result"
        assert credits == 10
        assert mock_pricing_service.get_price.call_count == 2
        mock_credit_repo.atomic_deduct.assert_called_once_with(
            user_id=user_id, amount=10, reason="image_generation via slai"
        )

    @pytest.mark.asyncio
    async def test_graceful_degradation_no_pricing(
        self, user_id, mock_pricing_service, mock_credit_repo, credit_svc
    ):
        """If no pricing is configured at all, skip deduction and execute."""
        mock_pricing_service.get_price = AsyncMock(
            side_effect=ExternalServiceError("No pricing configured")
        )

        operation = AsyncMock(return_value="free_result")

        result, credits = await credit_svc.execute_with_credits(
            user_id=user_id,
            ai_service="deepseek",
            operation_type="text_generation",
            operation=operation,
            fallback_operation_type="text_generation",
        )

        assert result == "free_result"
        assert credits == 0
        mock_credit_repo.get_balance.assert_not_called()
        mock_credit_repo.atomic_deduct.assert_not_called()
        operation.assert_called_once()


# ---------------------------------------------------------------------------
# Tests: Credit Deduction (Requirements 5.1–5.4)
# ---------------------------------------------------------------------------


class TestCreditDeduction:
    """Test credit balance check and deduction."""

    @pytest.mark.asyncio
    async def test_insufficient_credits_raises_402(
        self, user_id, mock_pricing_service, mock_credit_repo, credit_svc
    ):
        """Raises InsufficientCreditsError when balance < required credits."""
        mock_pricing_service.get_price = AsyncMock(return_value=20)
        mock_credit_repo.get_balance = AsyncMock(return_value=10)

        operation = AsyncMock()

        with pytest.raises(InsufficientCreditsError) as exc_info:
            await credit_svc.execute_with_credits(
                user_id=user_id,
                ai_service="deepseek",
                operation_type="text_generation",
                operation=operation,
            )

        assert exc_info.value.status_code == 402
        assert exc_info.value.details["required_credits"] == 20
        assert exc_info.value.details["current_balance"] == 10
        operation.assert_not_called()

    @pytest.mark.asyncio
    async def test_covers_deduct_per_count(
        self, user_id, mock_pricing_service, mock_credit_repo, credit_svc
    ):
        """For covers, credits = credits_per_operation × count."""
        mock_pricing_service.get_price = AsyncMock(return_value=8)
        mock_credit_repo.get_balance = AsyncMock(return_value=100)
        mock_credit_repo.atomic_deduct = AsyncMock(return_value=True)

        operation = AsyncMock(return_value=["img1", "img2", "img3"])

        result, credits = await credit_svc.execute_with_credits(
            user_id=user_id,
            ai_service="slai",
            operation_type="image_generation",
            operation=operation,
            count=3,
        )

        assert credits == 24  # 8 credits × 3 covers
        assert result == ["img1", "img2", "img3"]
        mock_credit_repo.atomic_deduct.assert_called_once_with(
            user_id=user_id, amount=24, reason="image_generation via slai"
        )

    @pytest.mark.asyncio
    async def test_race_condition_atomic_deduct_fails(
        self, user_id, mock_pricing_service, mock_credit_repo, credit_svc
    ):
        """If atomic_deduct returns False (race condition), raise 402."""
        mock_pricing_service.get_price = AsyncMock(return_value=10)
        mock_credit_repo.get_balance = AsyncMock(return_value=15)
        mock_credit_repo.atomic_deduct = AsyncMock(return_value=False)

        operation = AsyncMock()

        with pytest.raises(InsufficientCreditsError) as exc_info:
            await credit_svc.execute_with_credits(
                user_id=user_id,
                ai_service="deepseek",
                operation_type="text_generation",
                operation=operation,
            )

        assert exc_info.value.status_code == 402
        operation.assert_not_called()

    @pytest.mark.asyncio
    async def test_successful_single_deduction(
        self, user_id, mock_pricing_service, mock_credit_repo, credit_svc
    ):
        """Successful deduction returns total credits deducted."""
        mock_pricing_service.get_price = AsyncMock(return_value=15)
        mock_credit_repo.get_balance = AsyncMock(return_value=50)
        mock_credit_repo.atomic_deduct = AsyncMock(return_value=True)

        operation = AsyncMock(return_value="generated")

        result, credits = await credit_svc.execute_with_credits(
            user_id=user_id,
            ai_service="slai",
            operation_type="image_generation",
            operation=operation,
        )

        assert result == "generated"
        assert credits == 15


# ---------------------------------------------------------------------------
# Tests: Automatic Refund on Failure
# ---------------------------------------------------------------------------


class TestRefundOnFailure:
    """Test that credits are refunded when the operation fails."""

    @pytest.mark.asyncio
    async def test_refund_on_operation_failure(
        self, user_id, mock_pricing_service, mock_credit_repo, credit_svc
    ):
        """If operation raises, credits are refunded and exception re-raised."""
        mock_pricing_service.get_price = AsyncMock(return_value=10)
        mock_credit_repo.get_balance = AsyncMock(return_value=50)
        mock_credit_repo.atomic_deduct = AsyncMock(return_value=True)
        mock_credit_repo.refund = AsyncMock(return_value=50)

        operation = AsyncMock(side_effect=RuntimeError("AI service down"))

        with pytest.raises(RuntimeError, match="AI service down"):
            await credit_svc.execute_with_credits(
                user_id=user_id,
                ai_service="deepseek",
                operation_type="text_generation",
                operation=operation,
            )

        mock_credit_repo.refund.assert_called_once_with(
            user_id=user_id,
            amount=10,
            reason="refund:text_generation_failed",
        )

    @pytest.mark.asyncio
    async def test_refund_failure_does_not_mask_original_error(
        self, user_id, mock_pricing_service, mock_credit_repo, credit_svc
    ):
        """If refund itself fails, the original operation error is still raised."""
        mock_pricing_service.get_price = AsyncMock(return_value=10)
        mock_credit_repo.get_balance = AsyncMock(return_value=50)
        mock_credit_repo.atomic_deduct = AsyncMock(return_value=True)
        mock_credit_repo.refund = AsyncMock(side_effect=Exception("DB connection lost"))

        operation = AsyncMock(side_effect=RuntimeError("AI service down"))

        with pytest.raises(RuntimeError, match="AI service down"):
            await credit_svc.execute_with_credits(
                user_id=user_id,
                ai_service="deepseek",
                operation_type="text_generation",
                operation=operation,
            )

    @pytest.mark.asyncio
    async def test_no_refund_when_no_pricing(
        self, user_id, mock_pricing_service, mock_credit_repo, credit_svc
    ):
        """If pricing is 0 (graceful degradation), no refund on failure."""
        mock_pricing_service.get_price = AsyncMock(
            side_effect=ExternalServiceError("No pricing configured")
        )

        operation = AsyncMock(side_effect=RuntimeError("AI error"))

        with pytest.raises(RuntimeError, match="AI error"):
            await credit_svc.execute_with_credits(
                user_id=user_id,
                ai_service="deepseek",
                operation_type="text_generation",
                operation=operation,
                fallback_operation_type="text_generation",
            )

        mock_credit_repo.refund.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_fallback_uses_operation_type_directly(
        self, user_id, mock_pricing_service, mock_credit_repo, credit_svc
    ):
        """Without fallback_operation_type, goes directly to operation_type."""
        mock_pricing_service.get_price = AsyncMock(return_value=7)
        mock_credit_repo.get_balance = AsyncMock(return_value=100)
        mock_credit_repo.atomic_deduct = AsyncMock(return_value=True)

        operation = AsyncMock(return_value="done")

        result, credits = await credit_svc.execute_with_credits(
            user_id=user_id,
            ai_service="deepseek",
            operation_type="text_generation",
            operation=operation,
        )

        assert credits == 7
        mock_pricing_service.get_price.assert_called_once_with("deepseek", "text_generation")
