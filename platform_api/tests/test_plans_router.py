"""Tests for the plans router admin endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from platform_api.exceptions import ValidationError
from platform_api.main import create_app
from platform_api.middleware.auth import AuthContext, require_admin
from platform_api.models.domain import Plan
from platform_api.routers.plans import _get_plan_repo


ADMIN_CONTEXT = AuthContext(user_id=str(uuid4()), email="admin@example.com", role="admin")
NOW = datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)


def _make_plan(name: str = "Monthly", *, plan_kind: str = "subscription", profile_allowance: int = 2, price_cents: int = 7900) -> Plan:
    return Plan(
        id=uuid4(),
        name=name,
        price_cents=price_cents,
        billing_cycle_days=30,
        profile_allowance=profile_allowance,
        monthly_song_limit=420,
        monthly_image_limit=120,
        daily_song_limit_per_channel=7,
        daily_image_limit_per_channel=7,
        is_active=True,
        plan_kind=plan_kind,
        effective_from=NOW,
        created_at=NOW,
        updated_at=NOW,
    )


class FakePlanRepo:
    def __init__(self) -> None:
        self.plans: dict[UUID, Plan] = {}
        self.subscriber_counts: dict[UUID, int] = {}
        self.deleted_ids: list[UUID] = []

    async def get_all(self) -> list[Plan]:
        return list(self.plans.values())

    async def create(self, **kwargs) -> Plan:
        plan = _make_plan(kwargs.get("name", "Created"))
        self.plans[plan.id] = plan
        return plan

    async def get_by_id(self, plan_id: UUID) -> Plan | None:
        return self.plans.get(plan_id)

    async def update(self, plan_id: UUID, **fields) -> Plan | None:
        plan = self.plans.get(plan_id)
        if plan is None:
            return None
        for key, value in fields.items():
            setattr(plan, key, value)
        return plan

    async def get_subscriber_counts(self, plan_ids: list[UUID]) -> dict[UUID, int]:
        return {
            plan_id: self.subscriber_counts.get(plan_id, 0)
            for plan_id in plan_ids
            if self.subscriber_counts.get(plan_id, 0) > 0
        }

    async def delete_if_no_subscribers(self, plan_id: UUID) -> bool:
        plan = self.plans.get(plan_id)
        if plan is None:
            return False

        subscriber_count = self.subscriber_counts.get(plan_id, 0)
        if subscriber_count > 0:
            raise ValidationError(
                message="Cannot permanently delete a plan that has subscribed users.",
                details={
                    "plan_id": str(plan_id),
                    "subscriber_count": subscriber_count,
                },
            )

        self.deleted_ids.append(plan_id)
        self.plans.pop(plan_id, None)
        self.subscriber_counts.pop(plan_id, None)
        return True


@pytest.fixture
def fake_plan_repo() -> FakePlanRepo:
    return FakePlanRepo()


@pytest.fixture
def app(fake_plan_repo: FakePlanRepo):
    application = create_app()
    application.dependency_overrides[_get_plan_repo] = lambda: fake_plan_repo
    application.dependency_overrides[require_admin] = lambda: ADMIN_CONTEXT
    yield application
    application.dependency_overrides.clear()


@pytest.fixture
async def client(app) -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestListPlans:
    async def test_includes_subscriber_count_and_can_delete(
        self,
        client: AsyncClient,
        fake_plan_repo: FakePlanRepo,
    ) -> None:
        deletable = _make_plan("Deletable")
        in_use = _make_plan("In Use")
        fake_plan_repo.plans[deletable.id] = deletable
        fake_plan_repo.plans[in_use.id] = in_use
        fake_plan_repo.subscriber_counts[in_use.id] = 2

        response = await client.get("/api/v1/plans")

        assert response.status_code == 200
        data = response.json()
        by_name = {item["name"]: item for item in data}
        assert by_name["Deletable"]["subscriber_count"] == 0
        assert by_name["Deletable"]["can_delete"] is True
        assert by_name["In Use"]["subscriber_count"] == 2
        assert by_name["In Use"]["can_delete"] is False


class TestPublicProfileAddonQuote:
    async def test_returns_live_quote_from_two_channel_base(
        self,
        client: AsyncClient,
        fake_plan_repo: FakePlanRepo,
    ) -> None:
        base = _make_plan("Monthly · 2-channel")
        addon = _make_plan("Add-on · +2 channels", plan_kind="profile_addon", profile_allowance=2, price_cents=7900)
        addon.is_public = True
        fake_plan_repo.plans[base.id] = base
        fake_plan_repo.plans[addon.id] = addon

        response = await client.get(
            "/api/v1/plans/public/profile-addon-quote",
            params={"current_channels": 2},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["current_channels"] == 2
        assert data["addon_channels"] == 2
        assert data["new_total_channels"] == 4
        assert data["monthly_addon_cents"] == 7900
        assert data["two_channel_block_cents"] == 7900
        assert data["linear_plan_monthly_cents"] == 7900
        assert data["addon_plan_id"] == str(addon.id)
        assert data["base_plan_id"] == str(base.id)


class TestDeletePlan:
    async def test_deletes_plan_when_no_subscribers(
        self,
        client: AsyncClient,
        fake_plan_repo: FakePlanRepo,
    ) -> None:
        plan = _make_plan("Disposable")
        fake_plan_repo.plans[plan.id] = plan

        response = await client.delete(f"/api/v1/plans/{plan.id}")

        assert response.status_code == 204
        assert plan.id in fake_plan_repo.deleted_ids
        assert plan.id not in fake_plan_repo.plans

    async def test_rejects_delete_when_plan_has_subscribers(
        self,
        client: AsyncClient,
        fake_plan_repo: FakePlanRepo,
    ) -> None:
        plan = _make_plan("Protected")
        fake_plan_repo.plans[plan.id] = plan
        fake_plan_repo.subscriber_counts[plan.id] = 1

        response = await client.delete(f"/api/v1/plans/{plan.id}")

        assert response.status_code == 422
        data = response.json()
        assert data["error"]["message"] == (
            "Cannot permanently delete a plan that has subscribed users."
        )
        assert data["error"]["details"]["subscriber_count"] == 1
