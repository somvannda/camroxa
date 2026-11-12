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
        self._pool = _EmptyPool()

    async def music_credits_spent_today(self, user_id: UUID) -> int:
        return 0

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

    async def live_pack_expiry(self, user_id: UUID):
        return None

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

    async def live_pack_expiry(self, user_id: UUID):
        return None

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

    async def fetchval(self, query: str, *args):
        return False


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


@pytest.mark.asyncio
async def test_studio_ops_price_from_credit_pricing(
    store: FakeStore, wallet: FakeWallet
) -> None:
    """Studio ops have no plan column; their rows in credit_pricing rule."""
    pricing = FakePricing()
    pricing.prices[("suno", "studio_edit")] = credits_to_units(12)
    billing = CreditsOnlyBillingService(
        store=store,
        credit_repo=wallet,
        pricing_service=pricing,
        enforcement=FakeEnforcement(),
    )

    before = wallet.balance
    charged = await billing.charge(user_id=USER_ID, op="studio_edit", ref_id="op-1")

    assert charged["source"] == "credit_pricing"
    assert charged["amount_credits"] == 12
    assert wallet.balance == before - credits_to_units(12)

    refunded = await billing.refund(
        user_id=USER_ID, op="studio_edit", amount_credits=12, ref_id="op-1"
    )
    assert refunded["amount_credits"] == 12
    assert wallet.balance == before


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


class _TextRoutingResult:
    def __init__(self, provider: str | None, sub_model: str | None) -> None:
        self.provider = provider
        self.sub_model = sub_model


class FakeTextRouting:
    """AIRoutingService stand-in returning a provider + sub_model."""

    def __init__(self, provider: str | None, sub_model: str | None) -> None:
        self._provider = provider
        self._sub_model = sub_model

    async def resolve(self, operation: str) -> _TextRoutingResult:
        if self._provider is None:
            raise RuntimeError("no routing")
        return _TextRoutingResult(self._provider, self._sub_model)


class ModelPricing:
    """Pricing fake keyed by (service, operation, model)."""

    def __init__(self, prices: dict[tuple[str, str, str | None], int]) -> None:
        self.prices = prices

    async def get_price(self, ai_service: str, operation_type: str, sub_model: str | None = None) -> int:
        key = (ai_service, operation_type, sub_model or None)
        try:
            return self.prices[key]
        except KeyError as exc:
            raise RuntimeError(f"missing {key}") from exc

    async def get_all_pricing(self) -> list[dict]:
        return [
            {
                "ai_service": service,
                "operation_type": op,
                "sub_model": model or "",
                "credits_per_operation": units,
            }
            for (service, op, model), units in self.prices.items()
        ]


@pytest.mark.asyncio
async def test_quote_text_uses_routed_model_price(
    store: FakeStore, wallet: FakeWallet
) -> None:
    """Lyric routed to SLAI must charge the SLAI row, not a scanned row."""
    pricing = ModelPricing(
        {
            ("openai", "lyric", "gpt-4o-mini"): credits_to_units(0.144),
            ("slai", "lyric", "xiaomi/mimo-v2.5-pro"): credits_to_units(2),
        }
    )
    billing = CreditsOnlyBillingService(
        store=store,
        credit_repo=wallet,
        pricing_service=pricing,
        ai_routing_service=FakeTextRouting("slai", "xiaomi/mimo-v2.5-pro"),
    )

    quote = await billing.quote(
        op="lyric", user_id=USER_ID, operation="lyric"
    )

    assert quote.amount_credits == 2
    assert quote.amount_units == credits_to_units(2)


@pytest.mark.asyncio
async def test_quote_web_music_lyrics_prefers_concrete_assignment(
    store: FakeStore, wallet: FakeWallet
) -> None:
    """web_music_lyrics prices from its own assignment row first."""
    pricing = ModelPricing(
        {
            ("slai", "web_music_lyrics", "gpt-5.6-luna"): credits_to_units(2),
            ("slai", "lyric", "gpt-5.6-luna"): credits_to_units(3),
        }
    )
    billing = CreditsOnlyBillingService(
        store=store,
        credit_repo=wallet,
        pricing_service=pricing,
        ai_routing_service=FakeTextRouting("slai", "gpt-5.6-luna"),
    )

    quote = await billing.quote(
        op="web_music_lyrics",
        user_id=USER_ID,
        operation="web_music_lyrics",
    )

    assert quote.amount_credits == 2


