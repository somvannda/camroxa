"""Monthly/daily grants on the shared wallet. Unused grant lots expire; packs do not."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from platform_api.services.billing_calendar import (
    billing_month_start,
    billing_today,
    next_billing_midnight,
    next_billing_month_start,
)
from platform_api.services.credit_units import credits_to_units, units_to_credits
from platform_api.services.v3.store import V3BillingStore


class PeriodGrantService:
    def __init__(self, *, store: V3BillingStore, credit_repo: Any, plan_repo: Any | None = None) -> None:
        self._store = store
        self._credit_repo = credit_repo
        self._plan_repo = plan_repo

    async def expire_unused_grants(self, user_id: UUID | None = None) -> int:
        """Deduct leftover grant lots that passed expires_at. Returns users touched."""
        lots = await self._store.expired_grant_lots(user_id)
        touched = 0
        for lot in lots:
            remaining = int(lot["remaining_units"])
            owner = lot["user_id"]
            if remaining > 0:
                balance = int(await self._credit_repo.get_balance(owner))
                clawback = min(remaining, max(0, balance))
                if clawback > 0:
                    await self._credit_repo.atomic_deduct(
                        owner,
                        clawback,
                        "v3_grant_expire",
                        ref_id=str(lot["id"]),
                        metadata={"source": "v3", "tag": "grant", "billing": "grant_expire"},
                        consume_lots=False,
                    )
            await self._store.zero_lot_remaining(lot["id"])
            touched += 1
        return touched

    async def _resolve_period(self, user_id: UUID) -> tuple[date, datetime]:
        """Return a stable (period_start, expires_at) for the user's monthly grant.

        The period must be stable within a billing cycle so the unique
        (user_id, period_start) lot index makes the grant idempotent. Falling
        back to ``billing_today()`` made Free/web-subscription grants re-mint
        every day and stack for 30 days.
        """
        # 1) Desktop license: anchor to the license billing cycle.
        if self._plan_repo is not None:
            ctx = await self._plan_repo.get_user_active_subscription_context(user_id)
            if ctx is not None:
                from platform_api.services.billing_period_service import (
                    period_end_for_subscription,
                    period_start_for_subscription,
                )

                start = period_start_for_subscription(
                    plan=ctx.plan,
                    activated_at=ctx.activated_at,
                )
                end = period_end_for_subscription(plan=ctx.plan, period_start=start)
                return start, next_billing_midnight(from_date=end)

        # 2) Web (CutLuy) subscription: anchor to its current period.
        web_period = None
        getter = getattr(self._store, "web_subscription_period", None)
        if getter is not None:
            web_period = await getter(user_id)
        if web_period is not None:
            start, end = web_period
            return start, end

        # 3) Free / no subscription: one grant per calendar month.
        start = billing_month_start()
        return start, next_billing_month_start(from_date=start)

    async def ensure_period_grant(self, user_id: UUID) -> dict[str, Any]:
        await self.expire_unused_grants(user_id)
        plan = await self._store.resolve_charge_plan(user_id)
        if plan is None:
            return {"granted": False, "reason": "no_active_plan", "user_id": str(user_id)}

        monthly = int(plan.get("monthly_credits") or 0)
        if monthly <= 0:
            return {
                "granted": False,
                "reason": "no_monthly_credits",
                "user_id": str(user_id),
                "plan_id": plan["id"],
            }

        period_start, expires_at = await self._resolve_period(user_id)

        existing = await self._store.find_period_grant(user_id, period_start)
        if existing is not None:
            return {
                "granted": False,
                "reason": "already_granted",
                "user_id": str(user_id),
                "plan_id": plan["id"],
                "period_start": period_start.isoformat(),
            }

        units = credits_to_units(monthly)
        lot = await self._store.insert_lot_if_absent(
            user_id=user_id,
            tag="grant",
            amount_units=units,
            expires_at=expires_at,
            period_start=period_start,
        )
        if lot is None:
            return {
                "granted": False,
                "reason": "already_granted",
                "user_id": str(user_id),
                "plan_id": plan["id"],
                "period_start": period_start.isoformat(),
            }
        await self._credit_repo.add_credits(
            user_id,
            units,
            reason="v3_period_grant",
            ref_id=f"grant:{user_id}:{period_start.isoformat()}",
        )
        return {
            "granted": True,
            "user_id": str(user_id),
            "plan_id": plan["id"],
            "credits": monthly,
            "amount_units": units,
            "period_start": period_start.isoformat(),
            "expires_at": expires_at.isoformat(),
            "lot_id": str(lot["id"]),
            "balance_credits": units_to_credits(int(await self._credit_repo.get_balance(user_id))),
        }

    async def ensure_daily_grant(self, user_id: UUID) -> dict[str, Any]:
        """Mint today's Free-plan daily credits into the shared wallet.

        Paid license / CutLuy rows have daily_credits=0, so they no-op.
        Daily lots expire at the next billing midnight and do not stack.
        """
        await self.expire_unused_grants(user_id)
        plan = await self._store.resolve_charge_plan(user_id)
        if plan is None:
            return {"granted": False, "reason": "no_active_plan", "user_id": str(user_id)}

        daily = int(plan.get("daily_credits") or 0)
        if daily <= 0:
            return {
                "granted": False,
                "reason": "no_daily_credits",
                "user_id": str(user_id),
                "plan_id": plan["id"],
            }

        period_start = billing_today()
        existing = await self._store.find_daily_grant(user_id, period_start)
        if existing is not None:
            return {
                "granted": False,
                "reason": "already_granted",
                "user_id": str(user_id),
                "plan_id": plan["id"],
                "period_start": period_start.isoformat(),
            }

        units = credits_to_units(daily)
        expires_at = next_billing_midnight(from_date=period_start)
        # Lot first: if the unique daily index rejects (or the tag is invalid),
        # the wallet must not move. Crediting first is how Free users stacked 50.
        lot = await self._store.insert_lot_if_absent(
            user_id=user_id,
            tag="daily_grant",
            amount_units=units,
            expires_at=expires_at,
            period_start=period_start,
        )
        if lot is None:
            return {
                "granted": False,
                "reason": "already_granted",
                "user_id": str(user_id),
                "plan_id": plan["id"],
                "period_start": period_start.isoformat(),
            }
        await self._credit_repo.add_credits(
            user_id,
            units,
            reason="v3_daily_grant",
            ref_id=f"daily:{user_id}:{period_start.isoformat()}",
        )
        return {
            "granted": True,
            "user_id": str(user_id),
            "plan_id": plan["id"],
            "credits": daily,
            "amount_units": units,
            "period_start": period_start.isoformat(),
            "expires_at": expires_at.isoformat(),
            "lot_id": str(lot["id"]),
            "balance_credits": units_to_credits(int(await self._credit_repo.get_balance(user_id))),
        }
