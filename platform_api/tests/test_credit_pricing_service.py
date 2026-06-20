"""Unit tests for CreditPricingService.

Tests pricing CRUD operations, validation, margin computation,
and rejection of unconfigured model operations.

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


# ---------------------------------------------------------------------------
# Fake CreditPricingRepository
# ---------------------------------------------------------------------------


class FakeCreditPricingRepo:
    """In-memory fake implementing CreditPricingRepositoryProtocol."""

    def __init__(self) -> None:
        self._entries: dict[tuple[str, str], dict[str, Any]] = {}

    def seed(
        self,
        model_identifier: str,
        operation_type: str,
        credits_per_operation: int,
        external_cost_cents: int | None = None,
    ) -> None:
        """Seed an entry for testing."""
        key = (model_identifier, operation_type)
        now = datetime.now(timezone.utc)
        self._entries[key] = {
            "id": uuid4(),
            "model_identifier": model_identifier,
            "operation_type": operation_type,
            "credits_per_operation": credits_per_operation,
            "external_cost_cents": external_cost_cents,
            "created_at": now,
            "updated_at": now,
        }

    async def get_all(self) -> list[dict[str, Any]]:
        return list(self._entries.values())

    async def get_by_model_and_operation(
        self, model_identifier: str, operation_type: str
    ) -> dict[str, Any] | None:
        return self._entries.get((model_identifier, operation_type))

    async def create(
        self,
        model_identifier: str,
        operation_type: str,
        credits_per_operation: int,
        external_cost_cents: int | None,
    ) -> dict[str, Any]:
        key = (model_identifier, operation_type)
        now = datetime.now(timezone.utc)
        entry = {
            "id": uuid4(),
            "model_identifier": model_identifier,
            "operation_type": operation_type,
            "credits_per_operation": credits_per_operation,
            "external_cost_cents": external_cost_cents,
            "created_at": now,
            "updated_at": now,
        }
        self._entries[key] = entry
        return entry

    async def update(
        self,
        model_identifier: str,
        operation_type: str,
        credits_per_operation: int,
        external_cost_cents: int | None,
    ) -> dict[str, Any] | None:
        key = (model_identifier, operation_type)
        if key not in self._entries:
            return None
        self._entries[key]["credits_per_operation"] = credits_per_operation
        self._entries[key]["external_cost_cents"] = external_cost_cents
        self._entries[key]["updated_at"] = datetime.now(timezone.utc)
        return self._entries[key]

    async def delete(self, model_identifier: str, operation_type: str) -> bool:
        key = (model_identifier, operation_type)
        if key in self._entries:
            del self._entries[key]
            return True
        return False


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
        repo.seed("suno_v5", "music_generation", 14, 800)
        repo.seed("fal_ai", "image_generation", 5, 200)

        result = await service.get_all_pricing()
        assert len(result) == 2

        # Check margin computation: credits - (external_cost_cents / 100)
        suno_entry = next(e for e in result if e["model_identifier"] == "suno_v5")
        assert suno_entry["margin"] == 14 - (800 / 100)  # 14 - 8.0 = 6.0

        fal_entry = next(e for e in result if e["model_identifier"] == "fal_ai")
        assert fal_entry["margin"] == 5 - (200 / 100)  # 5 - 2.0 = 3.0

    @pytest.mark.asyncio
    async def test_margin_is_none_when_no_external_cost(
        self, service: CreditPricingService, repo: FakeCreditPricingRepo
    ) -> None:
        repo.seed("deepseek", "llm_generation", 3, None)

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
        repo.seed("suno_v5", "music_generation", 14, 800)
        price = await service.get_price("suno_v5", "music_generation")
        assert price == 14

    @pytest.mark.asyncio
    async def test_raises_external_service_error_when_not_configured(
        self, service: CreditPricingService
    ) -> None:
        """Req 5.6: Reject generation requests for unconfigured model operations."""
        with pytest.raises(ExternalServiceError) as exc_info:
            await service.get_price("unknown_model", "unknown_op")

        assert "not yet available" in exc_info.value.message
        assert exc_info.value.details["model_identifier"] == "unknown_model"
        assert exc_info.value.details["operation_type"] == "unknown_op"


# ---------------------------------------------------------------------------
# Tests: set_price
# ---------------------------------------------------------------------------


class TestSetPrice:
    """Tests for set_price method (create or update)."""

    @pytest.mark.asyncio
    async def test_creates_new_entry(
        self, service: CreditPricingService, repo: FakeCreditPricingRepo
    ) -> None:
        result = await service.set_price("suno_v5", "music_generation", 14, 800)
        assert result["model_identifier"] == "suno_v5"
        assert result["operation_type"] == "music_generation"
        assert result["credits_per_operation"] == 14
        assert result["external_cost_cents"] == 800
        assert result["margin"] == 6.0

    @pytest.mark.asyncio
    async def test_updates_existing_entry(
        self, service: CreditPricingService, repo: FakeCreditPricingRepo
    ) -> None:
        repo.seed("suno_v5", "music_generation", 14, 800)

        result = await service.set_price("suno_v5", "music_generation", 20, 900)
        assert result["credits_per_operation"] == 20
        assert result["external_cost_cents"] == 900
        assert result["margin"] == 20 - (900 / 100)  # 11.0

    @pytest.mark.asyncio
    async def test_validates_min_credits(
        self, service: CreditPricingService
    ) -> None:
        """Req 5.5: credits_per_operation must be >= 1."""
        with pytest.raises(ValidationError) as exc_info:
            await service.set_price("suno_v5", "music", 0, 100)
        assert "at least 1" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_validates_max_credits(
        self, service: CreditPricingService
    ) -> None:
        """Req 5.5: credits_per_operation must be <= 10000."""
        with pytest.raises(ValidationError) as exc_info:
            await service.set_price("suno_v5", "music", 10001, 100)
        assert "not exceed 10000" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_validates_negative_credits(
        self, service: CreditPricingService
    ) -> None:
        """Req 5.5: negative values rejected."""
        with pytest.raises(ValidationError):
            await service.set_price("suno_v5", "music", -5, 100)


# ---------------------------------------------------------------------------
# Tests: create_price (strict create — Req 5.7)
# ---------------------------------------------------------------------------


class TestCreatePrice:
    """Tests for create_price method (strict create)."""

    @pytest.mark.asyncio
    async def test_creates_new_entry(
        self, service: CreditPricingService
    ) -> None:
        result = await service.create_price("fal_ai", "image_generation", 5, 200)
        assert result["model_identifier"] == "fal_ai"
        assert result["credits_per_operation"] == 5

    @pytest.mark.asyncio
    async def test_raises_duplicate_error(
        self, service: CreditPricingService, repo: FakeCreditPricingRepo
    ) -> None:
        """Req 5.7: Reject duplicate (model_identifier, operation_type)."""
        repo.seed("suno_v5", "music_generation", 14, 800)

        with pytest.raises(DuplicateError) as exc_info:
            await service.create_price("suno_v5", "music_generation", 20, 900)
        assert "already exists" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_validates_credits(
        self, service: CreditPricingService
    ) -> None:
        with pytest.raises(ValidationError):
            await service.create_price("suno_v5", "music", 0, 100)


# ---------------------------------------------------------------------------
# Tests: update_price (strict update)
# ---------------------------------------------------------------------------


class TestUpdatePrice:
    """Tests for update_price method (strict update)."""

    @pytest.mark.asyncio
    async def test_updates_existing_entry(
        self, service: CreditPricingService, repo: FakeCreditPricingRepo
    ) -> None:
        repo.seed("suno_v5", "music_generation", 14, 800)

        result = await service.update_price("suno_v5", "music_generation", 18, 900)
        assert result["credits_per_operation"] == 18
        assert result["external_cost_cents"] == 900

    @pytest.mark.asyncio
    async def test_raises_not_found_when_missing(
        self, service: CreditPricingService
    ) -> None:
        with pytest.raises(NotFoundError) as exc_info:
            await service.update_price("unknown", "unknown_op", 10, 100)
        assert "No pricing found" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_validates_credits(
        self, service: CreditPricingService, repo: FakeCreditPricingRepo
    ) -> None:
        repo.seed("suno_v5", "music_generation", 14, 800)
        with pytest.raises(ValidationError):
            await service.update_price("suno_v5", "music_generation", 10001, 100)


# ---------------------------------------------------------------------------
# Tests: delete_price
# ---------------------------------------------------------------------------


class TestDeletePrice:
    """Tests for delete_price method."""

    @pytest.mark.asyncio
    async def test_deletes_existing_entry(
        self, service: CreditPricingService, repo: FakeCreditPricingRepo
    ) -> None:
        repo.seed("suno_v5", "music_generation", 14, 800)
        result = await service.delete_price("suno_v5", "music_generation")
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
