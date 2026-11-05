#!/usr/bin/env python3
"""Refund unkeyed desktop music charges that have no successful task.

Companion to ``audit_unkeyed_music_charges.py`` (same detection, then a write
through ``CreditRepository.refund_once`` so wallet + ledger + idempotency move
together). Only rows the audit reports are refunded.

Idempotency: the refund key is ``orphan:<debit id>``, one per debit row, so a
re-run is a no-op and two similar charges cannot collapse into one refund.

Dry run by default. ``--apply`` also requires ``--confirm-credits`` to match the
total found, so a stale plan cannot refund the wrong amount.

Usage:
    python scripts/ops/refund_unkeyed_music_charges.py --days 30
    python scripts/ops/refund_unkeyed_music_charges.py --days 30 \
        --apply --confirm-credits 20
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from decimal import Decimal

import asyncpg

UNITS_PER_CREDIT = 10_000
REFUND_REASON = "v3_refund_music"
REFUND_KEY_PREFIX = "orphan:"

SQL = """
WITH debits AS (
    SELECT ct.id, ct.user_id, ct.created_at, ct.amount
    FROM credit_transactions ct
    WHERE ct.reason = 'v3_music'
      AND ct.direction = 'debit'
      AND ct.ref_id IS NULL
      AND ct.created_at >= now() - ($1 || ' days')::interval
      AND ct.created_at < now() - ($2 || ' minutes')::interval
)
SELECT d.id, u.email, d.user_id, d.created_at, d.amount
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
WHERE (t.id IS NULL OR lower(coalesce(t.status, '')) IN ('failed', 'error'))
  AND NOT EXISTS (
        SELECT 1 FROM credit_transactions r
        WHERE r.user_id = d.user_id
          AND r.direction IN ('credit', 'refund')
          AND r.reason ILIKE '%refund%'
          AND (
                r.ref_id = d.id::text
                OR r.ref_id = ('orphan:' || d.id::text)
                OR (t.id IS NOT NULL AND r.ref_id = t.id::text)
                OR (t.song_id IS NOT NULL AND r.ref_id = t.song_id::text)
              )
  )
ORDER BY d.created_at;
"""


def _credits(value: object) -> int:
    return int(Decimal(str(value or 0)) // UNITS_PER_CREDIT)


async def run(
    dsn: str,
    days: int,
    min_age_minutes: int,
    apply: bool,
    confirm_credits: int | None,
) -> int:
    pool = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=2)
    try:
        rows = await pool.fetch(SQL, str(max(1, days)), str(max(0, min_age_minutes)))
        total = sum(_credits(r["amount"]) for r in rows)

        print(f"unrefunded unkeyed charges: {len(rows)} = {total} credits")
        for r in rows:
            print(
                f"  {r['email']:34} {r['created_at']:%Y-%m-%d %H:%M} "
                f"{_credits(r['amount']):>4}cr  debit={r['id']}"
            )

        if not rows:
            return 0

        if not apply:
            print(
                "\ndry run - nothing written. Re-run with --apply "
                f"--confirm-credits {total} to refund."
            )
            return 1

        if confirm_credits != total:
            print(
                f"\nrefusing: --confirm-credits {confirm_credits} does not match "
                f"the {total} credits found",
                file=sys.stderr,
            )
            return 2

        from uuid import UUID

        from platform_api.repositories.credit_repo import CreditRepository

        repo = CreditRepository(pool=pool)
        refunded = 0
        skipped = 0
        failed = 0
        for r in rows:
            amount = _credits(r["amount"]) * UNITS_PER_CREDIT
            try:
                applied = await repo.refund_once(
                    UUID(str(r["user_id"])),
                    amount,
                    reason=REFUND_REASON,
                    ref_id=f"{REFUND_KEY_PREFIX}{r['id']}",
                    metadata={
                        "source": "v3",
                        "op": "music",
                        "billing": "ops_backfill",
                        "note": "unkeyed desktop charge with no task",
                    },
                )
            except Exception as exc:  # noqa: BLE001 - report and continue
                print(f"  FAILED {r['email']} debit={r['id']}: {exc}", file=sys.stderr)
                failed += 1
                continue
            if applied:
                refunded += 1
                print(f"  refunded {amount // UNITS_PER_CREDIT}cr -> {r['email']} debit={r['id']}")
            else:
                skipped += 1
                print(f"  already refunded -> {r['email']} debit={r['id']}")

        remaining = await pool.fetchval(
            f"SELECT count(*) FROM ({SQL.rstrip().rstrip(';')}) AS q",
            str(max(1, days)),
            str(max(0, min_age_minutes)),
        )
        print(
            f"\nrefunded {refunded}, already refunded {skipped}, failed {failed}; "
            f"unrefunded now: {remaining}"
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
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--min-age-minutes", type=int, default=15)
    parser.add_argument("--apply", action="store_true", help="write the refunds")
    parser.add_argument("--confirm-credits", type=int, default=None)
    args = parser.parse_args()

    if not args.dsn:
        print("error: no DSN; pass --dsn or set PLATFORM_DATABASE_URL", file=sys.stderr)
        return 2
    dsn = str(args.dsn).replace("postgresql+asyncpg://", "postgresql://")

    try:
        return asyncio.run(
            run(dsn, args.days, args.min_age_minutes, args.apply, args.confirm_credits)
        )
    except Exception as exc:  # noqa: BLE001 - CLI boundary
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
