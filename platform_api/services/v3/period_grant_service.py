"""Monthly/daily grants on the shared wallet. Unused grant lots expire; packs do not."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from platform_api.services.billing_calendar import billing_today, next_billing_midnight
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
                    )
            await self._store.zero_lot_remaining(lot["id"])
            touched += 1
        return touched

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

        units = credits_to_units(monthly)
        cycle_days = int(plan.get("billing_cycle_days") or 30)
        expires_at = datetime.now(timezone.utc) + timedelta(days=max(1, cycle_days))

        # Anchor the period to the real subscription when we can. CutLuy web
        # subscribers have no license row, so fall back to their web_subscriptions
        # period; otherwise a same-day plan change collapses onto the calendar date.
        period_start = billing_today()
        ctx = None
        if self._plan_repo is not None:
            ctx = await self._plan_repo.get_user_active_subscription_context(user_id)
        if ctx is not None:
            from platform_api.services.billing_period_service import period_start_for_subscription

            period_start = period_start_for_subscription(
                plan=ctx.plan,
                activated_at=ctx.activated_at,
            )
        else:
            web_period_start = await self._store.get_web_subscription_period_start(user_id)
            if web_period_start is not None:
                period_start = web_period_start

        existing = await self._store.find_period_grant(user_id, period_start)
        if existing is not None:
            # A smaller lot for this period means the user changed plan mid-period
            # (e.g. Free -> paid on the same day). Grow it to the new plan's grant
            # instead of silently skipping the upgrade.
            delta_units = 0
            if int(existing.get("amount_units") or 0) < units:
                delta_units = await self._store.top_up_period_grant(
                    existing["id"],
                    target_units=units,
                    expires_at=expires_at,
                )
            if delta_units <= 0:
                return {
                    "granted": False,
                    "reason": "already_granted",
                    "user_id": str(user_id),
                    "plan_id": plan["id"],
                    "period_start": period_start.isoformat(),
                }
            await self._credit_repo.add_credits(
                user_id,
                delta_units,
                reason="v3_period_grant",
                ref_id=f"grant:{user_id}:{period_start.isoformat()}",
            )
            return {
                "granted": True,
                "reason": "grant_upgraded",
                "user_id": str(user_id),
                "plan_id": plan["id"],
                "credits": units_to_credits(delta_units),
                "amount_units": delta_units,
                "period_start": period_start.isoformat(),
                "expires_at": expires_at.isoformat(),
                "lot_id": str(existing["id"]),
                "balance_credits": units_to_credits(
                    int(await self._credit_repo.get_balance(user_id))
                ),
            }

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