@pytest.mark.asyncio
async def test_quote_text_falls_back_when_routed_model_has_no_row(
    store: FakeStore, wallet: FakeWallet
) -> None:
    """A routed text model without a row keeps the static chain price."""
    billing = CreditsOnlyBillingService(
        store=store,
        credit_repo=wallet,
        pricing_service=FakePricing(),
        ai_routing_service=FakeTextRouting("slai", "unknown-model"),
    )

    quote = await billing.quote(op="lyric", user_id=USER_ID, operation="lyric")

    assert quote.amount_credits == 5


@pytest.mark.asyncio
async def test_settle_executed_charge_refunds_cheaper_model(
    store: FakeStore, wallet: FakeWallet
) -> None:
    """Web-music lyric charged 2, served by openai-mini (216 units) refunds."""
    pricing = ModelPricing(
        {("openai", "lyric", "gpt-4o-mini"): 216}
    )
    billing = CreditsOnlyBillingService(
        store=store,
        credit_repo=wallet,
        pricing_service=pricing,
    )

    settled = await billing.settle_executed_charge(
        user_id=USER_ID,
        op="web_music_lyrics",
        operation="lyric",
        charged_units=credits_to_units(2),
        executed_provider="openai",
        executed_model="gpt-4o-mini",
        routed_provider="slai",
        routed_model="gpt-5.6-luna",
    )

    assert settled == 216
    refund = wallet.txs[-1]
    assert refund["kind"] == "refund"
    assert refund["amount"] == credits_to_units(2) - 216
    assert refund["metadata"]["executed_provider"] == "openai"


@pytest.mark.asyncio
async def test_settle_executed_charge_collects_expensive_model(
    store: FakeStore, wallet: FakeWallet
) -> None:
    pricing = ModelPricing({("openai", "lyric", "gpt-4o"): credits_to_units(1.3334)})
    billing = CreditsOnlyBillingService(
        store=store,
        credit_repo=wallet,
        pricing_service=pricing,
    )

    settled = await billing.settle_executed_charge(
        user_id=USER_ID,
        op="lyric",
        operation="lyric",
        charged_units=credits_to_units(0.5),
        executed_provider="openai",
        executed_model="gpt-4o",
        routed_provider="slai",
        routed_model="xiaomi/mimo-v2.5-pro",
    )

    assert settled == credits_to_units(1.3334)
    debit = wallet.txs[-1]
    assert debit["kind"] == "debit"
    assert debit["amount"] == credits_to_units(1.3334) - credits_to_units(0.5)


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


class _ImageRoutingResult:
    def __init__(self, provider: str | None, sub_model: str | None = None) -> None:
        self.provider = provider
        self.sub_model = sub_model


class FakeImageRouting:
    """Per-operation routing stand-in for the image assignments."""

    def __init__(self, assignments: dict[str, tuple[str, str | None]]) -> None:
        self._assignments = assignments

    async def resolve(self, operation: str) -> _ImageRoutingResult:
        try:
            provider, sub_model = self._assignments[operation]
        except KeyError as exc:
            raise RuntimeError(f"no routing for {operation}") from exc
        return _ImageRoutingResult(provider, sub_model)


class SubModelPricing:
    """Pricing double that honours (service, operation, sub_model) rows."""

    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows

    async def get_all_pricing(self) -> list[dict]:
        return list(self.rows)

    async def get_price(
        self, ai_service: str, operation_type: str, sub_model: str | None = None
    ) -> int:
        for row in self.rows:
            if row["ai_service"] != ai_service:
                continue
            if row["operation_type"] != operation_type:
                continue
            if (row.get("sub_model") or None) != (sub_model or None):
                continue
            return int(row["credits_per_operation"])
        raise RuntimeError(f"missing {ai_service}/{operation_type}/{sub_model}")


def _image_rows() -> list[dict]:
    return [
        # Stale FAL row: the static chain used to charge this 60-credit price
        # even though AI Routing runs SLAI.
        {
            "ai_service": "fal",
            "operation_type": "background_image",
            "sub_model": "flux-pro",
            "credits_per_operation": credits_to_units(60),
        },
        {
            "ai_service": "slai",
            "operation_type": "background_image",
            "sub_model": "cx/gpt-image-2.5",
            "credits_per_operation": credits_to_units(6),
        },
        {
            "ai_service": "slai",
            "operation_type": "thumbnail_image",
            "sub_model": "cx/gpt-image-2.5",
            "credits_per_operation": credits_to_units(8),
        },
    ]


