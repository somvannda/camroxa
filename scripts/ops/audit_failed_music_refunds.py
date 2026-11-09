#!/usr/bin/env python3
"""Report failed songs whose charge was never refunded.

A failed generation must not keep the user's credits. Charges and refunds are
keyed by the same reference, but *which* reference differs by product: web music
uses the task id, desktop uses the batch song id. ``suno_tasks`` carries both
(``id`` and ``song_id``), so match either — joining on only one of them produced
a large false-positive list on 2026-11-04.

Read-only.

Exit codes: 0 = every failed charge was refunded, 1 = something is unrefunded,
2 = error.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from decimal import Decimal

import asyncpg

UNITS_PER_CREDIT = 10_000

SQL = """
SELECT u.email,
       t.status,
       count(*) AS charges,
       sum(ct.amount) AS units
FROM credit_transactions ct
JOIN users u ON u.id = ct.user_id
JOIN suno_tasks t
  ON ct.ref_id = t.id::text OR ct.ref_id = t.song_id::text
WHERE ct.reason = 'v3_music'
  AND ct.direction = 'debit'
  AND lower(t.status) IN ('failed', 'error')
  AND ct.created_at >= now() - ($1 || ' days')::interval
  AND NOT EXISTS (
        SELECT 1 FROM credit_transactions r
        WHERE r.user_id = ct.user_id
          AND r.direction IN ('credit', 'refund')
          AND r.reason ILIKE '%refund%'
          -- Charges and refunds are keyed differently by product: web uses the
          -- task id, desktop uses the batch song id. A refund under either key
          -- (or the charge's own) settles the attempt.
          AND (r.ref_id = ct.ref_id
               OR r.ref_id = t.id::text
               OR r.ref_id = t.song_id::text))
GROUP BY u.email, t.status
ORDER BY sum(ct.amount) DESC;
"""


async def run(dsn: str, days: int, as_json: bool) -> int:
    conn = await asyncpg.connect(dsn=dsn)
    try:
        rows = await conn.fetch(SQL, str(max(1, days)))
    finally:
        await conn.close()

    total_units = sum(int(r["units"] or 0) for r in rows)
    total_credits = Decimal(total_units) / UNITS_PER_CREDIT
    charges = sum(int(r["charges"] or 0) for r in rows)

    if as_json:
        print(
            json.dumps(
                {
                    "unrefunded_failed_charges": charges,
                    "credits": float(total_credits),
                    "rows": [
                        {
                            "email": r["email"],
                            "status": r["status"],
                            "charges": int(r["charges"] or 0),
                            "credits": float(Decimal(int(r["units"] or 0)) / UNITS_PER_CREDIT),
                        }
                        for r in rows
                    ],
                },
                indent=2,
            )
        )
    else:
        print(
            f"failed songs charged without a refund (last {days}d): "
            f"{charges} charge(s) = {total_credits} credits"
        )
        for r in rows:
            print(
                f"  {r['email']:34} {str(r['status']):8} "
                f"{int(r['charges'] or 0):4}  {Decimal(int(r['units'] or 0)) / UNITS_PER_CREDIT:>8} credits"
            )

    return 1 if rows else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dsn",
        default=os.environ.get("PLATFORM_DATABASE_URL"),
        help="platform DB DSN (default: $PLATFORM_DATABASE_URL)",
    )
    parser.add_argument("--days", type=int, default=30, help="lookback window (default 30)")
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
