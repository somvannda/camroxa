from __future__ import annotations

from datetime import datetime, timezone

import pytest

from platform_api.middleware.auth import AuthContext
from platform_api.routers import content_pools
from platform_api.services import content_pool_service


class FakeContentPoolDb:
    def __init__(self) -> None:
        self.finalized: list[tuple[int, str]] = []
        self.released: list[tuple[int, str]] = []

    async def fetchrow(self, query: str, *args):
        if "UPDATE title_pool AS target" in query:
            return {
                "id": 8,
                "text": "Midnight Echo",
                "used_count": 5,
                "reservation_token": args[0],
                "reserved_by": args[1],
                "reserved_at": datetime(2026, 6, 28, 12, 0, tzinfo=timezone.utc),
                "created_at": datetime(2026, 6, 27, 10, 0, tzinfo=timezone.utc),
            }
        if "UPDATE opening_pairs AS target" in query:
            return {
                "id": 3,
                "line1": "Drive through the dark",
                "line2": "Chasing every light",
                "used_count": 7,
                "reservation_token": args[0],
                "reserved_by": args[1],
                "reserved_at": datetime(2026, 6, 28, 12, 5, tzinfo=timezone.utc),
                "created_at": datetime(2026, 6, 25, 8, 0, tzinfo=timezone.utc),
            }
        if "FROM title_pool" in query:
            return {"total": 120, "unused": 75}
        if "FROM album_pool" in query:
            return {"total": 80, "unused": 33}
        if "FROM opening_pairs" in query:
            return {"total": 64, "unused": 28}
        return None

    async def fetchval(self, query: str, *args):
        if "FROM title_pool" in query:
            return 120
        if "FROM album_pool" in query:
            return 80
        if "FROM opening_pairs" in query:
            return 64
        return 0

    async def fetch(self, query: str, *args):
        if "FROM title_pool" in query:
            return [
                {
                    "id": 8,
                    "text": "Midnight Echo",
                    "used_count": 5,
                    "created_at": datetime(2026, 6, 27, 10, 0, tzinfo=timezone.utc),
                }
            ]
        if "FROM album_pool" in query:
            return [
                {
                    "id": 4,
                    "text": "Neon Afterglow",
                    "used_count": 2,
                    "created_at": datetime(2026, 6, 26, 9, 0, tzinfo=timezone.utc),
                }
            ]
        if "FROM opening_pairs" in query:
            return [
                {
                    "id": 3,
                    "line1": "Drive through the dark",
                    "line2": "Chasing every light",
                    "used_count": 7,
                    "created_at": datetime(2026, 6, 25, 8, 0, tzinfo=timezone.utc),
                }
            ]
        return []

    async def execute(self, query: str, *args):
        if "UPDATE title_pool" in query and "used_count = used_count + 1" in query:
            self.finalized.append((args[0], args[1]))
            return "UPDATE 1"
        if "UPDATE opening_pairs" in query and "reservation_token = NULL" in query:
            self.released.append((args[0], args[1]))
            return "UPDATE 1"
        return "UPDATE 0"


@pytest.mark.asyncio
async def test_content_pool_stats_returns_used_and_unused_counts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(content_pools, "get_db_pool", lambda: FakeContentPoolDb())

    result = await content_pools.get_content_pool_stats(
        AuthContext(
            user_id="00000000-0000-0000-0000-000000000001",
            email="boss@example.com",
            role="user",
        )
    )

    assert result.titles.total == 120
    assert result.titles.unused == 75
    assert result.albums.total == 80
    assert result.openings.total == 64


@pytest.mark.asyncio
async def test_content_pool_list_returns_read_only_rows_with_used_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(content_pools, "get_db_pool", lambda: FakeContentPoolDb())

    title_rows = await content_pools.list_content_pool_items(
        "titles",
        AuthContext(
            user_id="00000000-0000-0000-0000-000000000001",
            email="boss@example.com",
            role="user",
        ),
        limit=100,
        offset=0,
    )
    opening_rows = await content_pools.list_content_pool_items(
        "openings",
        AuthContext(
            user_id="00000000-0000-0000-0000-000000000001",
            email="boss@example.com",
            role="user",
        ),
        limit=100,
        offset=0,
    )

    assert title_rows.total == 120
    assert title_rows.items[0].text == "Midnight Echo"
    assert title_rows.items[0].used_count == 5
    assert opening_rows.items[0].text == "Drive through the dark"
    assert opening_rows.items[0].secondary_text == "Chasing every light"
    assert opening_rows.items[0].used_count == 7


@pytest.mark.asyncio
async def test_content_pool_claim_returns_reserved_item(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(content_pool_service, "get_db_pool", lambda: FakeContentPoolDb())

    claimed = await content_pools.claim_content_pool_item(
        "titles",
        content_pools.ClaimContentPoolRequest(
            reservation_token="claim-123",
            consumer="music-workspace",
            limit=25,
            ttl_seconds=900,
        ),
        AuthContext(
            user_id="00000000-0000-0000-0000-000000000001",
            email="boss@example.com",
            role="user",
        ),
    )

    assert claimed.kind == "titles"
    assert claimed.item.id == 8
    assert claimed.item.text == "Midnight Echo"
    assert claimed.item.reservation_token == "claim-123"
    assert claimed.item.reserved_by.endswith(":music-workspace")


@pytest.mark.asyncio
async def test_content_pool_release_and_finalize_apply_reservation_action(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_db = FakeContentPoolDb()
    monkeypatch.setattr(content_pool_service, "get_db_pool", lambda: fake_db)
    ctx = AuthContext(
        user_id="00000000-0000-0000-0000-000000000001",
        email="boss@example.com",
        role="user",
    )

    finalized = await content_pools.finalize_content_pool_item(
        "titles",
        content_pools.ReservationActionRequest(item_id=8, reservation_token="claim-123"),
        ctx,
    )
    released = await content_pools.release_content_pool_item(
        "openings",
        content_pools.ReservationActionRequest(item_id=3, reservation_token="claim-456"),
        ctx,
    )

    assert finalized.ok is True
    assert released.ok is True
    assert fake_db.finalized == [(8, "claim-123")]
    assert fake_db.released == [(3, "claim-456")]
