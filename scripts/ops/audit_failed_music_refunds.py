#!/usr/bin/env python3
"""Report failed songs whose charge was never refunded.

A failed generation must not keep the user's credits. Charges and refunds are
keyed by the same reference, but *which* reference differs by product: web music
uses the task id, desktop uses the batch song id. ``suno_tasks`` carries both
(``id`` and ``song_id``), so a per-reference count works for both.

Matching is deliberately count-based, because a desktop song is charged once per
attempt under the same song id and is retried after a failure:

* every ``v3_music`` debit for the reference counts as a charge;
* every refund for the reference (``direction='refund'`` or a ``%refund%``
  reason — the automatic paths are named ``suno_generation_failed`` and
  ``web_music_generation_failed``) counts as settled;
* every **successful** task for the reference settles one charge too.

The reference is reported only when charges > refunds + successes, it has a
terminal failure, and no task on it is still in flight. That keeps a successful
retry from being flagged as an unrefunded failure.

Read-only. Charges with ``ref_id IS NULL`` (old desktop builds) cannot be
matched by key and are counted separately as unverifiable.

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
WITH debits AS (
    SELECT ct.user_id,
           ct.ref_id AS ref,
           count(*) AS charges,
           sum(ct.amount) AS units
    FROM credit_transactions ct
    WHERE ct.reason = 'v3_music'
      AND ct.direction = 'debit'
      AND ct.ref_id IS NOT NULL
      AND ct.created_at >= now() - ($1 || ' days')::interval
    GROUP BY ct.user_id, ct.ref_id
), refunds AS (
    SELECT r.user_id, r.ref_id AS ref, count(*) AS settled
    FROM credit_transactions r
    WHERE (r.direction = 'refund' OR r.reason ILIKE '%refund%')
      AND r.ref_id IS NOT NULL
    GROUP BY r.user_id, r.ref_id
), successes AS (
    SELECT t.user_id, t.id::text AS ref, count(*) AS settled
    FROM suno_tasks t
    WHERE lower(t.status) = 'success'
    GROUP BY t.user_id, t.id::text
    UNION ALL
    SELECT t.user_id, t.song_id::text AS ref, count(*) AS settled
    FROM suno_tasks t
    WHERE lower(t.status) = 'success' AND t.song_id IS NOT NULL
    GROUP BY t.user_id, t.song_id::text
)
SELECT u.email,
       a.ref,
       a.charges - COALESCE(rf.settled, 0) - COALESCE(su.settled, 0) AS charges,
       a.units,
       a.charges AS total_charges,
       (SELECT string_agg(DISTINCT t.status, ',' ORDER BY t.status)
        FROM suno_tasks t
        WHERE t.user_id = a.user_id
          AND (t.id::text = a.ref OR t.song_id::text = a.ref)) AS statuses
FROM debits a
JOIN users u ON u.id = a.user_id
LEFT JOIN refunds rf ON rf.user_id = a.user_id AND rf.ref = a.ref
LEFT JOIN successes su ON su.user_id = a.user_id AND su.ref = a.ref
WHERE a.charges - COALESCE(rf.settled, 0) - COALESCE(su.settled, 0) > 0
  -- A reference only counts once it has a terminal failure...
  AND EXISTS (
      SELECT 1 FROM suno_tasks t
      WHERE t.user_id = a.user_id
        AND (t.id::text = a.ref OR t.song_id::text = a.ref)
        AND lower(t.status) IN ('failed', 'error'))
  -- ...and nothing is still in flight on it.
  AND NOT EXISTS (
      SELECT 1 FROM suno_tasks t
      WHERE t.user_id = a.user_id
        AND (t.id::text = a.ref OR t.song_id::text = a.ref)
        AND lower(t.status) NOT IN ('failed', 'error', 'success'))
ORDER BY a.units DESC
"""

UNVERIFIABLE_SQL = """
SELECT count(*) AS charges, COALESCE(sum(amount), 0) AS units
FROM credit_transactions
WHERE reason = 'v3_music'
  AND direction = 'debit'
  AND ref_id IS NULL
  AND created_at >= now() - ($1 || ' days')::interval
"""


def _owed_units(row: dict) -> int:
    units = int(row["units"] or 0)
    total = int(row["total_charges"] or 0)
    owed = int(row["charges"] or 0)
    if total <= 0:
        return 0
    return round(units * owed / total)


async def run(dsn: str, days: int, as_json: bool) -> int:
    window = str(max(1, days))
    conn = await asyncpg.connect(dsn=dsn)
    try:
        rows = await conn.fetch(SQL, window)
        unverifiable = await conn.fetchrow(UNVERIFIABLE_SQL, window)
    finally:
        await conn.close()

    charges = sum(int(r["charges"] or 0) for r in rows)
    total_units = sum(_owed_units(dict(r)) for r in rows)
    total_credits = Decimal(total_units) / UNITS_PER_CREDIT
    unverifiable_charges = int(unverifiable["charges"] or 0)
    unverifiable_credits = Decimal(int(unverifiable["units"] or 0)) / UNITS_PER_CREDIT

    if as_json:
        print(
            json.dumps(
                {
                    "unrefunded_failed_charges": charges,
                    "credits": float(total_credits),
                    "unverifiable_null_ref_charges": unverifiable_charges,
                    "rows": [
                        {
                            "email": r["email"],
                            "status": r["statuses"],
                            "charges": int(r["charges"] or 0),
                            "credits": float(
                                Decimal(_owed_units(dict(r))) / UNITS_PER_CREDIT
                            ),
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
                f"  {r['email']:34} {str(r['statuses']):14} "
                f"{int(r['charges'] or 0):4}  "
                f"{Decimal(_owed_units(dict(r))) / UNITS_PER_CREDIT:>8} credits"
            )
        if unverifiable_charges:
            print(
                f"  note: {unverifiable_charges} unkeyed desktop charge(s) "
                f"({unverifiable_credits} credits) cannot be matched by key; "
                "see the admin failed-refunds audit"
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
