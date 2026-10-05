"""One-time leftover song-package conversion. Does not multiply by add-on slots."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from platform_api.exceptions import ValidationError
from platform_api.services.billing_period_service import period_start_for_subscription
from platform_api.services.credit_ledger import CreditLedger, GrantType
from platform_api.services.credit_units import credits_to_units, units_to_credits
from platform_api.services.v3.store import V3BillingStore

PACKAGES_TO_CREDITS = 10


class QuotaConversionService:
    def __init__(
        self,
        *,
        store: V3BillingStore,
        credit_repo: Any,
        plan_repo: Any,
        usage_repo: Any,
        topup_repo: Any | None = None,
    ) -> None:
        self._store = store
        self._credit_repo = credit_repo
        self._plan_repo = plan_repo
        self._usage_repo = usage_repo
        self._topup_repo = topup_repo

    async def preview_user(self, user_id: UUID) -> dict[str, Any]:
        applied = await self._store.get_applied_conversion(user_id)
        ctx = await self._plan_repo.get_user_active_subscription_context(user_id)
        if ctx is None:
            return {
                "user_id": str(user_id),
                "bucket": "no_active_license",
                "credits_to_mint": 0,
                "leftover_packages": 0,
                "skipped": True,
                "already_applied": applied is not None,
            }

        plan = ctx.plan
        name = str(getattr(plan, "name", "") or "").lower()
        if "lifetime" in name:
            return {
                "user_id": str(user_id),
                "bucket": "lifetime_skipped",
                "plan_id": str(plan.id),
                "plan_name": plan.name,
                "credits_to_mint": 0,
                "leftover_packages": 0,
                "skipped": True,
                "already_applied": applied is not None,
            }

        period_start = period_start_for_subscription(
            plan=plan,
            activated_at=ctx.activated_at,
        )
        song_limit = int(getattr(plan, "monthly_song_limit", 0) or 0)
        topup = 0
        if self._topup_repo is not None:
            topup = int(
                await self._topup_repo.sum_extra_units(user_id, period_start, "music") or 0
            )
        used = int(await self._usage_repo.get_monthly_count(user_id, "music", period_start) or 0)
        leftover = max(0, song_limit + topup - used)
        credits = leftover * PACKAGES_TO_CREDITS
        return {
            "user_id": str(user_id),
            "bucket": "monthly",
            "plan_id": str(plan.id),
            "plan_name": plan.name,
            "price_cents": int(getattr(plan, "price_cents", 0) or 0),
            "plan_song_limit": song_limit,
            "song_topup": topup,
            "music_used": used,
            "leftover_packages": leftover,
            "credits_to_mint": credits,
            "period_start": period_start.isoformat(),
            "skipped": False,
            "already_applied": applied is not None,
        }

    async def dry_run(self, user_ids: list[UUID] | None = None) -> list[dict[str, Any]]:
        if user_ids:
            targets = user_ids
        else:
            rows = await self._store.list_active_license_users()
            targets = [row["user_id"] for row in rows]
        return [await self.preview_user(user_id) for user_id in targets]

    async def apply(self, user_ids: list[UUID] | None = None, *, confirm: bool = False) -> list[dict[str, Any]]:
        if not confirm:
            raise ValidationError(
                "Conversion apply requires confirm=true. Dry-run first.",
                details={"confirm": False},
            )
        previews = await self.dry_run(user_ids)
        results: list[dict[str, Any]] = []
        for preview in previews:
            user_id = UUID(preview["user_id"])
            if preview.get("already_applied"):
                results.append({**preview, "status": "already_applied"})
                continue
            if preview.get("skipped") or int(preview.get("credits_to_mint") or 0) <= 0:
                await self._store.insert_conversion_run(
                    user_id=user_id,
                    plan_id=UUID(preview["plan_id"]) if preview.get("plan_id") else None,
                    leftover_packages=int(preview.get("leftover_packages") or 0),
                    credits_minted=0,
                    amount_units=0,
                    status="skipped",
                    dry_run=False,
                )
                results.append({**preview, "status": "skipped"})
                continue
            units = credits_to_units(int(preview["credits_to_mint"]))
            await CreditLedger(self._credit_repo).grant(
                user_id,
                units,
                grant_type=GrantType.QUOTA_CONVERSION,
                ref_id=f"quota_conversion:{user_id}",
            )
            await self._store.insert_lot(
                user_id=user_id,
                tag="quota_conversion",
                amount_units=units,
                expires_at=None,
                period_start=None,
            )
            await self._store.insert_conversion_run(
                user_id=user_id,
                plan_id=UUID(preview["plan_id"]) if preview.get("plan_id") else None,
                leftover_packages=int(preview["leftover_packages"]),
                credits_minted=int(preview["credits_to_mint"]),
                amount_units=units,
                status="applied",
                dry_run=False,
            )
            results.append(
                {
                    **preview,
                    "status": "applied",
                    "amount_units": units,
                    "balance_credits": units_to_credits(
                        int(await self._credit_repo.get_balance(user_id))
                    ),
                }
            )
        return results
