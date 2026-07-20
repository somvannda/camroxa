"""Tests for payment-gated onboarding AI entitlements."""

from __future__ import annotations

from uuid import uuid4

import pytest

from platform_api.exceptions import ForbiddenError
from platform_api.services.onboarding_entitlement_service import (
    ONBOARDING_AI_LIMITS,
    assert_onboarding_ai_allowed,
    run_onboarding_ai_operation,
    user_has_paid_for_onboarding,
    user_in_onboarding,
)


class FakePool:
    def __init__(self) -> None:
        self.paid = False
        self.profile_count = 0
        self.base_allowance = 2
        self.addon_slots = 0
        self.addon_pending = 0
        self.usage: dict[tuple, int] = {}
        self.events: list[tuple[str, tuple]] = []

    async def fetchrow(self, query: str, *args):
        q = " ".join(query.split())
        if "FROM billing_payments" in q and self.paid:
            return {"?": 1}
        if "FROM licenses l" in q and "JOIN plans p" in q and "profile_allowance" in q:
            return {
                "base_allowance": self.base_allowance,
                "addon_slots": self.addon_slots,
                "addon_pending": self.addon_pending,
            }
        if "FROM licenses l" in q and self.paid:
            return {"?": 1}
        if "FROM channel_profiles" in q:
            return {"cnt": self.profile_count}
        if "FROM onboarding_ai_usage" in q:
            key = (args[0], args[1])
            count = self.usage.get(key, 0)
            return {"usage_count": count} if count else None
        return None

    async def execute(self, query: str, *args):
        if "INSERT INTO onboarding_ai_usage" in query:
            key = (args[0], args[1])
            self.usage[key] = self.usage.get(key, 0) + int(args[2])
        if "INSERT INTO credit_transactions" in query:
            self.events.append(("credit_transactions", args))


@pytest.mark.asyncio
async def test_unpaid_user_blocked() -> None:
    pool = FakePool()
    pool.paid = False
    pool.profile_count = 0
    with pytest.raises(ForbiddenError, match="Complete payment"):
        await assert_onboarding_ai_allowed(pool, uuid4(), "channel_name")


@pytest.mark.asyncio
async def test_paid_user_in_onboarding_allowed() -> None:
    pool = FakePool()
    pool.paid = True
    pool.profile_count = 0
    await assert_onboarding_ai_allowed(pool, uuid4(), "channel_name")


@pytest.mark.asyncio
async def test_completed_onboarding_blocked() -> None:
    pool = FakePool()
    pool.paid = True
    pool.profile_count = 2
    with pytest.raises(ForbiddenError, match="finishing channel setup"):
        await assert_onboarding_ai_allowed(pool, uuid4(), "channel_name")


@pytest.mark.asyncio
async def test_addon_pending_reopens_onboarding_ai() -> None:
    pool = FakePool()
    pool.paid = True
    pool.profile_count = 2
    pool.addon_pending = 2
    await assert_onboarding_ai_allowed(pool, uuid4(), "channel_cover")


@pytest.mark.asyncio
async def test_addon_pending_scales_usage_limits() -> None:
    pool = FakePool()
    pool.paid = True
    pool.profile_count = 2
    pool.addon_pending = 2
    user_id = uuid4()
    # First onboarding already consumed the base limit; scaled limit should allow more.
    pool.usage[(user_id, "channel_logo")] = ONBOARDING_AI_LIMITS["channel_logo"]
    await assert_onboarding_ai_allowed(pool, user_id, "channel_logo")
    pool.usage[(user_id, "channel_logo")] = ONBOARDING_AI_LIMITS["channel_logo"] * 2
    with pytest.raises(ForbiddenError, match="limit reached"):
        await assert_onboarding_ai_allowed(pool, user_id, "channel_logo")


@pytest.mark.asyncio
async def test_usage_limit_enforced() -> None:
    pool = FakePool()
    pool.paid = True
    pool.profile_count = 0
    user_id = uuid4()
    limit = ONBOARDING_AI_LIMITS["channel_logo"]
    pool.usage[(user_id, "channel_logo")] = limit
    with pytest.raises(ForbiddenError, match="limit reached"):
        await assert_onboarding_ai_allowed(pool, user_id, "channel_logo")


@pytest.mark.asyncio
async def test_user_in_onboarding_helper() -> None:
    pool = FakePool()
    pool.profile_count = 1
    assert await user_in_onboarding(pool, uuid4()) is True
    pool.profile_count = 2
    assert await user_in_onboarding(pool, uuid4()) is False
    pool.addon_pending = 2
    assert await user_in_onboarding(pool, uuid4()) is True


@pytest.mark.asyncio
async def test_user_has_paid_helper() -> None:
    pool = FakePool()
    assert await user_has_paid_for_onboarding(pool, uuid4()) is False
    pool.paid = True
    assert await user_has_paid_for_onboarding(pool, uuid4()) is True


@pytest.mark.asyncio
async def test_run_onboarding_ai_operation_records_success_event() -> None:
    pool = FakePool()
    pool.paid = True
    user_id = uuid4()

    result = await run_onboarding_ai_operation(
        pool,
        user_id,
        "channel_name",
        lambda: _return_value("ok"),
        usage_metadata={"provider": "deepseek", "sub_model": "deepseek-chat"},
    )

    assert result == "ok"
    assert pool.usage[(user_id, "channel_name")] == 1
    assert len(pool.events) == 1
    assert pool.events[0][1][2] == "channel_name"


@pytest.mark.asyncio
async def test_run_onboarding_ai_operation_records_blocked_event() -> None:
    pool = FakePool()
    pool.paid = False
    user_id = uuid4()

    with pytest.raises(ForbiddenError, match="Complete payment"):
        await run_onboarding_ai_operation(
            pool,
            user_id,
            "channel_name",
            lambda: _return_value("ok"),
            usage_metadata={"provider": "deepseek", "sub_model": "deepseek-chat"},
        )

    assert pool.usage == {}
    assert len(pool.events) == 1
    assert pool.events[0][1][2] == "channel_name"


async def _return_value(value: str) -> str:
    return value
