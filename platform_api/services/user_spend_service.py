"""Admin User Spent rollup — per-user est. COGS, meters, and alerts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Protocol
from uuid import UUID

from platform_api.models.domain import Plan
from platform_api.services.billing_period_service import period_start_for_subscription
from platform_api.services.cogs_estimate import (
    estimate_cogs_usd,
    prorate_plan_revenue_usd,
)
from platform_api.services.credit_units import DEFAULT_GCV, units_to_credits
from platform_api.services.subscription_entitlement_service import (
    resolve_effective_entitlements,
)

# Free / zero-revenue users only flag margin risk above this USD floor.
FREE_MARGIN_COGS_FLOOR_USD = 1.0

METER_KEYS = ("song", "draft", "image", "video", "merge")


class UserSpendCreditRepo(Protocol):
    async def list_user_spend_cog_rows(
        self,
        *,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        q: str | None = None,
        provider: str | None = None,
        operation: str | None = None,
        plan_id: UUID | None = None,
    ) -> list[dict[str, Any]]: ...

    async def list_active_plans_for_users(
        self, user_ids: list[UUID]
    ) -> dict[UUID, dict[str, Any]]: ...

    async def list_monthly_meters_for_users(
        self, user_ids: list[UUID], *, period_start: Any
    ) -> dict[UUID, dict[str, int]]: ...

    async def get_all(self) -> list[dict[str, Any]]: ...


class ModelCostRepo(Protocol):
    async def get_all(self) -> list[dict[str, Any]]: ...


class SettingsService(Protocol):
    async def get_global_credit_value(self) -> float | None: ...


@dataclass
class MeterStatus:
    used: int = 0
    limit: int | None = None

    @property
    def pct(self) -> float | None:
        if self.limit is None or self.limit <= 0:
            return None
        return min(100.0, (self.used / self.limit) * 100.0)

    @property
    def hot(self) -> bool:
        return self.limit is not None and self.limit > 0 and self.used >= self.limit


@dataclass
class CogBreakdown:
    provider: str
    operation: str
    model: str
    events: int
    plan_included_usd: float
    wallet_usd: float
    est_cogs_usd: float | None
    coverage: str


@dataclass
class UserSpendRow:
    user_id: UUID
    email: str
    display_name: str | None
    plan_id: UUID | None
    plan_name: str
    plan_price_cents: int
    billing_cycle_days: int | None
    plan_revenue_usd: float
    est_cogs_usd: float
    wallet_charged_usd: float
    plan_included_usd: float
    soft_overage_events: int
    meters: dict[str, MeterStatus] = field(default_factory=dict)
    over_allowance: bool = False
    margin_risk: bool = False
    meters_hot: list[str] = field(default_factory=list)
    by_cog: list[CogBreakdown] = field(default_factory=list)


@dataclass
class UserSpendResult:
    items: list[UserSpendRow]
    total: int
    page: int
    page_size: int
    summary: dict[str, Any]


class UserSpendService:
    def __init__(
        self,
        *,
        credit_repo: UserSpendCreditRepo,
        model_cost_repo: ModelCostRepo,
        settings_service: SettingsService,
    ) -> None:
        self._credit_repo = credit_repo
        self._model_cost_repo = model_cost_repo
        self._settings = settings_service

    async def list_user_spend(
        self,
        *,
        page: int = 1,
        page_size: int = 50,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        q: str | None = None,
        plan_id: UUID | None = None,
        provider: str | None = None,
        operation: str | None = None,
        alert: str = "all",
        sort: str = "cogs_desc",
    ) -> UserSpendResult:
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 50

        cog_rows = await self._credit_repo.list_user_spend_cog_rows(
            from_date=from_date,
            to_date=to_date,
            q=q,
            provider=provider,
            operation=operation,
            plan_id=plan_id,
        )

        gcv_raw = await self._settings.get_global_credit_value()
        gcv = float(gcv_raw) if gcv_raw and float(gcv_raw) > 0 else DEFAULT_GCV
        pricing = await self._credit_repo.get_all()
        model_costs = await self._model_cost_repo.get_all()

        users = self._rollup_users(cog_rows, pricing=pricing, model_costs=model_costs, gcv=gcv)

        user_ids = [u.user_id for u in users]
        # Plans are retired: no plan rows to attach. Everyone is reported as
        # Free here; Pro is derived from live pack lots elsewhere.
        plans: dict[UUID, dict[str, Any]] = {}
        await self._attach_plans_and_meters(
            users,
            plans=plans,
            from_date=from_date,
            to_date=to_date,
            gcv=gcv,
        )

        filtered = self._apply_alert_filter(users, alert=alert)
        filtered = self._sort_users(filtered, sort=sort)

        total = len(filtered)
        users_over = sum(1 for u in filtered if u.over_allowance)
        users_margin = sum(1 for u in filtered if u.margin_risk)
        total_cogs = sum(u.est_cogs_usd for u in filtered)
        total_wallet = sum(u.wallet_charged_usd for u in filtered)

        start = (page - 1) * page_size
        page_items = filtered[start : start + page_size]

        return UserSpendResult(
            items=page_items,
            total=total,
            page=page,
            page_size=page_size,
            summary={
                "users_over_allowance": users_over,
                "users_margin_risk": users_margin,
                "total_est_cogs_usd": round(total_cogs, 6),
                "total_wallet_usd": round(total_wallet, 6),
                "gcv": gcv,
            },
        )

    def _rollup_users(
        self,
        cog_rows: list[dict[str, Any]],
        *,
        pricing: list[dict[str, Any]],
        model_costs: list[dict[str, Any]],
        gcv: float,
    ) -> list[UserSpendRow]:
        by_user: dict[UUID, UserSpendRow] = {}
        for row in cog_rows:
            uid = row["user_id"]
            if not isinstance(uid, UUID):
                uid = UUID(str(uid))
            user = by_user.get(uid)
            if user is None:
                user = UserSpendRow(
                    user_id=uid,
                    email=str(row.get("user_email") or ""),
                    display_name=row.get("user_display_name"),
                    plan_id=None,
                    plan_name="Free",
                    plan_price_cents=0,
                    billing_cycle_days=None,
                    plan_revenue_usd=0.0,
                    est_cogs_usd=0.0,
                    wallet_charged_usd=0.0,
                    plan_included_usd=0.0,
                    soft_overage_events=0,
                )
                by_user[uid] = user

            events = int(row.get("events") or 0)
            wallet_units = int(row.get("wallet_charged_units") or 0)
            plan_units = int(row.get("plan_included_list_units") or 0)
            soft = int(row.get("soft_overage_events") or 0)

            wallet_credits = units_to_credits(wallet_units)
            plan_credits = units_to_credits(plan_units)
            wallet_usd = wallet_credits * gcv
            plan_usd = plan_credits * gcv

            provider = str(row.get("provider") or "")
            operation = str(row.get("operation") or "unknown")
            model = str(row.get("model") or "")
            est, coverage = estimate_cogs_usd(
                events=events,
                operation=operation,
                provider=provider or None,
                model=model or None,
                pricing=pricing,
                model_costs=model_costs,
                gcv=gcv,
            )
            est_val = float(est or 0.0)

            user.wallet_charged_usd += wallet_usd
            user.plan_included_usd += plan_usd
            user.est_cogs_usd += est_val
            user.soft_overage_events += soft
            user.by_cog.append(
                CogBreakdown(
                    provider=provider,
                    operation=operation,
                    model=model,
                    events=events,
                    plan_included_usd=round(plan_usd, 6),
                    wallet_usd=round(wallet_usd, 6),
                    est_cogs_usd=round(est_val, 6) if est is not None else None,
                    coverage=coverage,
                )
            )

        for user in by_user.values():
            user.est_cogs_usd = round(user.est_cogs_usd, 6)
            user.wallet_charged_usd = round(user.wallet_charged_usd, 6)
            user.plan_included_usd = round(user.plan_included_usd, 6)
            user.by_cog.sort(
                key=lambda c: (c.est_cogs_usd is None, -(c.est_cogs_usd or 0), c.operation)
            )
        return list(by_user.values())

    async def _attach_plans_and_meters(
        self,
        users: list[UserSpendRow],
        *,
        plans: dict[UUID, dict[str, Any]],
        from_date: datetime | None,
        to_date: datetime | None,
        gcv: float,
    ) -> None:
        del gcv  # reserved if list-value conversion needs it later
        today = date.today()

        # Group users by their billing period start for batched meter reads.
        period_groups: dict[date, list[UUID]] = {}
        for user in users:
            plan_row = plans.get(user.user_id)
            if plan_row is None:
                user.plan_name = "Free"
                user.plan_price_cents = 0
                user.plan_revenue_usd = 0.0
                user.meters = {k: MeterStatus() for k in METER_KEYS}
                user.over_allowance = user.soft_overage_events > 0
                user.meters_hot = []
                user.margin_risk = user.est_cogs_usd > FREE_MARGIN_COGS_FLOOR_USD
                continue

            plan = _plan_from_row(plan_row)
            addon = int(plan_row.get("profile_addon_slots") or 0)
            ents = resolve_effective_entitlements(plan, addon)
            user.plan_id = plan.id
            user.plan_name = plan.name
            user.plan_price_cents = int(plan.price_cents or 0)
            user.billing_cycle_days = plan.billing_cycle_days
            user.plan_revenue_usd = round(
                prorate_plan_revenue_usd(
                    price_cents=user.plan_price_cents,
                    billing_cycle_days=plan.billing_cycle_days,
                    from_date=from_date,
                    to_date=to_date,
                ),
                6,
            )
            user.meters = {
                "song": MeterStatus(limit=ents.monthly_song_limit),
                "draft": MeterStatus(limit=ents.monthly_draft_limit),
                "image": MeterStatus(limit=ents.monthly_image_limit),
                "video": MeterStatus(limit=ents.monthly_video_limit),
                "merge": MeterStatus(limit=ents.monthly_merge_limit),
            }
            period_start = period_start_for_subscription(
                plan=plan,
                activated_at=plan_row.get("activated_at"),
                reference_date=today,
            )
            period_groups.setdefault(period_start, []).append(user.user_id)

        meters_by_user: dict[UUID, dict[str, int]] = {}
        for period_start, uids in period_groups.items():
            batch = await self._credit_repo.list_monthly_meters_for_users(
                uids, period_start=period_start
            )
            meters_by_user.update(batch)

        for user in users:
            if user.plan_id is None:
                continue
            used = meters_by_user.get(user.user_id) or {}
            for key in METER_KEYS:
                meter = user.meters[key]
                meter.used = int(used.get(key) or 0)
            hot = [k for k, m in user.meters.items() if m.hot]
            user.meters_hot = hot
            user.over_allowance = bool(hot) or user.soft_overage_events > 0
            if user.plan_price_cents <= 0:
                user.margin_risk = user.est_cogs_usd > FREE_MARGIN_COGS_FLOOR_USD
            else:
                user.margin_risk = user.est_cogs_usd > user.plan_revenue_usd

    @staticmethod
    def _apply_alert_filter(users: list[UserSpendRow], *, alert: str) -> list[UserSpendRow]:
        key = (alert or "all").strip().lower()
        if key == "over_allowance":
            return [u for u in users if u.over_allowance]
        if key == "margin_risk":
            return [u for u in users if u.margin_risk]
        if key == "healthy":
            return [u for u in users if not u.over_allowance and not u.margin_risk]
        return users

    @staticmethod
    def _sort_users(users: list[UserSpendRow], *, sort: str) -> list[UserSpendRow]:
        key = (sort or "cogs_desc").strip().lower()
        if key == "wallet_desc":
            return sorted(users, key=lambda u: (-u.wallet_charged_usd, -u.est_cogs_usd, u.email))
        if key == "overage_first":
            return sorted(
                users,
                key=lambda u: (
                    0 if u.over_allowance else 1,
                    0 if u.margin_risk else 1,
                    -u.est_cogs_usd,
                    u.email,
                ),
            )
        return sorted(users, key=lambda u: (-u.est_cogs_usd, u.email))


def _plan_from_row(row: dict[str, Any]) -> Plan:
    return Plan(
        id=row["plan_id"],
        name=str(row.get("plan_name") or "Plan"),
        price_cents=int(row.get("price_cents") or 0),
        billing_cycle_days=row.get("billing_cycle_days"),
        profile_allowance=int(row.get("profile_allowance") or 1),
        monthly_song_limit=row.get("monthly_song_limit"),
        monthly_draft_limit=row.get("monthly_draft_limit"),
        monthly_image_limit=row.get("monthly_image_limit"),
        monthly_video_limit=row.get("monthly_video_limit"),
        monthly_merge_limit=row.get("monthly_merge_limit"),
    )
