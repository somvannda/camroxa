#!/usr/bin/env python3
"""Report music charges that produced no song and were never refunded.

A ``v3_music`` debit is written before the ``suno_tasks`` row is created, so a
request that dies between the charge and the enqueue (client disconnect,
cancellation, API restart) can leave a paid song that never existed. The service
now refunds on cancellation, but this audit is the independent check: it must
stay read-only and alert on anything the refund path missed.

Read-only by design - it never writes. Use it in cron/CI and to drive manual
backfills through the normal refund path.

Usage:
    python scripts/ops/audit_orphan_music_charges.py
    python scripts/ops/audit_orphan_music_charges.py --days 30 --json
    python scripts/ops/audit_orphan_music_charges.py --dsn postgresql://...

Exit codes: 0 = clean, 1 = orphaned charges found, 2 = usage/connection error.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from decimal import Decimal

import asyncpg

CREDITS_PER_UNIT = 10_000

SQL = """
WITH debits AS (
    SELECT ct.id,
           ct.user_id,
           ct.created_at,
           ct.amount,
           ct.ref_id,
           ct.metadata->>'product' AS product,
           ct.metadata->>'model'   AS model
    FROM credit_transactions ct
    WHERE ct.reason = 'v3_music'
      AND ct.direction = 'debit'
      AND ct.ref_id IS NOT NULL
      AND ct.created_at >= now() - ($1 || ' days')::interval
      AND ct.created_at < now() - interval '15 minutes'
)
SELECT d.id,
       u.email,
       d.created_at,
       d.amount,
       d.ref_id,
       d.product,
       d.model
FROM debits d
JOIN users u ON u.id = d.user_id
WHERE NOT EXISTS (
        SELECT 1 FROM suno_tasks t
        WHERE t.id::text = d.ref_id OR t.song_id::text = d.ref_id
      )
  AND NOT EXISTS (
        SELECT 1 FROM job_queue q
        WHERE q.payload->>'task_id' = d.ref_id
           OR q.payload->>'reservation_id' = d.ref_id
      )
  AND NOT EXISTS (
        SELECT 1 FROM credit_transactions r
        WHERE r.user_id = d.user_id
          AND r.direction IN ('credit', 'refund')
          AND r.ref_id = d.ref_id
          AND r.reason ILIKE '%refund%'
      )
ORDER BY d.created_at DESC;
"""


def _dtoi(value: object) -> int:
    """psql numeric -> int."""
    return int(Decimal(str(value or 0)))


async def run(dsn: str, days: int, as_json: bool) -> int:
    conn = await asyncpg.connect(dsn=dsn)
    try:
        rows = await conn.fetch(SQL, str(max(1, days)))
    finally:
        await conn.close()

    total_units = sum(_dtoi(r["amount"]) for r in rows)
    total_credits = total_units / CREDITS_PER_UNIT

    if as_json:
        print(
            json.dumps(
                {
                    "orphaned_charges": len(rows),
                    "credits_at_risk": total_credits,
                    "rows": [
                        {
                            "email": r["email"],
                            "created_at": r["created_at"].isoformat(),
                            "credits": _dtoi(r["amount"]) / CREDITS_PER_UNIT,
                            "ref_id": r["ref_id"],
                            "product": r["product"],
                            "model": r["model"],
                        }
                        for r in rows
                    ],
                },
                indent=2,
            )
        )
    else:
        print(
            f"orphaned v3_music charges (last {days}d): {len(rows)} "
            f"= {total_credits:g} credits"
        )
        if rows:
            print(f"\n{'user':34} {'when':20} {'credits':>8} {'product':10} {'model':10}")
            for r in rows:
                print(
                    f"{r['email']:34} {r['created_at']:%Y-%m-%d %H:%M:%S} "
                    f"{_dtoi(r['amount']) / CREDITS_PER_UNIT:8g} "
                    f"{str(r['product'] or '-'):10} {str(r['model'] or '-'):10}"
                )

    return 1 if rows else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dsn",
        default=os.environ.get("PLATFORM_DATABASE_URL"),
        help="platform DB DSN (default: $PLATFORM_DATABASE_URL)",
    )
    parser.add_argument("--days", type=int, default=7, help="lookback window (default 7)")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args()

    if not args.dsn:
        print("error: no DSN; pass --dsn or set PLATFORM_DATABASE_URL", file=sys.stderr)
        return 2
    dsn = str(args.dsn).replace("postgresql+asyncpg://", "postgresql://")

    try:
        return asyncio.run(run(dsn, args.days, args.json))
    except Exception as exc:  # noqa: BLE001 - CLI boundary
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
