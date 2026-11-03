#!/usr/bin/env python3
"""Refund the difference on v3 image charges that used the wrong price.

Before 2026-11-03 the ``image`` op resolved its price from a provider-blind
chain and could charge another provider's row (production: 60 credits instead
of the routed SLAI 6). This finds ``v3_image`` debits above the price the
routed provider now resolves to and refunds the difference.

Dry-run by default. Idempotent: each refund is keyed by
``image_overcharge:<debit txn id>``, so re-running never double-credits.

The debit metadata does not record background vs thumbnail (old charges carry
only ``op: image``), so the reference is the **higher** of the two routed
prices. That never refunds more than the platform should keep; a correctly
priced thumbnail is left alone.

Run on the API host (needs ``DATABASE_URL`` and ``platform_api`` importable):

    python scripts/deploy/refund_v3_image_overcharge.py --since 2026-10-01
    python scripts/deploy/refund_v3_image_overcharge.py --since 2026-10-01 --apply
    python scripts/deploy/refund_v3_image_overcharge.py --user-id <uuid> --apply
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import date
from types import SimpleNamespace

import asyncpg

from platform_api.config import get_settings
from platform_api.repositories.credit_repo import CreditRepository
from platform_api.services.credit_units import units_to_credits
from platform_api.services.v3.list_prices import resolve_op_list_units

IMAGE_OPERATIONS = ("background_image", "thumbnail_image")
REFUND_REASON = "v3_refund_image"


class DbPricing:
    """``CreditPricingService`` shape backed by ``credit_pricing`` directly."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def get_price(
        self, ai_service: str, operation_type: str, sub_model: str | None = None
    ) -> int:
        row = await self._pool.fetchrow(
            "SELECT credits_per_operation FROM credit_pricing "
            "WHERE ai_service = $1 AND operation_type = $2 AND sub_model = $3",
            ai_service,
            operation_type,
            sub_model or "",
        )
        if row is None:
            raise LookupError(f"missing {ai_service}/{operation_type}/{sub_model or ''}")
        return int(row["credits_per_operation"])

    async def get_all_pricing(self) -> list[dict]:
        rows = await self._pool.fetch(
            "SELECT ai_service, operation_type, sub_model, credits_per_operation "
            "FROM credit_pricing ORDER BY ai_service, operation_type, sub_model"
        )
        return [dict(row) for row in rows]


class DbRouting:
    """``AIRoutingService`` shape backed by ``ai_routing_assignments``."""

    def __init__(self, assignments: dict) -> None:
        self._assignments = assignments

    async def resolve(self, operation: str) -> SimpleNamespace:
        entry = self._assignments.get(operation) or {}
        provider = str(entry.get("provider") or "").strip()
        if not provider:
            raise LookupError(f"no routing for {operation}")
        sub_model = str(entry.get("sub_model") or "").strip() or None
        return SimpleNamespace(provider=provider, sub_model=sub_model)


async def _assignments(pool: asyncpg.Pool) -> dict:
    raw = await pool.fetchval(
        "SELECT value::text FROM system_settings WHERE key = 'ai_routing_assignments'"
    )
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


async def _expected_units(pricing: DbPricing, routing: DbRouting) -> dict[str, int]:
    out: dict[str, int] = {}
    for operation in IMAGE_OPERATIONS:
        try:
            entry = await routing.resolve(operation)
            provider, sub_model = entry.provider, entry.sub_model
        except LookupError:
            provider, sub_model = None, None
        out[operation] = await resolve_op_list_units(
            pricing,
            "image",
            image_provider=provider,
            image_sub_model=sub_model,
            image_operation=operation,
        )
    return out


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="write the refunds")
    parser.add_argument("--user-id", default=None, help="limit to one user")
    parser.add_argument(
        "--since",
        default=date.today().replace(day=1).isoformat(),
        help="only debits on/after this date (YYYY-MM-DD)",
    )
    args = parser.parse_args()

    settings = get_settings()
    dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=3)
    try:
        pricing = DbPricing(pool)
        routing = DbRouting(await _assignments(pool))
        expected = await _expected_units(pricing, routing)
        reference = max(expected.values()) if expected else 0
        print(
            f"mode={'APPLY' if args.apply else 'DRY-RUN'} since={args.since} "
            f"expected_units={expected} "
            f"reference_credits={units_to_credits(reference):g}"
        )
        if reference <= 0:
            print("No routed image price resolved; refusing to refund.")
            return

        sql = """
        SELECT id, user_id, amount, ref_id, created_at
        FROM credit_transactions
        WHERE direction = 'debit'
          AND reason = 'v3_image'
          AND amount > $1
          AND created_at >= $2::timestamptz
        """
        params: list = [reference, args.since]
        if args.user_id:
            sql += " AND user_id = $3::uuid"
            params.append(args.user_id)
        sql += " ORDER BY created_at"

        rows = await pool.fetch(sql, *params)
        repo = CreditRepository(pool)
        total_units = 0
        refunded = 0
        for row in rows:
            over = int(row["amount"]) - reference
            if over <= 0:
                continue
            ref_id = f"image_overcharge:{row['id']}"
            print(
                f"{row['created_at']} user={row['user_id']} "
                f"charged={units_to_credits(int(row['amount'])):g} "
                f"refund={units_to_credits(over):g} ref={ref_id}"
            )
            total_units += over
            if not args.apply:
                continue
            did = await repo.refund_once(
                row["user_id"],
                over,
                reason=REFUND_REASON,
                ref_id=ref_id,
                metadata={
                    "billing": "wallet_refund",
                    "source": "v3",
                    "op": "image",
                    "note": "overcharge: image priced from a foreign provider row",
                    "debit_txn": str(row["id"]),
                },
            )
            refunded += 1 if did else 0
            print("  ->", "refunded" if did else "already refunded")

        print(
            f"IMAGE_OVERCHARGE_REFUND_DONE applied={args.apply} rows={len(rows)} "
            f"refunded={refunded} total_credits={units_to_credits(total_units):g}"
        )
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
