"""Renewal resolution for the hidden desktop plan ($79) in the quota-renew flow."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

import platform_api.routers.billing as billing
from platform_api.models.domain import License, Plan


def _license(plan_id, *, expires_in_days: int) -> License:
    now = datetime.now(timezone.utc)
    return License(
        id=uuid4(),
        license_key="k",
        plan_id=plan_id,
        user_id=uuid4(),
        status="active",
        activated_at=now - timedelta(days=30),
        expires_at=now + timedelta(days=expires_in_days),
        revoked_at=None,
        created_at=now,
    )


def _paid_plan() -> Plan:
    return Plan(
        id=uuid4(),
        name="Monthly · 2-channel",
        price_cents=7900,
        billing_cycle_days=30,
        monthly_credits=5150,
    )


def _patch_repos(*, active, latest, plan):
    license_repo = MagicMock()
    license_repo.get_active_for_user = AsyncMock(return_value=active)
    license_repo.get_latest_license_for_user = AsyncMock(return_value=latest)
    plan_repo = MagicMock()
    plan_repo.get_by_id = AsyncMock(return_value=plan)
    return (
        patch.object(billing, "LicenseRepository", return_value=license_repo),
        patch.object(billing, "PlanRepository", return_value=plan_repo),
        license_repo,
    )


@pytest.mark.asyncio
async def test_resolve_prefers_active_license() -> None:
    plan = _paid_plan()
    active = _license(plan.id, expires_in_days=2)
    p1, p2, license_repo = _patch_repos(active=active, latest=None, plan=plan)
    with p1, p2:
        resolved = await billing._resolve_renewable_license(object(), uuid4())
    assert resolved is not None
    assert resolved[1].price_cents == 7900
    license_repo.get_latest_license_for_user.assert_not_called()


@pytest.mark.asyncio
async def test_resolve_falls_back_to_lapsed_license() -> None:
    plan = _paid_plan()
    lapsed = _license(plan.id, expires_in_days=-1)
    p1, p2, license_repo = _patch_repos(active=None, latest=lapsed, plan=plan)
    with p1, p2:
        resolved = await billing._resolve_renewable_license(object(), uuid4())
    assert resolved is not None
    assert resolved[0].id == lapsed.id
    license_repo.get_latest_license_for_user.assert_awaited_once()


@pytest.mark.asyncio
async def test_resolve_rejects_free_plan() -> None:
    plan = Plan(id=uuid4(), name="Free", price_cents=0, billing_cycle_days=30)
    active = _license(plan.id, expires_in_days=5)
    p1, p2, _ = _patch_repos(active=active, latest=None, plan=plan)
    with p1, p2:
        resolved = await billing._resolve_renewable_license(object(), uuid4())
    assert resolved is None


@pytest.mark.asyncio
async def test_get_quota_renewal_reports_days_left_and_expired_flag() -> None:
    plan = _paid_plan()
    active = _license(plan.id, expires_in_days=2)
    ctx = MagicMock()
    ctx.user_id = str(uuid4())
    p1, p2, _ = _patch_repos(active=active, latest=None, plan=plan)
    with p1, p2:
        result = await billing.get_quota_renewal(ctx=ctx, pool=object())
    assert result.eligible is True
    assert result.plan_name == "Monthly · 2-channel"
    assert result.price_cents == 7900
    assert result.days_left is not None and result.days_left >= 1
    assert result.expired is False


@pytest.mark.asyncio
async def test_get_quota_renewal_ineligible_without_license() -> None:
    p1, p2, _ = _patch_repos(active=None, latest=None, plan=None)
    ctx = MagicMock()
    ctx.user_id = str(uuid4())
    with p1, p2:
        result = await billing.get_quota_renewal(ctx=ctx, pool=object())
    assert result.eligible is False
    assert result.plan_id is None


class _CapturingPool:
    def __init__(self) -> None:
        self.query = ""
        self.args = ()

    async def fetchrow(self, query, *args):
        self.query = " ".join(query.split())
        self.args = args
        return {
            "id": uuid4(),
            "license_key": "k",
            "plan_id": uuid4(),
            "user_id": uuid4(),
            "status": "active",
            "activated_at": datetime.now(timezone.utc),
            "expires_at": datetime.now(timezone.utc) + timedelta(days=30),
            "revoked_at": None,
            "profile_addon_slots": 0,
            "profile_addon_pending": 0,
            "created_at": datetime.now(timezone.utc),
        }


@pytest.mark.asyncio
async def test_extend_license_stacks_from_expiry_and_keeps_activated_at() -> None:
    from platform_api.repositories.license_repo import LicenseRepository

    pool = _CapturingPool()
    repo = LicenseRepository(pool=pool)
    await repo.extend_license(uuid4(), 30)

    # New period is added on top of the current expiry (never drops remaining days).
    assert "GREATEST(COALESCE(expires_at, NOW()), NOW())" in pool.query
    # activated_at must not be reset, so the monthly grant rolls at the period boundary.
    assert "activated_at =" not in pool.query
    assert pool.args[-1] == 30


def test_renewal_window_boundaries() -> None:
    now = datetime.now(timezone.utc)
    assert billing._renewal_window(None, now)[0] is True
    assert billing._renewal_window(now - timedelta(days=1), now)[0] is True
    assert billing._renewal_window(now + timedelta(days=6), now)[0] is True
    assert billing._renewal_window(now + timedelta(days=20), now)[0] is False

    renewable, days_left, expired, opens_in = billing._renewal_window(
        now + timedelta(days=20), now
    )
    assert renewable is False
    assert expired is False
    assert opens_in == 20 - billing.RENEWAL_WINDOW_DAYS


@pytest.mark.asyncio
async def test_get_quota_renewal_visible_but_not_renewable_outside_window() -> None:
    plan = _paid_plan()
    active = _license(plan.id, expires_in_days=20)
    ctx = MagicMock()
    ctx.user_id = str(uuid4())
    p1, p2, _ = _patch_repos(active=active, latest=None, plan=plan)
    with p1, p2:
        result = await billing.get_quota_renewal(ctx=ctx, pool=object())
    # The card is visible (eligible) so it can show a countdown, but not renewable yet.
    assert result.eligible is True
    assert result.renewable is False
    assert result.plan_name == "Monthly · 2-channel"
    assert result.renewal_opens_in_days is not None


@pytest.mark.asyncio
async def test_create_quota_renewal_rejects_before_window() -> None:
    plan = _paid_plan()
    active = _license(plan.id, expires_in_days=20)
    ctx = MagicMock()
    ctx.user_id = str(uuid4())
    with patch.object(
        billing, "_resolve_renewable_license", AsyncMock(return_value=(active, plan))
    ):
        with pytest.raises(billing.ValidationError) as excinfo:
            await billing.create_quota_renewal(ctx=ctx, pool=object())
    assert excinfo.value.details.get("error_code") == "RENEWAL_NOT_YET_OPEN"
