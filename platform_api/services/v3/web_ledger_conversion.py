"""One-time CutLuy leftover → non-expiring quota_conversion lot.

Does not use billing_conversion_runs (that table is unique per user for
desktop leftover). Idempotent via credit_transactions.ref_id.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from platform_api.exceptions import ValidationError
from platform_api.services.credit_units import credits_to_units, units_to_credits


def web_remaining_ref_id(user_id: UUID) -> str:
    return f"web_remaining:{user_id}"


class WebLedgerConversionService:
    def __init__(self, *, store: Any, credit_repo: Any) -> None:
        self._store = store
        self._credit_repo = credit_repo

    def _remaining(self, row: dict[str, Any]) -> tuple[int, int, int]:
        granted = int(row.get("monthly_credits_granted") or 0)
        used = int(row.get("monthly_credits_used") or 0)
        monthly = max(0, granted - used)
        topup = max(0, int(row.get("topup_credits_balance") or 0))
        return monthly, topup, monthly + topup

    async def preview_row(self, row: dict[str, Any]) -> dict[str, Any]:
        user_id = UUID(str(row["user_id"]))
        monthly, topup, remaining = self._remaining(row)
        already = await self._store.has_transaction_ref(web_remaining_ref_id(user_id))
        skipped = remaining <= 0 or already
        return {
            "user_id": str(user_id),
            "subscription_id": str(row.get("subscription_id") or ""),
            "plan_id": str(row["plan_id"]) if row.get("plan_id") else None,
            "plan_name": row.get("plan_name"),
            "price_cents": int(row.get("price_cents") or 0),
            "monthly_remaining": monthly,
            "topup_remaining": topup,
            "credits_to_mint": 0 if already else remaining,
            "already_applied": already,
            "skipped": skipped,
            "bucket": "already_applied" if already else ("zero_remaining" if remaining <= 0 else "web_remaining"),
        }

    async def dry_run(self, user_ids: list[UUID] | None = None) -> list[dict[str, Any]]:
        rows = await self._store.list_active_web_subscribers(user_ids)
        seen: set[str] = set()
        previews: list[dict[str, Any]] = []
        for row in rows:
            key = str(row["user_id"])
            if key in seen:
                continue
            seen.add(key)
            previews.append(await self.preview_row(row))
        return previews

    async def apply(
        self,
        user_ids: list[UUID] | None = None,
        *,
        confirm: bool = False,
    ) -> list[dict[str, Any]]:
        if not confirm:
            raise ValidationError(
                "Web leftover apply requires confirm=true. Dry-run first.",
                details={"confirm": False},
            )
        previews = await self.dry_run(user_ids)
        results: list[dict[str, Any]] = []
        for preview in previews:
            user_id = UUID(preview["user_id"])
            if preview.get("already_applied"):
                results.append({**preview, "status": "already_applied"})
                continue
            credits = int(preview.get("credits_to_mint") or 0)
            if preview.get("skipped") or credits <= 0:
                results.append({**preview, "status": "skipped"})
                continue
            units = credits_to_units(credits)
            ref_id = web_remaining_ref_id(user_id)
            await self._credit_repo.add_credits(
                user_id,
                units,
                reason="v3_web_remaining",
                ref_id=ref_id,
            )
            lot = await self._store.insert_lot(
                user_id=user_id,
                tag="quota_conversion",
                amount_units=units,
                expires_at=None,
                period_start=None,
            )
            await self._store.zero_web_subscription_remaining(user_id)
            results.append(
                {
                    **preview,
                    "status": "applied",
                    "amount_units": units,
                    "lot_id": str(lot["id"]),
                    "ref_id": ref_id,
                    "balance_credits": units_to_credits(
                        int(await self._credit_repo.get_balance(user_id))
                    ),
                }
            )
        return results
