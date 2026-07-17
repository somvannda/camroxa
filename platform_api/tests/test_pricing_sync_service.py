"""Tests for routing-driven pricing sync helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from platform_api.ai.capability_catalog import audit_routing_configuration
from platform_api.services.credit_pricing_service import CreditPricingService
from platform_api.services.pricing_sync_service import (
    collect_required_pricing_pairs,
    suggest_pricing_values,
)


def test_collect_required_pairs_includes_fallback_operations() -> None:
    pairs = collect_required_pricing_pairs(
        assignments={"lyric": {"provider": "deepseek", "sub_model": "deepseek-chat"}},
        text_fallback_chain=[{"provider": "openai", "sub_model": "gpt-4o-mini"}],
        image_fallback_chain=[{"provider": "fal", "sub_model": "flux-pro"}],
    )
    keys = {(p.ai_service, p.operation_type, p.sub_model) for p in pairs}
    assert ("deepseek", "lyric", "deepseek-chat") in keys
    assert ("openai", "channel_name", "gpt-4o-mini") in keys
    assert ("openai", "album", "gpt-4o-mini") in keys
    assert ("fal", "channel_logo", "flux-pro") in keys
    assert ("fal", "thumbnail_image", "flux-pro") in keys


def test_suggest_pricing_copies_same_provider() -> None:
    credits, cost = suggest_pricing_values(
        ai_service="openai",
        operation_type="title",
        existing_entries=[
            {
                "ai_service": "openai",
                "operation_type": "lyric",
                "credits_per_operation": 7,
                "external_cost_cents": 2,
            }
        ],
    )
    assert credits == 7
    assert cost == 2


def test_audit_treats_draft_pricing_as_warning_not_error() -> None:
    result = audit_routing_configuration(
        assignments={"channel_name": {"provider": "openai", "sub_model": "gpt-4o-mini"}},
        text_fallback_chain=[],
        image_fallback_chain=[],
        pricing_entries=[
            {
                "ai_service": "openai",
                "operation_type": "channel_name",
                "sub_model": "gpt-4o-mini",
                "credits_per_operation": 3,
                "needs_review": True,
            }
        ],
    )
    assert result["ready"] is True
    assert any(issue["code"] == "draft_pricing" for issue in result["issues"])
    assert not any(issue["code"] == "missing_pricing" for issue in result["issues"])


class _FakePricingRepo:
    def __init__(self) -> None:
        self._entries: dict[tuple[str, str, str], dict] = {}

    async def get_all(self) -> list[dict]:
        return list(self._entries.values())

    async def get_by_service_and_operation(
        self,
        ai_service: str,
        operation_type: str,
        sub_model: str = "",
    ) -> dict | None:
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
    ) -> dict:
        now = datetime.now(timezone.utc)
        row = {
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
        self._entries[(ai_service, operation_type, sub_model)] = row
        return row

    async def update(self, *args, **kwargs):
        return None

    async def delete(self, *args, **kwargs) -> bool:
        return False

    async def approve(self, *args, **kwargs):
        return None

    async def approve_many(self, pairs):
        return 0


@pytest.mark.asyncio
async def test_sync_from_routing_creates_draft_rows() -> None:
    repo = _FakePricingRepo()
    service = CreditPricingService(pricing_repo=repo)
    result = await service.sync_from_routing_config(
        assignments={"lyric": {"provider": "deepseek", "sub_model": "deepseek-chat"}},
        text_fallback_chain=[{"provider": "openai", "sub_model": "gpt-4o-mini"}],
        image_fallback_chain=[],
    )
    assert result["created_count"] > 0
    assert all(row["needs_review"] for row in result["created"])
