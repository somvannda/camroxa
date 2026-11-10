"""Tests for the royalty policy foundation (Phase 0)."""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from platform_api.exceptions import ValidationError
from platform_api.services.royalty_policy_service import (
    DEFAULT_ROYALTY_POLICY,
    RoyaltyPolicyService,
    normalize_policy,
    validate_policy,
)


@pytest.mark.asyncio
async def test_get_active_falls_back_to_default_when_no_policy_exists() -> None:
    pool = AsyncMock()
    pool.fetchrow = AsyncMock(return_value=None)

    policy = await RoyaltyPolicyService(pool).get_active()

    assert policy["source"] == "default"
    assert policy["version"] == 0
    assert policy["document"]["weights"]["ai_generated"] == 0.3
    assert policy["document"]["eligibility_streams"] == 500
    assert policy["document"]["caps"]["per_creator_pool_pct"] == 40


@pytest.mark.asyncio
async def test_get_active_merges_a_partial_document() -> None:
    pool = AsyncMock()
    pool.fetchrow = AsyncMock(
        return_value={
            "id": uuid4(),
            "version": 7,
            "document": '{"weights": {"ai_generated": 0.2}, "caps": {"per_track_weighted_streams": 250000}}',
            "effective_from": None,
            "effective_to": None,
            "created_at": None,
        }
    )

    policy = await RoyaltyPolicyService(pool).get_active()

    assert policy["source"] == "database"
    assert policy["version"] == 7
    assert policy["document"]["weights"]["ai_generated"] == 0.2
    # Defaults still fill the rest of the document.
    assert policy["document"]["weights"]["original"] == 1.0
    assert policy["document"]["eligibility_streams"] == 500
    # Compatibility keys follow the track cap.
    assert policy["document"]["ai"]["max_royalty_streams"] == 250000


def test_validate_policy_rejects_invalid_weights() -> None:
    document = normalize_policy({"weights": {"original": 2.0}})

    with pytest.raises(ValidationError) as exc:
        validate_policy(document)

    assert "weights.original" in (exc.value.details or {}).get("fields", {})


def test_normalize_policy_keeps_legacy_eligibility_in_sync() -> None:
    document = normalize_policy(
        {"eligibility_streams": 900, "eligibility_unique_listeners": 75}
    )

    assert document["eligibility"]["min_valid_streams"] == 900
    assert document["eligibility"]["min_unique_listeners"] == 75
    assert document["eligibility_streams"] == 900
    assert document["eligibility_unique_listeners"] == 75


class _Transaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False


class _Connection:
    def __init__(self) -> None:
        self.fetchval = AsyncMock(return_value=2)
        self.execute = AsyncMock()
        self.fetchrow = AsyncMock(
            return_value={
                "id": uuid4(),
                "version": 3,
                "document": DEFAULT_ROYALTY_POLICY,
                "effective_from": None,
                "effective_to": None,
                "created_at": None,
            }
        )

    def transaction(self):
        return _Transaction()


class _Acquire:
    def __init__(self, conn: _Connection) -> None:
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *_args):
        return False


class _Pool:
    def __init__(self, conn: _Connection) -> None:
        self._conn = conn

    def acquire(self):
        return _Acquire(self._conn)


@pytest.mark.asyncio
async def test_create_version_closes_the_active_policy_and_inserts_the_next_version() -> None:
    conn = _Connection()
    pool = _Pool(conn)

    policy = await RoyaltyPolicyService(pool).create_version({"pool": {"amount_usd": 5000}})

    assert policy["version"] == 3
    conn.execute.assert_awaited_once()
    assert "UPDATE royalty_policies" in conn.execute.await_args.args[0]
    conn.fetchrow.assert_awaited_once()
    assert "INSERT INTO royalty_policies" in conn.fetchrow.await_args.args[0]


@pytest.mark.asyncio
async def test_attach_royalty_stats_handles_missing_rows_and_origins() -> None:
    from platform_api.routers.streaming_admin import _attach_royalty_stats

    pool = AsyncMock()
    pool.fetchrow = AsyncMock(
        return_value={
            "id": uuid4(),
            "version": 1,
            "document": DEFAULT_ROYALTY_POLICY,
            "effective_from": None,
            "effective_to": None,
            "created_at": None,
        }
    )
    pool.fetch = AsyncMock(return_value=[])

    rows = [
        {"id": uuid4(), "origin": "ai_assisted"},
        {"id": uuid4(), "origin": "ai_generated"},
    ]

    await _attach_royalty_stats(pool, rows)

    for row in rows:
        assert row["valid_streams"] == 0
        assert row["unique_listeners"] == 0
        assert row["eligible"] is False
        assert row["earned_usd"] == 0.0
        assert row["cap_remaining"] == 500_000
