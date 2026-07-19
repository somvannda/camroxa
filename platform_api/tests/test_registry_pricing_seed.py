"""Tests for registry-based pricing gap seeding."""

from __future__ import annotations

from typing import Any

import pytest

from platform_api.services.pricing_generator_service import (
    collect_registry_pricing_pairs,
    PricingGeneratorService,
)


def test_collect_registry_pricing_pairs_includes_local_video_merge() -> None:
    pairs = collect_registry_pricing_pairs()
    keys = {(p.ai_service, p.operation_type, p.sub_model) for p in pairs}
    assert ("local", "video", "") in keys
    assert ("local", "video_merge", "") in keys


def test_collect_registry_pricing_pairs_includes_slai_gpt56() -> None:
    pairs = collect_registry_pricing_pairs()
    keys = {(p.ai_service, p.sub_model, p.operation_type) for p in pairs}
    assert ("slai", "gpt-5.6-luna", "lyric") in keys


class _FakePricingRepo:
    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.rows = list(rows or [])
        self.created: list[dict[str, Any]] = []

    async def get_all(self) -> list[dict[str, Any]]:
        return list(self.rows)

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
        row = {
            "ai_service": ai_service,
            "operation_type": operation_type,
            "sub_model": sub_model,
            "credits_per_operation": credits_per_operation,
            "external_cost_cents": external_cost_cents,
            "needs_review": needs_review,
        }
        self.created.append(row)
        self.rows.append(row)
        return row

    async def update(self, *args: Any, **kwargs: Any) -> dict[str, Any] | None:
        return None


class _FakeModelCostRepo:
    async def get_all(self) -> list[dict[str, Any]]:
        return [
            {
                "ai_service": "slai",
                "sub_model": "gpt-5.6-luna",
                "operation_type": "lyric",
                "cost_usd": 0.0012,
            }
        ]

    async def get_by_key(self, *args: Any, **kwargs: Any) -> dict[str, Any] | None:
        return None


@pytest.mark.asyncio
async def test_list_registry_pricing_gaps() -> None:
    pricing_repo = _FakePricingRepo(
        [{"ai_service": "slai", "sub_model": "xiaomi/mimo-v2.5-pro", "operation_type": "lyric"}]
    )
    service = PricingGeneratorService(
        model_cost_repo=_FakeModelCostRepo(),
        pricing_repo=pricing_repo,
    )
    gaps = await service.list_registry_pricing_gaps()
    gap_keys = {(g["ai_service"], g.get("sub_model") or "", g["operation_type"]) for g in gaps}
    assert ("slai", "gpt-5.6-luna", "lyric") in gap_keys
    assert ("slai", "xiaomi/mimo-v2.5-pro", "lyric") not in gap_keys


@pytest.mark.asyncio
async def test_generate_missing_from_registry_creates_needs_review_only() -> None:
    pricing_repo = _FakePricingRepo()
    service = PricingGeneratorService(
        model_cost_repo=_FakeModelCostRepo(),
        pricing_repo=pricing_repo,
    )
    result = await service.generate_missing_from_registry(
        margin_percent=50.0,
        global_credit_value=0.01,
    )
    assert result["created_count"] >= 1
    assert result["updated_count"] == 0
    luna_rows = [
        row
        for row in pricing_repo.created
        if row["ai_service"] == "slai"
        and row["sub_model"] == "gpt-5.6-luna"
        and row["operation_type"] == "lyric"
    ]
    assert len(luna_rows) == 1
    assert luna_rows[0]["needs_review"] is True


@pytest.mark.asyncio
async def test_generate_missing_from_registry_skips_existing() -> None:
    pricing_repo = _FakePricingRepo(
        [
            {
                "ai_service": "slai",
                "sub_model": "gpt-5.6-luna",
                "operation_type": "lyric",
                "credits_per_operation": 50000,
                "external_cost_cents": 12000,
                "needs_review": False,
            }
        ]
    )
    service = PricingGeneratorService(
        model_cost_repo=_FakeModelCostRepo(),
        pricing_repo=pricing_repo,
    )
    before = len(pricing_repo.rows)
    result = await service.generate_missing_from_registry(
        margin_percent=50.0,
        global_credit_value=0.01,
    )
    assert result["updated_count"] == 0
    luna = [
        row
        for row in pricing_repo.rows
        if row["ai_service"] == "slai"
        and row["sub_model"] == "gpt-5.6-luna"
        and row["operation_type"] == "lyric"
    ]
    assert len(luna) == 1
    assert luna[0]["credits_per_operation"] == 50000
    assert len(pricing_repo.rows) >= before


def test_collect_registry_suno_uses_music_operation_only() -> None:
    pairs = collect_registry_pricing_pairs()
    suno_ops = {p.operation_type for p in pairs if p.ai_service == "suno"}
    assert "music" in suno_ops
    assert "music_generation" not in suno_ops


@pytest.mark.asyncio
async def test_registry_gaps_skip_legacy_suno_music_generation_when_music_exists() -> None:
    pricing_repo = _FakePricingRepo(
        [
            {
                "ai_service": "suno",
                "sub_model": "V5",
                "operation_type": "music",
                "credits_per_operation": 75000,
                "external_cost_cents": 60000,
            }
        ]
    )
    service = PricingGeneratorService(
        model_cost_repo=_FakeModelCostRepo(),
        pricing_repo=pricing_repo,
    )
    gaps = await service.list_registry_pricing_gaps()
    assert not any(
        gap["ai_service"] == "suno" and gap["operation_type"] == "music_generation"
        for gap in gaps
    )