@pytest.mark.asyncio
async def test_image_quote_uses_routed_provider_and_model_price(
    store: FakeStore, wallet: FakeWallet
) -> None:
    """AI Routing picks the price: SLAI background image is 6, not FAL's 60."""
    billing = CreditsOnlyBillingService(
        store=store,
        credit_repo=wallet,
        pricing_service=SubModelPricing(_image_rows()),
        ai_routing_service=FakeImageRouting(
            {"background_image": ("slai", "cx/gpt-image-2.5")}
        ),
    )
    quote = await billing.quote(op="image", user_id=USER_ID)
    assert quote.amount_credits == 6
    assert quote.amount_units == credits_to_units(6)


@pytest.mark.asyncio
async def test_image_quote_prices_the_thumbnail_assignment(
    store: FakeStore, wallet: FakeWallet
) -> None:
    """A thumbnail job bills the thumbnail_image assignment, not background."""
    billing = CreditsOnlyBillingService(
        store=store,
        credit_repo=wallet,
        pricing_service=SubModelPricing(_image_rows()),
        ai_routing_service=FakeImageRouting(
            {
                "background_image": ("slai", "cx/gpt-image-2.5"),
                "thumbnail_image": ("slai", "cx/gpt-image-2.5"),
            }
        ),
    )
    background = await billing.quote(
        op="image", user_id=USER_ID, operation="background_image"
    )
    thumbnail = await billing.quote(
        op="image", user_id=USER_ID, operation="thumbnail_image"
    )
    assert background.amount_credits == 6
    assert thumbnail.amount_credits == 8


@pytest.mark.asyncio
async def test_image_charge_debits_the_routed_price(
    store: FakeStore, wallet: FakeWallet
) -> None:
    billing = CreditsOnlyBillingService(
        store=store,
        credit_repo=wallet,
        pricing_service=SubModelPricing(_image_rows()),
        ai_routing_service=FakeImageRouting(
            {"background_image": ("slai", "cx/gpt-image-2.5")}
        ),
    )
    before = wallet.balance
    charged = await billing.charge(
        user_id=USER_ID, op="image", operation="background_image", product="desktop"
    )
    assert charged["charged"] is True
    assert charged["amount_credits"] == 6
    assert wallet.balance == before - credits_to_units(6)
    assert wallet.txs[-1]["reason"] == "v3_image"


@pytest.mark.asyncio
async def test_image_scan_prefers_the_routed_provider(
    store: FakeStore, wallet: FakeWallet
) -> None:
    """When no exact row matches, the scan must not take another provider's row."""

    class ScanOnlyPricing:
        async def get_price(self, *_args, **_kwargs) -> int:
            raise RuntimeError("no exact row")

        async def get_all_pricing(self) -> list[dict]:
            return _image_rows()

    billing = CreditsOnlyBillingService(
        store=store,
        credit_repo=wallet,
        pricing_service=ScanOnlyPricing(),
        ai_routing_service=FakeImageRouting(
            {"background_image": ("slai", "cx/gpt-image-2.5")}
        ),
    )
    quote = await billing.quote(op="image", user_id=USER_ID)
    assert quote.amount_credits == 6


@pytest.mark.asyncio
async def test_image_quote_keeps_static_chain_without_routing(
    store: FakeStore, wallet: FakeWallet
) -> None:
    """A routing miss still resolves a price instead of hard-failing."""
    billing = CreditsOnlyBillingService(
        store=store,
        credit_repo=wallet,
        pricing_service=SubModelPricing(_image_rows()),
        ai_routing_service=FakeImageRouting({}),
    )
    quote = await billing.quote(op="image", user_id=USER_ID)
    assert quote.amount_credits == 60


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
async def test_charge_records_product_metadata(
    billing: CreditsOnlyBillingService, wallet: FakeWallet
) -> None:
    await billing.charge(
        user_id=USER_ID, op="lyric", product="web_music", model="V6_WILD"
    )
    assert wallet.txs[-1]["metadata"]["product"] == "web_music"
    assert wallet.txs[-1]["metadata"]["model"] == "V6_WILD"

    await billing.refund(user_id=USER_ID, op="lyric", product="web_music")
    assert wallet.txs[-1]["metadata"]["product"] == "web_music"


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
