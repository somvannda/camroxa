#!/usr/bin/env python3
"""Refund music charges that produced no song and were never refunded.

Companion to ``audit_orphan_music_charges.py``. That script reports; this one
fixes, through the same credit service the app uses, so the wallet, the ledger
and the refund idempotency all behave exactly like a normal refund.

Dry run by default. ``--apply`` additionally requires ``--confirm-credits`` to
match the total found, so a stale plan cannot silently refund the wrong amount.

Usage:
    python scripts/ops/refund_orphan_music_charges.py --days 7
    python scripts/ops/refund_orphan_music_charges.py --days 7 --apply --confirm-credits 180

Exit codes: 0 = nothing to do or applied cleanly, 1 = dry run found work,
2 = error or confirmation mismatch.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from decimal import Decimal

import asyncpg

CREDITS_PER_UNIT = 10_000
REFUND_SOURCE = "music_charge"  # ledger reason becomes ``refunded_music_charge``

SQL = """
WITH debits AS (
    SELECT ct.id, ct.user_id, ct.created_at, ct.amount, ct.ref_id,
           ct.metadata->>'product' AS product
    FROM credit_transactions ct
    WHERE ct.reason = 'v3_music'
      AND ct.direction = 'debit'
      AND ct.ref_id IS NOT NULL
      AND ct.created_at >= now() - ($1 || ' days')::interval
      AND ct.created_at < now() - interval '15 minutes'
)
SELECT d.id, u.email, d.user_id, d.created_at, d.amount, d.ref_id, d.product
FROM debits d
JOIN users u ON u.id = d.user_id
WHERE NOT EXISTS (SELECT 1 FROM suno_tasks t WHERE t.id::text = d.ref_id)
  AND NOT EXISTS (
        SELECT 1 FROM job_queue q
        WHERE q.payload->>'task_id' = d.ref_id
           OR q.payload->>'reservation_id' = d.ref_id)
  AND NOT EXISTS (
        SELECT 1 FROM credit_transactions r
        WHERE r.user_id = d.user_id
          AND r.direction = 'credit'
          AND r.ref_id = d.ref_id
          AND r.reason ILIKE '%refund%')
ORDER BY d.created_at;
"""


def _credits(value: object) -> int:
    return int(Decimal(str(value or 0)) // CREDITS_PER_UNIT)


async def run(dsn: str, days: int, apply: bool, confirm_credits: int | None) -> int:
    pool = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=2)
    try:
        rows = await pool.fetch(SQL, str(max(1, days)))
        total = sum(_credits(r["amount"]) for r in rows)

        print(f"orphaned charges: {len(rows)} = {total} credits")
        for r in rows:
            print(
                f"  {r['email']:34} {r['created_at']:%Y-%m-%d %H:%M} "
                f"{_credits(r['amount']):>4}cr  ref={r['ref_id']}"
            )

        if not rows:
            return 0

        if not apply:
            print("\ndry run - nothing written. Re-run with --apply --confirm-credits "
                  f"{total} to refund.")
            return 1

        if confirm_credits != total:
            print(
                f"\nrefusing: --confirm-credits {confirm_credits} does not match the "
                f"{total} credits found",
                file=sys.stderr,
            )
            return 2

        from platform_api.repositories.credit_repo import CreditRepository
        from uuid import UUID

        repo = CreditRepository(pool=pool)
        refunded = 0
        skipped = 0
        failed = 0
        for r in rows:
            amount = _credits(r["amount"]) * CREDITS_PER_UNIT
            try:
                applied = await repo.refund_once(
                    UUID(str(r["user_id"])),
                    amount,
                    reason="v3_refund_music",
                    ref_id=str(r["ref_id"]),
                    metadata={"source": "v3", "op": "music", "billing": "ops_backfill"},
                )
            except Exception as exc:  # noqa: BLE001 - report and continue
                print(f"  FAILED {r['email']} ref={r['ref_id']}: {exc}", file=sys.stderr)
                failed += 1
                continue
            if applied:
                refunded += 1
                print(f"  refunded {amount // CREDITS_PER_UNIT}cr -> {r['email']} ref={r['ref_id']}")
            else:
                skipped += 1
                print(f"  already refunded -> {r['email']} ref={r['ref_id']}")

        remaining = await pool.fetchval(
            f"SELECT count(*) FROM ({SQL}) AS q", str(max(1, days))
        )
        print(
            f"\nrefunded {refunded}, already refunded {skipped}, failed {failed}; "
            f"orphans remaining now: {remaining}"
        )
        return 0 if failed == 0 and int(remaining or 0) == 0 else 2
    finally:
        await pool.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dsn",
        default=os.environ.get("PLATFORM_DATABASE_URL"),
        help="platform DB DSN (default: $PLATFORM_DATABASE_URL)",
    )
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--apply", action="store_true", help="write the refunds")
    parser.add_argument(
        "--confirm-credits",
        type=int,
        default=None,
        help="total credits from the dry run; must match exactly",
    )
    args = parser.parse_args()

    if not args.dsn:
        print("error: no DSN; pass --dsn or set PLATFORM_DATABASE_URL", file=sys.stderr)
        return 2
    dsn = str(args.dsn).replace("postgresql+asyncpg://", "postgresql://")

    try:
        return asyncio.run(run(dsn, args.days, args.apply, args.confirm_credits))
    except Exception as exc:  # noqa: BLE001 - CLI boundary
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
