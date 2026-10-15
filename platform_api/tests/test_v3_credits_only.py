"""Credits-only API v3: same wallet/pricing as v1, new charge path."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from platform_api.exceptions import InsufficientCreditsError, QuotaExceededError
from platform_api.main import create_app
from platform_api.middleware.auth import AuthContext, get_current_user, require_admin
from platform_api.models.domain import Plan
from platform_api.routers.plans import _get_plan_repo
from platform_api.services.credit_units import credits_to_units, units_to_credits
from platform_api.services.v3.credits_only_billing_service import CreditsOnlyBillingService
from platform_api.services.v3.quota_conversion_service import QuotaConversionService
from platform_api.dependencies import (
    get_v3_billing_service,
    get_v3_conversion_service,
    get_v3_grant_service,
    get_v3_store,
)


NOW = datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc)
USER_ID = uuid4()
ADMIN = AuthContext(user_id=str(uuid4()), email="admin@example.com", role="admin")
USER = AuthContext(user_id=str(USER_ID), email="user@example.com", role="user")


class FakePricing:
    def __init__(self) -> None:
        self.prices: dict[tuple[str, str], int] = {
            ("suno", "music"): credits_to_units(7.5),
            ("openai", "lyric"): credits_to_units(5),
        }

    async def get_all_pricing(self) -> list[dict]:
        return [
            {
                "ai_service": service,
                "operation_type": op,
                "credits_per_operation": units,
            }
            for (service, op), units in self.prices.items()
        ]

    async def get_price(self, ai_service: str, operation_type: str, sub_model: str | None = None) -> int:
        try:
            return self.prices[(ai_service, operation_type)]
        except KeyError as exc:
            raise RuntimeError(f"missing {ai_service}/{operation_type}") from exc


class FakeWallet:
    def __init__(self, balance: int = 0) -> None:
        self.balance = balance
        self.txs: list[dict] = []

    async def get_balance(self, user_id: UUID | str) -> int:
        return self.balance

    async def atomic_deduct(self, user_id, amount: int, reason: str, ref_id=None, metadata=None) -> bool:
        if self.balance < amount:
            return False
        self.balance -= amount
        self.txs.append({"kind": "debit", "amount": amount, "reason": reason, "ref_id": ref_id, "metadata": metadata})
        return True

    async def add_credits(self, user_id, amount: int, reason: str, ref_id=None, pack_id=None, payment_ref=None, **kwargs) -> int:
        self.balance += amount
        self.txs.append({"kind": "credit", "amount": amount, "reason": reason, "ref_id": ref_id})
        return self.balance

    async def refund(self, user_id, amount: int, reason: str, ref_id=None, metadata=None) -> None:
        self.balance += amount
        self.txs.append({"kind": "refund", "amount": amount, "reason": reason, "ref_id": ref_id, "metadata": metadata})


class FakeStore:
    def __init__(self) -> None:
        self.plans: dict[str, dict] = {}
        self.user_plan: dict[str, str] = {}
        self.lots: list[dict] = []
        self.applied: set[str] = set()
        self.conversion_runs: list[dict] = []

    async def list_plans(self) -> list[dict]:
        return list(self.plans.values())

    async def list_public_plans(self, *, credits_per_generate: int | float | None = None) -> list[dict]:
        rows = [p for p in self.plans.values() if p.get("is_active") and p.get("is_public")]
        if credits_per_generate is None:
            return rows
        return [{**p, "credits_per_generate": credits_per_generate} for p in rows]

    async def get_plan(self, plan_id: UUID) -> dict | None:
        return self.plans.get(str(plan_id))

    async def get_plan_for_user(self, user_id: UUID) -> dict | None:
        plan_id = self.user_plan.get(str(user_id))
        return self.plans.get(plan_id) if plan_id else None

    async def get_plan_for_web_subscription(self, user_id: UUID) -> dict | None:
        return None

    async def get_active_free_plan(self) -> dict | None:
        for plan in self.plans.values():
            if str(plan.get("name") or "").lower() == "free" and plan.get("is_active"):
                return plan
        return None

    async def resolve_charge_plan(self, user_id: UUID) -> dict | None:
        plan = await self.get_plan_for_user(user_id)
        if plan is not None:
            return plan
        web_plan = await self.get_plan_for_web_subscription(user_id)
        if web_plan is not None and int(web_plan.get("price_cents") or 0) > 0:
            return web_plan
        return await self.get_active_free_plan()

    async def patch_plan(self, plan_id: UUID, fields: dict) -> dict | None:
        plan = self.plans.get(str(plan_id))
        if plan is None:
            return None
        plan.update(fields)
        return plan

    async def list_lots(self, user_id: UUID) -> list[dict]:
        return [lot for lot in self.lots if str(lot["user_id"]) == str(user_id)]

    async def grant_remaining_units(self, user_id: UUID) -> int:
        return sum(
            int(lot["remaining_units"])
            for lot in await self.list_lots(user_id)
            if lot["tag"] == "grant"
        )

    async def insert_lot(self, **kwargs) -> dict:
        lot = {"id": uuid4(), **kwargs}
        self.lots.append(lot)
        return lot

    async def get_applied_conversion(self, user_id: UUID) -> dict | None:
        if str(user_id) in self.applied:
            return {"user_id": str(user_id), "status": "applied"}
        return None

    async def insert_conversion_run(self, **kwargs) -> dict:
        row = {"id": uuid4(), **kwargs}
        self.conversion_runs.append(row)
        if kwargs.get("status") == "applied":
            self.applied.add(str(kwargs["user_id"]))
        return row

    async def list_active_license_users(self) -> list[dict]:
        return [{"user_id": UUID(uid)} for uid in self.user_plan]

    async def expire_unused(self) -> None:
        return None


class FakeEnforcement:
    def __init__(self, used: int = 0, budget: int = 10) -> None:
        self.used = used
        self.budget = budget

    async def enforce_fail_absorb_budget(self, user_id: UUID) -> None:
        if self.budget > 0 and self.used >= self.budget:
            raise QuotaExceededError(
                "Daily fail/retry budget exceeded. Try again tomorrow.",
                details={"fail_absorb_used": self.used, "fail_absorb_budget": self.budget},
            )

    async def record_fail_absorb(self, user_id: UUID) -> int:
        self.used += 1
        return self.used


class FakeUsage:
    def __init__(self, music_used: int = 80) -> None:
        self.music_used = music_used

    async def get_monthly_count(self, user_id, operation_type, period_start) -> int:
        return self.music_used if operation_type == "music" else 0


class FakeTopup:
    def __init__(self, extra: int = 0) -> None:
        self.extra = extra

    async def sum_extra_units(self, user_id, period_start, quota_kind) -> int:
        return self.extra if quota_kind == "music" else 0


class _EmptyPool:
    async def fetch(self, query: str, *args):
        return []


class FakePlanRepo:
    def __init__(self, plan: Plan | None = None, activated_at=None) -> None:
        self.plan = plan
        self.activated_at = activated_at or NOW
        self.plans: dict[UUID, Plan] = {}
        self._pool = _EmptyPool()
        if plan is not None:
            self.plans[plan.id] = plan

    async def get_all(self) -> list[Plan]:
        return list(self.plans.values())

    async def get_subscriber_counts(self, plan_ids: list[UUID]) -> dict[UUID, int]:
        return {}

    async def get_user_active_subscription_context(self, user_id: UUID):
        if self.plan is None:
            return None
        return SimpleNamespace(
            plan=self.plan,
            license_id=uuid4(),
            activated_at=self.activated_at,
            profile_addon_slots=0,
            profile_addon_pending=0,
        )


def _v3_plan(**overrides) -> dict:
    plan_id = overrides.pop("id", uuid4())
    base = {
        "id": str(plan_id),
        "name": "Monthly · 2-channel",
        "price_cents": 7900,
        "billing_cycle_days": 30,
        "profile_allowance": 2,
        "monthly_song_limit": 300,
        "monthly_credits": 0,
        "daily_credits": 0,
        "is_public": False,
        "is_active": True,
        "plan_kind": "subscription",
        "plan_type": "desktop_pro",
        "lyric_credits": None,
        "title_credits": None,
        "album_credits": None,
        "music_credits": None,
        "style_credits": None,
        "image_credits": None,
        "video_credits": None,
        "merge_credits": None,
        "pricing_features": [],
        "pricing_credit_lines": [],
        "created_at": NOW,
        "updated_at": NOW,
    }
    base.update(overrides)
    return base


def _domain_plan(*, monthly_song_limit: int = 300) -> Plan:
    return Plan(
        id=uuid4(),
        name="Monthly · 2-channel",
        price_cents=7900,
        billing_cycle_days=30,
        profile_allowance=2,
        monthly_song_limit=monthly_song_limit,
        is_active=True,
        effective_from=NOW,
        created_at=NOW,
        updated_at=NOW,
    )


@pytest.fixture
def store() -> FakeStore:
    return FakeStore()


@pytest.fixture
def wallet() -> FakeWallet:
    return FakeWallet(balance=credits_to_units(100))


@pytest.fixture
def billing(store: FakeStore, wallet: FakeWallet) -> CreditsOnlyBillingService:
    plan = _v3_plan()
    store.plans[plan["id"]] = plan
    store.user_plan[str(USER_ID)] = plan["id"]
    return CreditsOnlyBillingService(
        store=store,
        credit_repo=wallet,
        pricing_service=FakePricing(),
        enforcement=FakeEnforcement(),
    )


@pytest.mark.asyncio
async def test_quote_falls_back_to_credit_pricing(billing: CreditsOnlyBillingService) -> None:
    quote = await billing.quote(op="music", user_id=USER_ID)
    assert quote.source == "credit_pricing"
    assert quote.amount_credits == 7.5
    assert quote.amount_units == credits_to_units(7.5)


class _RoutingResult:
    def __init__(self, provider: str) -> None:
        self.provider = provider


class FakeRouting:
    """Minimal AIRoutingService stand-in returning a fixed music provider."""

    def __init__(self, provider: str | None) -> None:
        self._provider = provider

    async def resolve(self, operation: str) -> _RoutingResult:
        if self._provider is None:
            raise RuntimeError("no routing")
        return _RoutingResult(self._provider)


@pytest.mark.asyncio
async def test_quote_uses_routed_music_provider_price(
    store: FakeStore, wallet: FakeWallet
) -> None:
    """Selecting camxora_music_api in AI Routing charges its 10-credit row."""
    pricing = FakePricing()
    pricing.prices[("camxora_music_api", "music")] = credits_to_units(10)
    billing = CreditsOnlyBillingService(
        store=store,
        credit_repo=wallet,
        pricing_service=pricing,
        ai_routing_service=FakeRouting("camxora_music_api"),
    )
    quote = await billing.quote(op="music", user_id=USER_ID)
    assert quote.amount_credits == 10
    assert quote.amount_units == credits_to_units(10)


@pytest.mark.asyncio
async def test_quote_falls_back_to_suno_price_when_routing_misses(
    store: FakeStore, wallet: FakeWallet
) -> None:
    """A routing miss keeps the static Suno chain instead of hard-failing."""
    billing = CreditsOnlyBillingService(
        store=store,
        credit_repo=wallet,
        pricing_service=FakePricing(),
        ai_routing_service=FakeRouting(None),
    )
    quote = await billing.quote(op="music", user_id=USER_ID)
    assert quote.amount_credits == 7.5


@pytest.mark.asyncio
async def test_quote_falls_back_when_routed_provider_has_no_price(
    store: FakeStore, wallet: FakeWallet
) -> None:
    """A routed provider without a row falls back to the static chain."""
    billing = CreditsOnlyBillingService(
        store=store,
        credit_repo=wallet,
        pricing_service=FakePricing(),
        ai_routing_service=FakeRouting("camxora_music_api"),
    )
    quote = await billing.quote(op="music", user_id=USER_ID)
    assert quote.amount_credits == 7.5


@pytest.mark.asyncio
async def test_plan_override_ignored(billing: CreditsOnlyBillingService, store: FakeStore) -> None:
    plan_id = store.user_plan[str(USER_ID)]
    store.plans[plan_id]["music_credits"] = 10
    quote = await billing.quote(op="music", user_id=USER_ID)
    assert quote.source == "credit_pricing"
    assert quote.amount_credits == 7.5
    assert quote.amount_units == credits_to_units(7.5)


def test_overlay_plan_list_prices_writes_credits_page_ops() -> None:
    from platform_api.services.v3.list_prices import overlay_plan_list_prices

    plan = {"id": "p1", "name": "Starter", "music_credits": 10, "monthly_credits": 1000}
    out = overlay_plan_list_prices(plan, {"music": 7.5, "lyric": 0.252}, overlay_ops=True)
    assert out["credits_per_generate"] == 7.5
    assert out["music_credits"] == 7.5
    assert out["lyric_credits"] == 0.252


@pytest.mark.asyncio
async def test_quote_scans_credit_pricing_when_named_fallback_misses() -> None:
    class ScanPricing:
        async def get_price(self, ai_service: str, operation_type: str, sub_model: str | None = None) -> int:
            raise RuntimeError(f"missing {ai_service}/{operation_type}")

        async def get_all_pricing(self) -> list[dict]:
            return [
                {
                    "ai_service": "slai",
                    "operation_type": "lyric",
                    "credits_per_operation": credits_to_units(0.252),
                }
            ]

    store = FakeStore()
    plan = _v3_plan()
    store.plans[plan["id"]] = plan
    store.user_plan[str(USER_ID)] = plan["id"]
    billing = CreditsOnlyBillingService(
        store=store,
        credit_repo=FakeWallet(balance=credits_to_units(100)),
        pricing_service=ScanPricing(),
    )
    quote = await billing.quote(op="lyric", user_id=USER_ID)
    assert quote.source == "credit_pricing"
    assert quote.amount_credits == 0.252


@pytest.mark.asyncio
async def test_charge_and_refund_change_shared_wallet(
    billing: CreditsOnlyBillingService, wallet: FakeWallet
) -> None:
    before = wallet.balance
    charged = await billing.charge(user_id=USER_ID, op="lyric")
    assert charged["charged"] is True
    assert wallet.balance == before - credits_to_units(5)
    refunded = await billing.refund(user_id=USER_ID, op="lyric", absorb=True)
    assert refunded["fail_absorb_used"] == 1
    assert wallet.balance == before


@pytest.mark.asyncio
async def test_admin_adjust_visible_on_v3_wallet(store: FakeStore, wallet: FakeWallet) -> None:
    billing = CreditsOnlyBillingService(
        store=store, credit_repo=wallet, pricing_service=FakePricing()
    )
    await wallet.add_credits(USER_ID, credits_to_units(10), reason="admin_adjust")
    view = await billing.wallet_view(USER_ID)
    assert view["balance_credits"] == units_to_credits(wallet.balance)
    assert view["reset_label"] is None


@pytest.mark.asyncio
async def test_wallet_view_uses_free_plan_reset_label(store: FakeStore, wallet: FakeWallet) -> None:
    store.user_plan.clear()
    free = _v3_plan(
        name="Free",
        price_cents=0,
        monthly_credits=50,
        daily_credits=0,
        is_public=True,
        is_active=True,
    )
    store.plans[free["id"]] = free
    billing = CreditsOnlyBillingService(
        store=store, credit_repo=wallet, pricing_service=FakePricing()
    )
    view = await billing.wallet_view(USER_ID)
    assert view["plan"]["name"] == "Free"
    assert view["plan"]["monthly_credits"] == 50
    assert view["plan"]["daily_credits"] == 0
    assert view["reset_label"] == "Credit reset monthly"


@pytest.mark.asyncio
async def test_fail_absorb_blocks_charge(store: FakeStore, wallet: FakeWallet) -> None:
    billing = CreditsOnlyBillingService(
        store=store,
        credit_repo=wallet,
        pricing_service=FakePricing(),
        enforcement=FakeEnforcement(used=3, budget=3),
    )
    with pytest.raises(QuotaExceededError):
        await billing.charge(user_id=USER_ID, op="music")


@pytest.mark.asyncio
async def test_insufficient_credits_is_402(store: FakeStore) -> None:
    wallet = FakeWallet(balance=0)
    plan = _v3_plan(music_credits=10)
    store.plans[plan["id"]] = plan
    store.user_plan[str(USER_ID)] = plan["id"]
    billing = CreditsOnlyBillingService(
        store=store, credit_repo=wallet, pricing_service=FakePricing(), enforcement=FakeEnforcement()
    )
    with pytest.raises(InsufficientCreditsError) as exc:
        await billing.charge(user_id=USER_ID, op="music")
    assert exc.value.status_code == 402


@pytest.mark.asyncio
async def test_leftover_formula_uses_plan_row_not_addons() -> None:
    plan = _domain_plan(monthly_song_limit=300)
    store = FakeStore()
    wallet = FakeWallet()
    service = QuotaConversionService(
        store=store,
        credit_repo=wallet,
        plan_repo=FakePlanRepo(plan),
        usage_repo=FakeUsage(music_used=80),
        topup_repo=FakeTopup(extra=0),
    )
    preview = await service.preview_user(USER_ID)
    assert preview["leftover_packages"] == 220
    assert preview["credits_to_mint"] == 2200


@pytest.mark.asyncio
async def test_conversion_apply_is_idempotent() -> None:
    plan = _domain_plan(monthly_song_limit=300)
    store = FakeStore()
    wallet = FakeWallet()
    service = QuotaConversionService(
        store=store,
        credit_repo=wallet,
        plan_repo=FakePlanRepo(plan),
        usage_repo=FakeUsage(music_used=80),
        topup_repo=FakeTopup(),
    )
    first = await service.apply([USER_ID], confirm=True)
    second = await service.apply([USER_ID], confirm=True)
    assert first[0]["status"] == "applied"
    assert second[0]["status"] == "already_applied"
    assert wallet.balance == credits_to_units(2200)


@pytest.mark.asyncio
async def test_v3_routes_and_v1_public_shape_unchanged() -> None:
    store = FakeStore()
    wallet = FakeWallet(balance=credits_to_units(40))
    pricing = FakePricing()
    hidden = _v3_plan(is_public=False, is_active=True, name="Monthly · 2-channel")
    public = _v3_plan(is_public=True, is_active=True, name="Starter", price_cents=1000, monthly_credits=1000)
    store.plans[hidden["id"]] = hidden
    store.plans[public["id"]] = public
    store.user_plan[str(USER_ID)] = hidden["id"]
    billing = CreditsOnlyBillingService(
        store=store, credit_repo=wallet, pricing_service=pricing, enforcement=FakeEnforcement()
    )

    v1_hidden = _domain_plan()
    v1_hidden.is_public = False
    v1_public_plan = _domain_plan()
    v1_public_plan.id = uuid4()
    v1_public_plan.name = "Starter"
    v1_public_plan.price_cents = 1000
    v1_public_plan.is_public = True
    v1_repo = FakePlanRepo(v1_public_plan)
    v1_repo.plans[v1_hidden.id] = v1_hidden
    v1_repo.plans[v1_public_plan.id] = v1_public_plan

    async def _expire(_user_id):
        return 0

    async def _daily(_user_id):
        return {"granted": False, "reason": "test_noop"}

    async def _period(_user_id):
        return {"granted": False, "reason": "test_noop"}

    grants = SimpleNamespace(
        expire_lapsed_lots=_expire,
        ensure_daily_grant=_daily,
        ensure_period_grant=_period,
    )

    app = create_app()
    app.dependency_overrides[get_v3_store] = lambda: store
    app.dependency_overrides[get_v3_billing_service] = lambda: billing
    app.dependency_overrides[get_v3_grant_service] = lambda: grants
    app.dependency_overrides[get_v3_conversion_service] = lambda: SimpleNamespace()
    app.dependency_overrides[_get_plan_repo] = lambda: v1_repo
    app.dependency_overrides[require_admin] = lambda: ADMIN
    app.dependency_overrides[get_current_user] = lambda: USER

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        v1_public = await client.get("/api/v1/plans/public")
        assert v1_public.status_code == 200
        v1_names = {row["name"] for row in v1_public.json()}
        assert v1_names == {"Starter"}
        v1_item = v1_public.json()[0]
        assert "monthly_song_limit" in v1_item
        assert "music_credits" not in v1_item
        assert "pricing_features" in v1_item
        assert "pricing_credit_lines" in v1_item

        v3_public = await client.get("/api/v3/plans/public")
        assert v3_public.status_code == 200
        names = {row["name"] for row in v3_public.json()}
        assert names == {"Starter"}

        listed = await client.get("/api/v3/plans")
        assert listed.status_code == 200
        assert {row["name"] for row in listed.json()} == {"Monthly · 2-channel", "Starter"}

        patched = await client.patch(
            f"/api/v3/admin/plans/{hidden['id']}",
            json={
                "music_credits": 10,
                "monthly_credits": 3000,
                "pricing_features": ["Web Create", "Custom desktop perk"],
                "pricing_credit_lines": ["credits per month", "Custom song hint"],
            },
        )
        assert patched.status_code == 200
        assert patched.json()["pricing_features"] == ["Web Create", "Custom desktop perk"]
        assert patched.json()["pricing_credit_lines"] == ["credits per month", "Custom song hint"]
        quote = await client.post("/api/v3/billing/quote", json={"op": "music"})
        assert quote.status_code == 200
        assert quote.json()["amount_credits"] == 7.5
        assert quote.json()["source"] == "credit_pricing"

        v3_item = v3_public.json()[0]
        assert v3_item.get("credits_per_generate") == 7.5

        wallet.balance = credits_to_units(50)
        me = await client.get("/api/v3/me/credits")
        assert me.status_code == 200
        assert me.json()["balance_credits"] == 50

        docs = await client.get("/api/v3/docs")
        assert docs.status_code == 200
        openapi = await client.get("/api/v3/openapi.json")
        assert openapi.status_code == 200
        assert all(path.startswith("/api/v3") for path in openapi.json()["paths"])


@pytest.mark.asyncio
async def test_get_plan_for_user_qualifies_joined_id() -> None:
    from platform_api.services.v3.store import V3BillingStore

    class RecordingPool:
        sql = ""

        async def fetchrow(self, sql: str, *_args: object) -> None:
            self.sql = sql
            return None

    pool = RecordingPool()
    await V3BillingStore(pool).get_plan_for_user(USER_ID)
    assert "p.id" in pool.sql
    assert "INNER JOIN licenses" in pool.sql
    assert "SELECT\n            id," not in pool.sql
