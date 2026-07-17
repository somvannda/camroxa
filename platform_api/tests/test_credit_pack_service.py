"""Tests for credit pack admin service."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import pytest

from platform_api.exceptions import NotFoundError, ValidationError
from platform_api.services.credit_pack_service import CreditPackService


class FakePackRepo:
    def __init__(self) -> None:
        self._packs: dict[UUID, dict[str, Any]] = {}

    async def get_all_packs(self, *, include_inactive: bool = True) -> list[dict[str, Any]]:
        rows = list(self._packs.values())
        if include_inactive:
            return rows
        return [row for row in rows if row["is_active"]]

    async def get_by_id(self, pack_id: UUID) -> dict[str, Any] | None:
        return self._packs.get(pack_id)

    async def create_pack(
        self,
        *,
        name: str,
        price_cents: int,
        song_credits: int,
        request_count: int,
        is_active: bool,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        row = {
            "id": uuid4(),
            "name": name,
            "price_cents": price_cents,
            "song_credits": song_credits,
            "request_count": request_count,
            "is_active": is_active,
            "created_at": now,
            "updated_at": now,
        }
        self._packs[row["id"]] = row
        return row

    async def update_pack(
        self,
        pack_id: UUID,
        *,
        name: str,
        price_cents: int,
        song_credits: int,
        request_count: int,
        is_active: bool,
    ) -> dict[str, Any] | None:
        existing = self._packs.get(pack_id)
        if existing is None:
            return None
        existing.update(
            {
                "name": name,
                "price_cents": price_cents,
                "song_credits": song_credits,
                "request_count": request_count,
                "is_active": is_active,
                "updated_at": datetime.now(timezone.utc),
            }
        )
        return existing

    async def delete_pack(self, pack_id: UUID) -> bool:
        return self._packs.pop(pack_id, None) is not None


@pytest.mark.asyncio
async def test_create_pack_sets_legacy_request_count() -> None:
    service = CreditPackService(pack_repo=FakePackRepo())
    created = await service.create_pack(
        name="Starter",
        price_cents=1000,
        song_credits=3000,
    )
    assert created["song_credits"] == 3000
    assert created["request_count"] == 3000
    assert created["is_active"] is True


@pytest.mark.asyncio
async def test_update_pack_requires_existing_row() -> None:
    service = CreditPackService(pack_repo=FakePackRepo())
    with pytest.raises(NotFoundError):
        await service.update_pack(
            str(uuid4()),
            name="Missing",
            price_cents=1000,
            song_credits=100,
            is_active=True,
        )


@pytest.mark.asyncio
async def test_create_pack_rejects_low_price() -> None:
    service = CreditPackService(pack_repo=FakePackRepo())
    with pytest.raises(ValidationError):
        await service.create_pack(name="Bad", price_cents=10, song_credits=100)
