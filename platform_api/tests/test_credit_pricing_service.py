"""Unit tests for CreditPricingService.

Tests pricing CRUD operations, validation, margin computation,
and rejection of unconfigured service operations.

Requirements: 5.1, 5.2, 5.4, 5.5, 5.6, 5.7
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import pytest

from platform_api.exceptions import (
    DuplicateError,
    ExternalServiceError,
    NotFoundError,
    ValidationError,
)
from platform_api.services.credit_pricing_service import CreditPricingService
from platform_api.services.credit_units import CREDIT_SCALE, MAX_CREDIT_UNITS


def cr(display: int | float) -> int:
    """Convert display credits to micro-units for tests."""
    return int(display * CREDIT_SCALE)


# ---------------------------------------------------------------------------
# Fake CreditPricingRepository
# ---------------------------------------------------------------------------


class FakeCreditPricingRepo:
    """In-memory fake implementing CreditPricingRepositoryProtocol."""

    def __init__(self) -> None:
        self._entries: dict[tuple[str, str, str], dict[str, Any]] = {}

    def seed(
        self,
        ai_service: str,
        operation_type: str,
        credits_per_operation: int,
        external_cost_cents: int | None = None,
        *,
        sub_model: str = "",
    ) -> None:
        """Seed an entry for testing."""
        key = (ai_service, operation_type, sub_model)
        now = datetime.now(timezone.utc)
        self._entries[key] = {
            "id": uuid4(),
            "ai_service": ai_service,
            "operation_type": operation_type,
            "sub_model": sub_model,
            "credits_per_operation": credits_per_operation,
            "external_cost_cents": external_cost_cents,
            "needs_review": False,
            "created_at": now,
            "updated_at": now,
        }

    async def get_all(self) -> list[dict[str, Any]]:
        return list(self._entries.values())

    async def get_by_service_and_operation(
        self,
        ai_service: str,
        operation_type: str,
        sub_model: str = "",
    ) -> dict[str, Any] | None:
        return self._entries.get((ai_service, operation_type, sub_model))

    async def create(
        self,
        ai_service: str,
        operation_type: str,
        credits_per_operation: int,
        external_cost_cents: int | None,
        *,
        sub_model: str = "",
        needs_review: bool = False,
    ) -> dict[str, Any]:
        key = (ai_service, operation_type, sub_model)
        now = datetime.now(timezone.utc)
        entry = {
            "id": uuid4(),
            "ai_service": ai_service,
            "operation_type": operation_type,
            "sub_model": sub_model,
            "credits_per_operation": credits_per_operation,
            "external_cost_cents": external_cost_cents,
            "needs_review": needs_review,
            "created_at": now,
            "updated_at": now,
        }
        self._entries[key] = entry
        return entry

    async def update(
        self,
        ai_service: str,
        operation_type: str,
        credits_per_operation: int,
        external_cost_cents: int | None,
        *,
        sub_model: str = "",
    ) -> dict[str, Any] | None:
        key = (ai_service, operation_type, sub_model)
        if key not in self._entries:
            return None
        self._entries[key]["credits_per_operation"] = credits_per_operation
        self._entries[key]["external_cost_cents"] = external_cost_cents
        self._entries[key]["updated_at"] = datetime.now(timezone.utc)
        return self._entries[key]

    async def delete(
        self,
        ai_service: str,
        operation_type: str,
        *,
        sub_model: str = "",
    ) -> bool:
        key = (ai_service, operation_type, sub_model)
        if key in self._entries:
            del self._entries[key]
            return True
        return False

    async def delete_all(self, *, ai_service: str | None = None) -> int:
        if ai_service:
            keys = [k for k in self._entries if k[0] == ai_service]
        else:
            keys = list(self._entries.keys())
        for key in keys:
            del self._entries[key]
        return len(keys)

    async def approve(
        self,
        ai_service: str,
        operation_type: str,
        *,
        sub_model: str = "",
    ) -> dict[str, Any] | None:
        key = (ai_service, operation_type, sub_model)
        if key not in self._entries:
            return None
        self._entries[key]["needs_review"] = False
        return self._entries[key]

    async def approve_many(self, pairs: list[tuple[str, str, str]]) -> int:
        count = 0
        for ai_service, operation_type, sub_model in pairs:
            if await self.approve(ai_service, operation_type, sub_model=sub_model):
                count += 1
        return count


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def repo() -> FakeCreditPricingRepo:
    return FakeCreditPricingRepo()


@pytest.fixture
def service(repo: FakeCreditPricingRepo) -> CreditPricingService:
    return CreditPricingService(pricing_repo=repo)


# ---------------------------------------------------------------------------
# Tests: get_all_pricing
# ---------------------------------------------------------------------------


class TestGetAllPricing:
    """Tests for get_all_pricing method."""

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_entries(
        self, service: CreditPricingService
    ) -> None:
        result = await service.get_all_pricing()
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_all_entries_with_margin(
        self, service: CreditPricingService, repo: FakeCreditPricingRepo
    ) -> None:
        repo.seed("suno", "music_generation", cr(14), cr(8))
        repo.seed("fal", "image_generation", cr(5), cr(2))

        result = await service.get_all_pricing()
        assert len(result) == 2

        suno_entry = next(e for e in result if e["ai_service"] == "suno")
        assert suno_entry["margin"] == 6.0

        fal_entry = next(e for e in result if e["ai_service"] == "fal")
        assert fal_entry["margin"] == 3.0

    @pytest.mark.asyncio
    async def test_margin_is_none_when_no_external_cost(
        self, service: CreditPricingService, repo: FakeCreditPricingRepo
    ) -> None:
        repo.seed("deepseek", "text_generation", cr(3), None)

        result = await service.get_all_pricing()
        assert len(result) == 1
        assert result[0]["margin"] is None


# ---------------------------------------------------------------------------
# Tests: get_price
# ---------------------------------------------------------------------------


class TestGetPrice:
    """Tests for get_price method (Req 5.6)."""

    @pytest.mark.asyncio
    async def test_returns_credits_per_operation(
        self, service: CreditPricingService, repo: FakeCreditPricingRepo
    ) -> None:
        repo.seed("suno", "music_generation", cr(14), cr(8))
        price = await service.get_price("suno", "music_generation")
        assert price == cr(14)

    @pytest.mark.asyncio
    async def test_raises_external_service_error_when_not_configured(
        self, service: CreditPricingService
    ) -> None:
        """Req 5.6: Reject generation requests for unconfigured service operations."""
        with pytest.raises(ExternalServiceError) as exc_info:
            await service.get_price("unknown_service", "unknown_op")

        assert "not yet available" in exc_info.value.message
        assert exc_info.value.details["ai_service"] == "unknown_service"
        assert exc_info.value.details["operation_type"] == "unknown_op"

    @pytest.mark.asyncio
    async def test_prefers_model_specific_price_over_default(
        self, service: CreditPricingService, repo: FakeCreditPricingRepo
    ) -> None:
        repo.seed("deepseek", "lyric", cr(2), sub_model="")
        repo.seed("deepseek", "lyric", cr(5), sub_model="deepseek-reasoner")

        assert await service.get_price("deepseek", "lyric", "deepseek-reasoner") == cr(5)
        assert await service.get_price("deepseek", "lyric", "deepseek-chat") == cr(2)

    @pytest.mark.asyncio
    async def test_falls_back_to_provider_default_when_model_missing(
        self, service: CreditPricingService, repo: FakeCreditPricingRepo
    ) -> None:
        repo.seed("openai", "title", cr(3), sub_model="")
        assert await service.get_price("openai", "title", "gpt-4o-mini") == cr(3)

    @pytest.mark.asyncio
    async def test_suno_v5_and_v5_5_use_separate_pricing_rows(
        self, service: CreditPricingService, repo: FakeCreditPricingRepo
    ) -> None:
        repo.seed("suno", "music_generation", cr(14), cr(8), sub_model="V5")
        repo.seed("suno", "music_generation", cr(16), cr(9), sub_model="V5_5")
        assert await service.get_price("suno", "music_generation", "V5") == cr(14)
        assert await service.get_price("suno", "music_generation", "V5_5") == cr(16)
        assert await service.get_price("suno", "music_generation", "v5.5") == cr(16)

    @pytest.mark.asyncio
    async def test_suno_music_operation_aliases_music_generation_row(
        self, service: CreditPricingService, repo: FakeCreditPricingRepo
    ) -> None:
        repo.seed("suno", "music_generation", cr(14), cr(8), sub_model="V5")
        assert await service.get_price("suno", "music", "V5") == cr(14)

    @pytest.mark.asyncio
    async def test_suno_prefers_music_row_over_music_generation_alias(
        self, service: CreditPricingService, repo: FakeCreditPricingRepo
    ) -> None:
        repo.seed("suno", "music_generation", cr(14), cr(8), sub_model="V5")
        repo.seed("suno", "music", cr(20), cr(10), sub_model="V5")
        assert await service.get_price("suno", "music", "V5") == cr(20)
        assert await service.get_price("suno", "music_generation", "V5") == cr(20)


# ---------------------------------------------------------------------------
# Tests: set_price
# ---------------------------------------------------------------------------


class TestSetPrice:
    """Tests for set_price method (create or update)."""

    @pytest.mark.asyncio
    async def test_creates_new_entry(
        self, service: CreditPricingService, repo: FakeCreditPricingRepo
    ) -> None:
        result = await service.set_price("suno", "music_generation", cr(14), cr(8))
        assert result["ai_service"] == "suno"
        assert result["operation_type"] == "music_generation"
        assert result["credits_per_operation"] == cr(14)
        assert result["external_cost_cents"] == cr(8)
        assert result["margin"] == 6.0

    @pytest.mark.asyncio
    async def test_updates_existing_entry(
        self, service: CreditPricingService, repo: FakeCreditPricingRepo
    ) -> None:
        repo.seed("suno", "music_generation", cr(14), cr(8))

        result = await service.set_price("suno", "music_generation", cr(20), cr(9))
        assert result["credits_per_operation"] == cr(20)
        assert result["external_cost_cents"] == cr(9)
        assert result["margin"] == 11.0

    @pytest.mark.asyncio
    async def test_validates_min_credits(
        self, service: CreditPricingService
    ) -> None:
        """Req 5.5: credits_per_operation must be >= 1 micro-unit."""
        with pytest.raises(ValidationError):
            await service.set_price("suno", "music", 0, cr(1))

    @pytest.mark.asyncio
    async def test_validates_max_credits(
        self, service: CreditPricingService
    ) -> None:
        """Req 5.5: credits_per_operation must be <= max micro-units."""
        with pytest.raises(ValidationError):
            await service.set_price("suno", "music", MAX_CREDIT_UNITS + 1, cr(1))

    @pytest.mark.asyncio
    async def test_validates_negative_credits(
        self, service: CreditPricingService
    ) -> None:
        """Req 5.5: negative values rejected."""
        with pytest.raises(ValidationError):
            await service.set_price("suno", "music", -5, cr(1))

    @pytest.mark.asyncio
    async def test_rejects_cost_above_sell(
        self, service: CreditPricingService
    ) -> None:
        with pytest.raises(ValidationError) as exc_info:
            await service.set_price("fal", "background_image", cr(5), cr(6))
        assert exc_info.value.details["error_code"] == "COST_EXCEEDS_SELL"

    @pytest.mark.asyncio
    async def test_rejects_music_cost_below_basis(
        self, service: CreditPricingService
    ) -> None:
        with pytest.raises(ValidationError) as exc_info:
            await service.set_price("suno", "music", cr(7.5), cr(5))
        assert exc_info.value.details["error_code"] == "MUSIC_COST_BELOW_BASIS"

    @pytest.mark.asyncio
    async def test_allows_music_cost_at_basis(
        self, service: CreditPricingService
    ) -> None:
        result = await service.set_price("suno", "music", cr(7.5), cr(6))
        assert result["external_cost_cents"] == cr(6)


# ---------------------------------------------------------------------------
# Tests: create_price (strict create — Req 5.7)
# ---------------------------------------------------------------------------


class TestCreatePrice:
    """Tests for create_price method (strict create)."""

    @pytest.mark.asyncio
    async def test_creates_new_entry(
        self, service: CreditPricingService
    ) -> None:
        result = await service.create_price("fal", "image_generation", cr(5), cr(2))
        assert result["ai_service"] == "fal"
        assert result["credits_per_operation"] == cr(5)

    @pytest.mark.asyncio
    async def test_raises_duplicate_error(
        self, service: CreditPricingService, repo: FakeCreditPricingRepo
    ) -> None:
        """Req 5.7: Reject duplicate (ai_service, operation_type)."""
        repo.seed("suno", "music_generation", cr(14), cr(8))

        with pytest.raises(DuplicateError) as exc_info:
            await service.create_price("suno", "music_generation", cr(20), cr(9))
        assert "already exists" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_validates_credits(
        self, service: CreditPricingService
    ) -> None:
        with pytest.raises(ValidationError):
            await service.create_price("suno", "music", 0, cr(1))


# ---------------------------------------------------------------------------
# Tests: update_price (strict update)
# ---------------------------------------------------------------------------


class TestUpdatePrice:
    """Tests for update_price method (strict update)."""

    @pytest.mark.asyncio
    async def test_updates_existing_entry(
        self, service: CreditPricingService, repo: FakeCreditPricingRepo
    ) -> None:
        repo.seed("suno", "music_generation", cr(14), cr(8))

        result = await service.update_price("suno", "music_generation", cr(18), cr(9))
        assert result["credits_per_operation"] == cr(18)
        assert result["external_cost_cents"] == cr(9)

    @pytest.mark.asyncio
    async def test_raises_not_found_when_missing(
        self, service: CreditPricingService
    ) -> None:
        with pytest.raises(NotFoundError) as exc_info:
            await service.update_price("unknown", "unknown_op", cr(10), cr(1))
        assert "No pricing found" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_validates_credits(
        self, service: CreditPricingService, repo: FakeCreditPricingRepo
    ) -> None:
        repo.seed("suno", "music_generation", cr(14), cr(8))
        with pytest.raises(ValidationError):
            await service.update_price("suno", "music_generation", MAX_CREDIT_UNITS + 1, cr(1))


# ---------------------------------------------------------------------------
# Tests: delete_price
# ---------------------------------------------------------------------------


class TestDeletePrice:
    """Tests for delete_price method."""

    @pytest.mark.asyncio
    async def test_deletes_existing_entry(
        self, service: CreditPricingService, repo: FakeCreditPricingRepo
    ) -> None:
        repo.seed("suno", "music_generation", cr(14), cr(8))
        result = await service.delete_price("suno", "music_generation")
        assert result is True

        # Verify it's gone
        entries = await service.get_all_pricing()
        assert len(entries) == 0

    @pytest.mark.asyncio
    async def test_returns_false_when_not_found(
        self, service: CreditPricingService
    ) -> None:
        result = await service.delete_price("missing", "missing_op")
        assert result is False


# ---------------------------------------------------------------------------
# Tests: delete_all_prices
# ---------------------------------------------------------------------------


class TestDeleteAllPrices:
    """Tests for delete_all_prices method."""

    @pytest.mark.asyncio
    async def test_deletes_all_entries(
        self, service: CreditPricingService, repo: FakeCreditPricingRepo
    ) -> None:
        repo.seed("suno", "music_generation", cr(14), cr(8))
        repo.seed("openai", "lyric", cr(5), cr(3))
        count = await service.delete_all_prices()
        assert count == 2
        assert await service.get_all_pricing() == []

    @pytest.mark.asyncio
    async def test_deletes_only_matching_provider(
        self, service: CreditPricingService, repo: FakeCreditPricingRepo
    ) -> None:
        repo.seed("suno", "music_generation", cr(14), cr(8))
        repo.seed("openai", "lyric", cr(5), cr(3))
        count = await service.delete_all_prices(ai_service="suno")
        assert count == 1
        entries = await service.get_all_pricing()
        assert len(entries) == 1
        assert entries[0]["ai_service"] == "openai"
