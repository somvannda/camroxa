"""Monthly/daily grants on the shared wallet. Unused grant lots expire; packs do not."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
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

        # The monthly allowance keys off the billing period. Licensed plans have an
        # activation anchor; a license-less account (the Free plan) does not, so it
        # must key off the calendar month. Keying off `billing_today()` minted a
        # fresh "monthly" grant every day, and since each lot lived for the whole
        # billing cycle the grants stacked — a Free wallet grew ~50/day instead of
        # resetting each month.
        period_start = billing_month_start()
        monthly_allowance = True
        if self._plan_repo is not None:
            ctx = await self._plan_repo.get_user_active_subscription_context(user_id)
            if ctx is not None:
                from platform_api.services.billing_period_service import period_start_for_subscription

                period_start = period_start_for_subscription(
                    plan=ctx.plan,
                    activated_at=ctx.activated_at,
                )
                monthly_allowance = False

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
        if monthly_allowance:
            # Calendar-month allowance: expire at the next billing month start so
            # unused Free credits roll off instead of lingering past the period.
            expires_at = next_billing_month_start(from_date=period_start)
        else:
            cycle_days = int(plan.get("billing_cycle_days") or 30)
            expires_at = datetime.now(timezone.utc) + timedelta(days=max(1, cycle_days))
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

    async def carryover_period_grant(
        self,
        *,
        user_id: UUID,
        monthly_credits: int,
        billing_cycle_days: int,
        new_expires_at: datetime,
    ) -> dict[str, Any]:
        """Roll unused grant credits into the next period on an early renewal.

        The current period's remaining grant is moved into the next period's grant
        together with the new allowance, expiring at the new license expiry. The old
        lots are zeroed (without clawback) so the value is neither lost nor
        double-counted.
        """
        from platform_api.services.billing_period_service import period_start_for_subscription

        cycle_days = max(1, int(billing_cycle_days or 30))
        monthly = max(0, int(monthly_credits or 0))

        ctx = None
        if self._plan_repo is not None:
            ctx = await self._plan_repo.get_user_active_subscription_context(user_id)
        current_start = period_start_for_subscription(
            plan=ctx.plan if ctx is not None else None,
            activated_at=ctx.activated_at if ctx is not None else None,
        )
        next_start = current_start + timedelta(days=cycle_days)

        if await self._store.find_period_grant(user_id, next_start) is not None:
            return {
                "granted": False,
                "reason": "already_granted",
                "period_start": next_start.isoformat(),
            }

        carried = int(await self._store.grant_remaining_units(user_id))
        allowance_units = credits_to_units(monthly)
        if carried <= 0 and allowance_units <= 0:
            return {
                "granted": False,
                "reason": "nothing_to_grant",
                "period_start": next_start.isoformat(),
            }

        for lot in await self._store.list_lots(user_id):
            if str(lot["tag"]) not in ("grant", "daily_grant"):
                continue
            if int(lot["remaining_units"]) <= 0:
                continue
            expires_at = lot.get("expires_at")
            # Only carry lots that are still live; expired lots are clawed back by
            # expire_unused_grants (zeroing them here without a deduction would leak).
            if expires_at is None or expires_at > datetime.now(timezone.utc):
                await self._store.zero_lot_remaining(lot["id"])

        amount_units = carried + allowance_units
        lot = await self._store.insert_lot_if_absent(
            user_id=user_id,
            tag="grant",
            amount_units=amount_units,
            expires_at=new_expires_at,
            period_start=next_start,
        )
        if lot is None:
            return {
                "granted": False,
                "reason": "already_granted",
                "period_start": next_start.isoformat(),
            }

        # The carried units are already in the wallet; only the new allowance is added.
        if allowance_units > 0:
            await self._credit_repo.add_credits(
                user_id,
                allowance_units,
                reason="v3_period_grant",
                ref_id=f"grant:{user_id}:{next_start.isoformat()}",
            )
        return {
            "granted": True,
            "carried_units": carried,
            "carried_credits": units_to_credits(carried),
            "credits": monthly,
            "amount_units": amount_units,
            "period_start": next_start.isoformat(),
            "expires_at": new_expires_at.isoformat(),
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
