"""Unit tests for LicenseService.

Tests license creation, assignment, revocation, validation,
daily/monthly quota enforcement, plan offers, and plan deactivation
using in-memory fakes for the repositories.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from platform_api.exceptions import (
    DuplicateError,
    LicenseExpiredError,
    NotFoundError,
    QuotaExceededError,
    ValidationError,
)
from platform_api.models.domain import License, Plan
from platform_api.models.enums import LicenseStatus
from platform_api.services.license_service import LicenseService


# ---------------------------------------------------------------------------
# Fakes / In-memory implementations
# ---------------------------------------------------------------------------


class FakeLicenseRepository:
    """In-memory license repository for testing."""

    def __init__(self) -> None:
        self._licenses: dict[UUID, License] = {}
        self._duplicates: dict[tuple[UUID, UUID], bool] = {}

    async def create(self, plan_id: UUID) -> License:
        license = License(
            id=uuid4(),
            license_key="fake-key-" + str(uuid4())[:8],
            plan_id=plan_id,
            status=LicenseStatus.UNASSIGNED,
            created_at=datetime.now(timezone.utc),
        )
        self._licenses[license.id] = license
        return license

    async def get_by_id(self, license_id: UUID) -> License | None:
        return self._licenses.get(license_id)

    async def assign_to_user(
        self, license_id: UUID, user_id: UUID, plan: Plan
    ) -> License:
        license = self._licenses[license_id]
        license.user_id = user_id
        license.status = LicenseStatus.ACTIVE
        license.activated_at = datetime.now(timezone.utc)
        if plan.billing_cycle_days is not None:
            license.expires_at = datetime.now(timezone.utc) + timedelta(
                days=plan.billing_cycle_days
            )
        return license

    async def revoke(self, license_id: UUID) -> bool:
        license = self._licenses.get(license_id)
        if license is None or license.status == LicenseStatus.REVOKED:
            return False
        license.status = LicenseStatus.REVOKED
        license.revoked_at = datetime.now(timezone.utc)
        return True

    async def get_active_for_user(self, user_id: UUID) -> License | None:
        for lic in self._licenses.values():
            if (
                lic.user_id == user_id
                and lic.status == LicenseStatus.ACTIVE
            ):
                # Return active licenses even if expired - let the service
                # layer handle expiration checks (Req 4.8)
                return lic
        return None

    async def has_duplicate_plan(self, user_id: UUID, plan_id: UUID) -> bool:
        key = (user_id, plan_id)
        if key in self._duplicates:
            return self._duplicates[key]
        for lic in self._licenses.values():
            if (
                lic.user_id == user_id
                and lic.plan_id == plan_id
                and lic.status == LicenseStatus.ACTIVE
            ):
                return True
        return False


class FakePlanRepository:
    """In-memory plan repository for testing."""

    def __init__(self) -> None:
        self._plans: dict[UUID, Plan] = {}
        self._usage: dict[tuple[UUID, UUID], int] = {}

    async def get_by_id(self, plan_id: UUID) -> Plan | None:
        return self._plans.get(plan_id)

    async def get_or_create_usage(
        self, user_id: UUID, license_id: UUID, period_start: date, period_end: date
    ) -> dict:
        key = (user_id, license_id)
        songs_used = self._usage.get(key, 0)
        return {
            "id": uuid4(),
            "user_id": user_id,
            "license_id": license_id,
            "period_start": period_start,
            "period_end": period_end,
            "songs_used": songs_used,
        }

    async def get_current_usage(self, user_id: UUID, license_id: UUID) -> int:
        return self._usage.get((user_id, license_id), 0)

    def set_usage(self, user_id: UUID, license_id: UUID, count: int) -> None:
        self._usage[(user_id, license_id)] = count


class FakeCreditRepository:
    """In-memory credit repository for testing."""

    def __init__(self) -> None:
        self.credits_added: list[tuple[UUID, int, str, str | None]] = []

    async def add_credits(
        self, user_id: UUID, amount: int, reason: str, ref_id: str | None = None
    ) -> int:
        self.credits_added.append((user_id, amount, reason, ref_id))
        return amount


class FakeOfferRepository:
    """In-memory offer repository for testing."""

    def __init__(self) -> None:
        self._offers: dict[UUID, dict] = {}

    async def get_active_offers_for_plan(self, plan_id: UUID) -> list[dict]:
        return [
            o for o in self._offers.values()
            if o["plan_id"] == plan_id and o["is_active"]
        ]

    async def get_offer_by_id(self, offer_id: UUID) -> dict | None:
        return self._offers.get(offer_id)

    async def increment_redemption(self, offer_id: UUID) -> dict | None:
        offer = self._offers.get(offer_id)
        if offer is None:
            return None
        offer["current_redemptions"] += 1
        return offer

    async def deactivate_offer(self, offer_id: UUID) -> None:
        offer = self._offers.get(offer_id)
        if offer is not None:
            offer["is_active"] = False

    def add_offer(
        self,
        plan_id: UUID,
        promo_price_cents: int = 99900,
        max_redemptions: int = 50,
        current_redemptions: int = 0,
    ) -> UUID:
        offer_id = uuid4()
        self._offers[offer_id] = {
            "id": offer_id,
            "plan_id": plan_id,
            "promo_price_cents": promo_price_cents,
            "max_redemptions": max_redemptions,
            "current_redemptions": current_redemptions,
            "is_active": True,
        }
        return offer_id


class FakeDailyUsageRepository:
    """In-memory daily usage repository for testing."""

    def __init__(self) -> None:
        self._counts: dict[tuple[UUID, date], int] = {}

    async def get_daily_song_count(self, user_id: UUID, day: date) -> int:
        return self._counts.get((user_id, day), 0)

    async def get_daily_song_count_per_channel(
        self, user_id: UUID, channel_count: int, day: date
    ) -> int:
        total = self._counts.get((user_id, day), 0)
        return total // max(channel_count, 1)

    def set_daily_count(self, user_id: UUID, day: date, count: int) -> None:
        self._counts[(user_id, day)] = count


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_plan(
    plan_id: UUID | None = None,
    name: str = "monthly",
    price_cents: int = 7900,
    billing_cycle_days: int | None = 30,
    profile_allowance: int = 2,
    monthly_song_quota: int | None = 420,
    daily_song_limit_per_channel: int = 7,
    is_active: bool = True,
) -> Plan:
    return Plan(
        id=plan_id or uuid4(),
        name=name,
        price_cents=price_cents,
        billing_cycle_days=billing_cycle_days,
        profile_allowance=profile_allowance,
        monthly_song_quota=monthly_song_quota,
        daily_song_limit_per_channel=daily_song_limit_per_channel,
        is_active=is_active,
        effective_from=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def license_repo() -> FakeLicenseRepository:
    return FakeLicenseRepository()


@pytest.fixture
def plan_repo() -> FakePlanRepository:
    return FakePlanRepository()


@pytest.fixture
def credit_repo() -> FakeCreditRepository:
    return FakeCreditRepository()


@pytest.fixture
def offer_repo() -> FakeOfferRepository:
    return FakeOfferRepository()


@pytest.fixture
def daily_usage_repo() -> FakeDailyUsageRepository:
    return FakeDailyUsageRepository()


@pytest.fixture
def service(
    license_repo: FakeLicenseRepository,
    plan_repo: FakePlanRepository,
    credit_repo: FakeCreditRepository,
    offer_repo: FakeOfferRepository,
    daily_usage_repo: FakeDailyUsageRepository,
) -> LicenseService:
    return LicenseService(
        license_repo=license_repo,
        plan_repo=plan_repo,
        credit_repo=credit_repo,
        offer_repo=offer_repo,
        daily_usage_repo=daily_usage_repo,
    )


# ---------------------------------------------------------------------------
# Tests: create_license
# ---------------------------------------------------------------------------


class TestCreateLicense:
    """Tests for LicenseService.create_license."""

    async def test_creates_license_for_active_plan(
        self, service: LicenseService, plan_repo: FakePlanRepository
    ) -> None:
        plan = _make_plan()
        plan_repo._plans[plan.id] = plan

        result = await service.create_license(plan.id)

        assert result.plan_id == plan.id
        assert result.status == LicenseStatus.UNASSIGNED
        assert result.user_id is None

    async def test_raises_not_found_for_nonexistent_plan(
        self, service: LicenseService
    ) -> None:
        with pytest.raises(NotFoundError, match="Plan not found"):
            await service.create_license(uuid4())

    async def test_raises_validation_for_inactive_plan(
        self, service: LicenseService, plan_repo: FakePlanRepository
    ) -> None:
        plan = _make_plan(is_active=False)
        plan_repo._plans[plan.id] = plan

        with pytest.raises(ValidationError, match="inactive plan"):
            await service.create_license(plan.id)


# ---------------------------------------------------------------------------
# Tests: assign_license
# ---------------------------------------------------------------------------


class TestAssignLicense:
    """Tests for LicenseService.assign_license."""

    async def test_assigns_license_to_user(
        self,
        service: LicenseService,
        license_repo: FakeLicenseRepository,
        plan_repo: FakePlanRepository,
    ) -> None:
        plan = _make_plan()
        plan_repo._plans[plan.id] = plan
        license = await license_repo.create(plan.id)
        user_id = uuid4()

        result = await service.assign_license(license.id, user_id)

        assert result.user_id == user_id
        assert result.status == LicenseStatus.ACTIVE
        assert result.activated_at is not None

    async def test_sets_expiration_for_monthly_plan(
        self,
        service: LicenseService,
        license_repo: FakeLicenseRepository,
        plan_repo: FakePlanRepository,
    ) -> None:
        plan = _make_plan(billing_cycle_days=30)
        plan_repo._plans[plan.id] = plan
        license = await license_repo.create(plan.id)
        user_id = uuid4()

        result = await service.assign_license(license.id, user_id)

        assert result.expires_at is not None

    async def test_no_expiration_for_lifetime_plan(
        self,
        service: LicenseService,
        license_repo: FakeLicenseRepository,
        plan_repo: FakePlanRepository,
    ) -> None:
        plan = _make_plan(name="lifetime", billing_cycle_days=None)
        plan_repo._plans[plan.id] = plan
        license = await license_repo.create(plan.id)
        user_id = uuid4()

        result = await service.assign_license(license.id, user_id)

        assert result.expires_at is None

    async def test_credits_lifetime_bonus(
        self,
        service: LicenseService,
        license_repo: FakeLicenseRepository,
        plan_repo: FakePlanRepository,
        credit_repo: FakeCreditRepository,
    ) -> None:
        plan = _make_plan(name="lifetime", billing_cycle_days=None)
        plan_repo._plans[plan.id] = plan
        license = await license_repo.create(plan.id)
        user_id = uuid4()

        await service.assign_license(license.id, user_id)

        assert len(credit_repo.credits_added) == 1
        _, amount, reason, ref_id = credit_repo.credits_added[0]
        assert amount == 1000
        assert reason == "lifetime_bonus"

    async def test_raises_not_found_for_nonexistent_license(
        self, service: LicenseService
    ) -> None:
        with pytest.raises(NotFoundError, match="License not found"):
            await service.assign_license(uuid4(), uuid4())

    async def test_raises_validation_for_already_assigned_license(
        self,
        service: LicenseService,
        license_repo: FakeLicenseRepository,
        plan_repo: FakePlanRepository,
    ) -> None:
        plan = _make_plan()
        plan_repo._plans[plan.id] = plan
        license = await license_repo.create(plan.id)
        # Manually set to active
        license.status = LicenseStatus.ACTIVE

        with pytest.raises(ValidationError, match="not in unassigned state"):
            await service.assign_license(license.id, uuid4())

    async def test_raises_validation_for_inactive_plan(
        self,
        service: LicenseService,
        license_repo: FakeLicenseRepository,
        plan_repo: FakePlanRepository,
    ) -> None:
        plan = _make_plan(is_active=False)
        plan_repo._plans[plan.id] = plan
        license = await license_repo.create(plan.id)

        with pytest.raises(ValidationError, match="inactive plan"):
            await service.assign_license(license.id, uuid4())

    async def test_raises_duplicate_for_same_plan_type(
        self,
        service: LicenseService,
        license_repo: FakeLicenseRepository,
        plan_repo: FakePlanRepository,
    ) -> None:
        plan = _make_plan()
        plan_repo._plans[plan.id] = plan
        user_id = uuid4()

        # Create and assign first license
        lic1 = await license_repo.create(plan.id)
        await service.assign_license(lic1.id, user_id)

        # Try to assign second license of same plan
        lic2 = await license_repo.create(plan.id)
        with pytest.raises(DuplicateError, match="already has an active"):
            await service.assign_license(lic2.id, user_id)


# ---------------------------------------------------------------------------
# Tests: revoke_license
# ---------------------------------------------------------------------------


class TestRevokeLicense:
    """Tests for LicenseService.revoke_license."""

    async def test_revokes_active_license(
        self,
        service: LicenseService,
        license_repo: FakeLicenseRepository,
        plan_repo: FakePlanRepository,
    ) -> None:
        plan = _make_plan()
        plan_repo._plans[plan.id] = plan
        license = await license_repo.create(plan.id)
        user_id = uuid4()
        await service.assign_license(license.id, user_id)

        result = await service.revoke_license(license.id)

        assert result.status == LicenseStatus.REVOKED
        assert result.revoked_at is not None

    async def test_raises_not_found_for_nonexistent_license(
        self, service: LicenseService
    ) -> None:
        with pytest.raises(NotFoundError, match="License not found"):
            await service.revoke_license(uuid4())


# ---------------------------------------------------------------------------
# Tests: validate_license
# ---------------------------------------------------------------------------


class TestValidateLicense:
    """Tests for LicenseService.validate_license."""

    async def test_returns_plan_details_for_active_license(
        self,
        service: LicenseService,
        license_repo: FakeLicenseRepository,
        plan_repo: FakePlanRepository,
    ) -> None:
        plan = _make_plan(
            name="monthly",
            profile_allowance=2,
            monthly_song_quota=420,
            daily_song_limit_per_channel=7,
        )
        plan_repo._plans[plan.id] = plan
        license = await license_repo.create(plan.id)
        user_id = uuid4()
        await service.assign_license(license.id, user_id)

        result = await service.validate_license(user_id)

        assert result["plan_type"] == "monthly"
        assert result["profile_allowance"] == 2
        assert result["monthly_song_quota"] == 420
        assert result["songs_remaining"] == 420
        assert result["daily_song_limit_per_channel"] == 7
        assert result["license_status"] == "active"
        assert result["expiration_date"] is not None

    async def test_calculates_songs_remaining(
        self,
        service: LicenseService,
        license_repo: FakeLicenseRepository,
        plan_repo: FakePlanRepository,
    ) -> None:
        plan = _make_plan(monthly_song_quota=420)
        plan_repo._plans[plan.id] = plan
        license = await license_repo.create(plan.id)
        user_id = uuid4()
        await service.assign_license(license.id, user_id)

        # Set some usage
        plan_repo.set_usage(user_id, license.id, 100)

        result = await service.validate_license(user_id)

        assert result["songs_remaining"] == 320

    async def test_lifetime_plan_has_no_monthly_quota(
        self,
        service: LicenseService,
        license_repo: FakeLicenseRepository,
        plan_repo: FakePlanRepository,
    ) -> None:
        plan = _make_plan(
            name="lifetime",
            billing_cycle_days=None,
            monthly_song_quota=None,
        )
        plan_repo._plans[plan.id] = plan
        license = await license_repo.create(plan.id)
        user_id = uuid4()
        await service.assign_license(license.id, user_id)

        result = await service.validate_license(user_id)

        assert result["monthly_song_quota"] is None
        assert result["songs_remaining"] is None
        assert result["expiration_date"] is None

    async def test_raises_not_found_for_no_active_license(
        self, service: LicenseService
    ) -> None:
        with pytest.raises(NotFoundError, match="No active license"):
            await service.validate_license(uuid4())

    async def test_raises_expired_for_expired_license(
        self,
        service: LicenseService,
        license_repo: FakeLicenseRepository,
        plan_repo: FakePlanRepository,
    ) -> None:
        plan = _make_plan(billing_cycle_days=30)
        plan_repo._plans[plan.id] = plan
        license = await license_repo.create(plan.id)
        user_id = uuid4()
        await service.assign_license(license.id, user_id)

        # Manually expire the license
        license.expires_at = datetime.now(timezone.utc) - timedelta(days=1)

        with pytest.raises(LicenseExpiredError, match="expired"):
            await service.validate_license(user_id)


# ---------------------------------------------------------------------------
# Tests: check_daily_quota
# ---------------------------------------------------------------------------


class TestCheckDailyQuota:
    """Tests for LicenseService.check_daily_quota."""

    async def test_passes_when_under_limit(
        self,
        service: LicenseService,
        license_repo: FakeLicenseRepository,
        plan_repo: FakePlanRepository,
        daily_usage_repo: FakeDailyUsageRepository,
    ) -> None:
        plan = _make_plan(daily_song_limit_per_channel=7)
        plan_repo._plans[plan.id] = plan
        license = await license_repo.create(plan.id)
        user_id = uuid4()
        await service.assign_license(license.id, user_id)

        # 10 songs used with 2 channels = limit of 14
        daily_usage_repo.set_daily_count(user_id, date.today(), 10)

        # Should not raise
        await service.check_daily_quota(user_id, channel_count=2)

    async def test_raises_quota_exceeded_at_limit(
        self,
        service: LicenseService,
        license_repo: FakeLicenseRepository,
        plan_repo: FakePlanRepository,
        daily_usage_repo: FakeDailyUsageRepository,
    ) -> None:
        plan = _make_plan(daily_song_limit_per_channel=7)
        plan_repo._plans[plan.id] = plan
        license = await license_repo.create(plan.id)
        user_id = uuid4()
        await service.assign_license(license.id, user_id)

        # 14 songs used with 2 channels = at limit of 14
        daily_usage_repo.set_daily_count(user_id, date.today(), 14)

        with pytest.raises(QuotaExceededError, match="Daily") as exc_info:
            await service.check_daily_quota(user_id, channel_count=2)

        assert exc_info.value.details is not None
        assert exc_info.value.details["limit"] == 14
        assert exc_info.value.details["current_usage"] == 14

    async def test_raises_not_found_for_no_license(
        self, service: LicenseService
    ) -> None:
        with pytest.raises(NotFoundError):
            await service.check_daily_quota(uuid4(), channel_count=1)


# ---------------------------------------------------------------------------
# Tests: check_monthly_quota
# ---------------------------------------------------------------------------


class TestCheckMonthlyQuota:
    """Tests for LicenseService.check_monthly_quota."""

    async def test_passes_when_under_quota(
        self,
        service: LicenseService,
        license_repo: FakeLicenseRepository,
        plan_repo: FakePlanRepository,
    ) -> None:
        plan = _make_plan(monthly_song_quota=420)
        plan_repo._plans[plan.id] = plan
        license = await license_repo.create(plan.id)
        user_id = uuid4()
        await service.assign_license(license.id, user_id)

        plan_repo.set_usage(user_id, license.id, 200)

        # Should not raise
        await service.check_monthly_quota(user_id)

    async def test_raises_quota_exceeded_at_limit(
        self,
        service: LicenseService,
        license_repo: FakeLicenseRepository,
        plan_repo: FakePlanRepository,
    ) -> None:
        plan = _make_plan(monthly_song_quota=420)
        plan_repo._plans[plan.id] = plan
        license = await license_repo.create(plan.id)
        user_id = uuid4()
        await service.assign_license(license.id, user_id)

        plan_repo.set_usage(user_id, license.id, 420)

        with pytest.raises(QuotaExceededError, match="Monthly") as exc_info:
            await service.check_monthly_quota(user_id)

        assert exc_info.value.details is not None
        assert exc_info.value.details["limit"] == 420
        assert exc_info.value.details["current_usage"] == 420

    async def test_lifetime_plan_skips_quota_check(
        self,
        service: LicenseService,
        license_repo: FakeLicenseRepository,
        plan_repo: FakePlanRepository,
    ) -> None:
        plan = _make_plan(
            name="lifetime",
            billing_cycle_days=None,
            monthly_song_quota=None,
        )
        plan_repo._plans[plan.id] = plan
        license = await license_repo.create(plan.id)
        user_id = uuid4()
        await service.assign_license(license.id, user_id)

        # Should not raise regardless of usage
        await service.check_monthly_quota(user_id)

    async def test_raises_not_found_for_no_license(
        self, service: LicenseService
    ) -> None:
        with pytest.raises(NotFoundError):
            await service.check_monthly_quota(uuid4())


# ---------------------------------------------------------------------------
# Tests: get_plan_offers
# ---------------------------------------------------------------------------


class TestGetPlanOffers:
    """Tests for LicenseService.get_plan_offers."""

    async def test_returns_active_offers(
        self,
        service: LicenseService,
        plan_repo: FakePlanRepository,
        offer_repo: FakeOfferRepository,
    ) -> None:
        plan = _make_plan(name="lifetime")
        plan_repo._plans[plan.id] = plan
        offer_id = offer_repo.add_offer(
            plan.id, promo_price_cents=99900, max_redemptions=50
        )

        result = await service.get_plan_offers(plan.id)

        assert len(result) == 1
        assert result[0]["id"] == offer_id
        assert result[0]["promo_price_cents"] == 99900
        assert result[0]["remaining"] == 50

    async def test_raises_not_found_for_nonexistent_plan(
        self, service: LicenseService
    ) -> None:
        with pytest.raises(NotFoundError, match="Plan not found"):
            await service.get_plan_offers(uuid4())


# ---------------------------------------------------------------------------
# Tests: redeem_offer
# ---------------------------------------------------------------------------


class TestRedeemOffer:
    """Tests for LicenseService.redeem_offer."""

    async def test_increments_redemption_count(
        self,
        service: LicenseService,
        plan_repo: FakePlanRepository,
        offer_repo: FakeOfferRepository,
    ) -> None:
        plan = _make_plan()
        plan_repo._plans[plan.id] = plan
        offer_id = offer_repo.add_offer(plan.id, max_redemptions=50)

        result = await service.redeem_offer(offer_id)

        assert result is True
        offer = offer_repo._offers[offer_id]
        assert offer["current_redemptions"] == 1

    async def test_auto_deactivates_at_max_redemptions(
        self,
        service: LicenseService,
        plan_repo: FakePlanRepository,
        offer_repo: FakeOfferRepository,
    ) -> None:
        plan = _make_plan()
        plan_repo._plans[plan.id] = plan
        offer_id = offer_repo.add_offer(
            plan.id, max_redemptions=2, current_redemptions=1
        )

        await service.redeem_offer(offer_id)

        offer = offer_repo._offers[offer_id]
        assert offer["current_redemptions"] == 2
        assert offer["is_active"] is False

    async def test_raises_not_found_for_nonexistent_offer(
        self, service: LicenseService
    ) -> None:
        with pytest.raises(NotFoundError, match="Offer not found"):
            await service.redeem_offer(uuid4())

    async def test_raises_validation_for_inactive_offer(
        self,
        service: LicenseService,
        plan_repo: FakePlanRepository,
        offer_repo: FakeOfferRepository,
    ) -> None:
        plan = _make_plan()
        plan_repo._plans[plan.id] = plan
        offer_id = offer_repo.add_offer(plan.id, max_redemptions=10)
        offer_repo._offers[offer_id]["is_active"] = False

        with pytest.raises(ValidationError, match="no longer active"):
            await service.redeem_offer(offer_id)

    async def test_raises_validation_for_max_redemptions_reached(
        self,
        service: LicenseService,
        plan_repo: FakePlanRepository,
        offer_repo: FakeOfferRepository,
    ) -> None:
        plan = _make_plan()
        plan_repo._plans[plan.id] = plan
        offer_id = offer_repo.add_offer(
            plan.id, max_redemptions=5, current_redemptions=5
        )

        with pytest.raises(ValidationError, match="maximum redemptions"):
            await service.redeem_offer(offer_id)
