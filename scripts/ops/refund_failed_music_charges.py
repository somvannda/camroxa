#!/usr/bin/env python3
"""Refund failed generations whose charge was never returned.

Companion to ``audit_failed_music_refunds.py``: same detection, then a refund
through the credit repository so the wallet, ledger and idempotency all behave
like a normal refund.

Charges and refunds are keyed differently by product (web: task id, desktop:
batch song id), so a refund is keyed on the charge's own reference and the
"already refunded?" check matches that reference plus either task key.

Dry run by default. ``--apply`` additionally requires ``--confirm-credits`` to
match the total found, so a stale plan cannot refund the wrong amount.

Usage:
    python scripts/ops/refund_failed_music_charges.py --days 60
    python scripts/ops/refund_failed_music_charges.py --days 60 --apply --confirm-credits 1320

Exit codes: 0 = nothing to do or applied cleanly, 1 = dry run found work,
2 = error or confirmation mismatch.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from decimal import Decimal
from uuid import UUID

import asyncpg

UNITS_PER_CREDIT = 10_000
REFUND_REASON = "v3_refund_music"

SQL = """
SELECT ct.id AS txn_id, ct.user_id, ct.amount, ct.ref_id, ct.created_at,
       u.email, t.status
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
          -- Automatic refunds are named suno_generation_failed /
          -- web_music_generation_failed; requiring '%refund%' in the reason hid
          -- them and made this tool refund the same charge twice.
          AND (r.direction = 'refund' OR r.reason ILIKE '%refund%')
          AND (r.ref_id = ct.ref_id
               OR r.ref_id = t.id::text
               OR r.ref_id = t.song_id::text))
ORDER BY ct.created_at;
"""


def _credits(units: object) -> int:
    return int(Decimal(str(units or 0)) // UNITS_PER_CREDIT)


async def run(dsn: str, days: int, apply: bool, confirm_credits: int | None) -> int:
    pool = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=2)
    try:
        rows = await pool.fetch(SQL, str(max(1, days)))
        total = sum(int(r["amount"] or 0) for r in rows) // UNITS_PER_CREDIT

        print(f"unrefunded failed charges: {len(rows)} = {total} credits")
        for r in rows[:15]:
            print(
                f"  {r['email']:34} {r['created_at']:%Y-%m-%d %H:%M} "
                f"{_credits(r['amount']):>4}cr  ref={r['ref_id']}"
            )
        if len(rows) > 15:
            print(f"  … and {len(rows) - 15} more")

        if not rows:
            return 0

        if not apply:
            print(
                f"\ndry run - nothing written. Re-run with --apply "
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

        from platform_api.repositories.credit_repo import CreditRepository

        repo = CreditRepository(pool=pool)
        refunded = 0
        skipped = 0
        failed = 0
        for r in rows:
            try:
                applied = await repo.refund_once(
                    UUID(str(r["user_id"])),
                    int(r["amount"]),
                    reason=REFUND_REASON,
                    ref_id=str(r["ref_id"]),
                    metadata={
                        "source": "v3",
                        "op": "music",
                        "billing": "ops_backfill",
                        "note": "failed generation, refunded by ops",
                    },
                )
            except Exception as exc:  # noqa: BLE001 - report and continue
                print(f"  FAILED {r['email']} ref={r['ref_id']}: {exc}", file=sys.stderr)
                failed += 1
                continue
            if applied:
                refunded += 1
            else:
                skipped += 1

        remaining = await pool.fetchval(
            f"SELECT count(*) FROM ({SQL.rstrip().rstrip(';')}) AS q", str(max(1, days))
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
    parser.add_argument("--days", type=int, default=60)
    parser.add_argument("--apply", action="store_true", help="write the refunds")
    parser.add_argument("--confirm-credits", type=int, default=None)
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
