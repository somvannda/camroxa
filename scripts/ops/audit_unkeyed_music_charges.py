#!/usr/bin/env python3
"""Report unkeyed desktop music charges that have no successful task.

Desktop music debits were written with ``ref_id = NULL`` until commit
``c23c7b9b`` (2026-11-03). The keyed audits cannot see those rows at all:

* ``audit_orphan_music_charges.py`` filters ``ref_id IS NOT NULL``;
* ``audit_failed_music_refunds.py`` joins ``credit_transactions.ref_id`` to a
  ``suno_tasks`` row.

This audit closes that gap by time-correlating each unkeyed debit with the
nearest ``suno_tasks`` row for the same user. A charge is reported when:

* no task exists within the window (the request died between charge and
  enqueue), or
* the nearest task failed and no refund under its task/song key exists.

Charges younger than ``--min-age-minutes`` are skipped so an in-flight submit
is not reported as an orphan. Read-only; never writes.

Exit codes: 0 = clean, 1 = unrefunded charges found, 2 = error.
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
WITH debits AS (
    SELECT ct.id,
           ct.user_id,
           ct.created_at,
           ct.amount
    FROM credit_transactions ct
    WHERE ct.reason = 'v3_music'
      AND ct.direction = 'debit'
      AND ct.ref_id IS NULL
      AND ct.created_at >= now() - ($1 || ' days')::interval
      AND ct.created_at < now() - ($2 || ' minutes')::interval
)
SELECT d.id,
       u.email,
       d.created_at,
       d.amount,
       t.id AS task_id,
       t.song_id,
       t.status AS task_status,
       EXISTS (
           SELECT 1 FROM credit_transactions r
           WHERE r.user_id = d.user_id
             AND (r.direction = 'refund' OR r.reason ILIKE '%refund%')
             AND (r.ref_id = t.id::text OR r.ref_id = t.song_id::text)
       ) AS refunded
FROM debits d
JOIN users u ON u.id = d.user_id
LEFT JOIN LATERAL (
    SELECT t.id, t.song_id, t.status
    FROM suno_tasks t
    WHERE t.user_id = d.user_id
      AND t.created_at BETWEEN d.created_at - interval '120 seconds'
                           AND d.created_at + interval '120 seconds'
    ORDER BY abs(extract(epoch FROM (t.created_at - d.created_at)))
    LIMIT 1
) t ON true
WHERE t.id IS NULL
   OR (
        lower(coalesce(t.status, '')) IN ('failed', 'error')
        AND NOT EXISTS (
            SELECT 1 FROM credit_transactions r
            WHERE r.user_id = d.user_id
              AND (r.direction = 'refund' OR r.reason ILIKE '%refund%')
              AND (r.ref_id = t.id::text OR r.ref_id = t.song_id::text)
        )
   )
ORDER BY d.created_at;
"""


def _credits(value: object) -> float:
    return float(Decimal(str(value or 0)) / UNITS_PER_CREDIT)


async def run(
    dsn: str,
    days: int,
    min_age_minutes: int,
    as_json: bool,
) -> int:
    conn = await asyncpg.connect(dsn=dsn)
    try:
        rows = await conn.fetch(SQL, str(max(1, days)), str(max(0, min_age_minutes)))
    finally:
        await conn.close()

    total = sum(_credits(r["amount"]) for r in rows)

    if as_json:
        print(
            json.dumps(
                {
                    "unrefunded_unkeyed_charges": len(rows),
                    "credits": total,
                    "rows": [
                        {
                            "email": r["email"],
                            "created_at": r["created_at"].isoformat(),
                            "credits": _credits(r["amount"]),
                            "task_status": r["task_status"],
                            "task_id": str(r["task_id"]) if r["task_id"] else None,
                            "song_id": str(r["song_id"]) if r["song_id"] else None,
                            "debit_id": str(r["id"]),
                        }
                        for r in rows
                    ],
                },
                indent=2,
            )
        )
    else:
        print(
            f"unrefunded unkeyed v3_music charges (last {days}d): "
            f"{len(rows)} = {total:g} credits"
        )
        if rows:
            print(
                f"\n{'user':34} {'when':20} {'credits':>8} "
                f"{'task':10} {'debit_id'}"
            )
            for r in rows:
                print(
                    f"{r['email']:34} {r['created_at']:%Y-%m-%d %H:%M:%S} "
                    f"{_credits(r['amount']):8g} "
                    f"{str(r['task_status'] or 'no_task'):10} {r['id']}"
                )

    return 1 if rows else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dsn",
        default=os.environ.get("PLATFORM_DATABASE_URL"),
        help="platform DB DSN (default: $PLATFORM_DATABASE_URL)",
    )
    parser.add_argument("--days", type=int, default=30, help="lookback window")
    parser.add_argument(
        "--min-age-minutes",
        type=int,
        default=15,
        help="skip charges younger than this (in-flight submits)",
    )
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args()

    if not args.dsn:
        print("error: no DSN; pass --dsn or set PLATFORM_DATABASE_URL", file=sys.stderr)
        return 2
    dsn = str(args.dsn).replace("postgresql+asyncpg://", "postgresql://")

    try:
        return asyncio.run(
            run(dsn, args.days, args.min_age_minutes, args.json)
        )
    except Exception as exc:  # noqa: BLE001 - CLI boundary
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
