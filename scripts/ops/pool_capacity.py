#!/usr/bin/env python3
"""Report Suno pool runway: credits left vs recent daily burn.

The paid Suno accounts are a shared pool. If it runs dry every generation fails,
and nobody notices until users complain. This prints the runway and exits 1 when
it drops below the threshold, so a timer can page.

Read-only.

Usage:
    python scripts/ops/pool_capacity.py
    python scripts/ops/pool_capacity.py --days 3 --min-runway 2 --json
    python scripts/ops/pool_capacity.py --dsn postgresql://...

Exit codes: 0 = enough runway, 1 = below threshold, 2 = usage/connection error.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

import asyncpg

PAID_ACCOUNTS_SQL = """
SELECT label, credits_left, renews_on
FROM suno_accounts
WHERE type = 'paid' AND is_active = true
ORDER BY credits_left DESC;
"""

BURN_SQL = """
SELECT created_at::date AS day,
       coalesce(sum(credits), 0)::bigint AS credits,
       count(*)::bigint AS jobs
FROM jobs
WHERE endpoint = 'music'
  AND created_at >= now() - ($1 || ' days')::interval
GROUP BY 1
ORDER BY 1;
"""


async def run(dsn: str, days: int, min_runway: float, as_json: bool) -> int:
    conn = await asyncpg.connect(dsn=dsn)
    try:
        accounts = await conn.fetch(PAID_ACCOUNTS_SQL)
        burn = await conn.fetch(BURN_SQL, str(max(1, days)))
    finally:
        await conn.close()

    remaining = sum(int(a["credits_left"] or 0) for a in accounts)
    per_day = [int(r["credits"] or 0) for r in burn]
    # Today is partial, so average only the days before it when possible.
    full_days = per_day[:-1] if len(per_day) > 1 else per_day
    avg_burn = (sum(full_days) / len(full_days)) if full_days else 0.0
    runway = (remaining / avg_burn) if avg_burn > 0 else float("inf")

    payload = {
        "credits_remaining": remaining,
        "avg_daily_burn": round(avg_burn, 2),
        "runway_days": None if runway == float("inf") else round(runway, 2),
        "min_runway_days": min_runway,
        "accounts": [
            {
                "label": a["label"],
                "credits_left": int(a["credits_left"] or 0),
                "renews_on": a["renews_on"].isoformat() if a["renews_on"] else None,
            }
            for a in accounts
        ],
    }

    if as_json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"paid credits remaining: {remaining:,}")
        print(f"avg daily burn ({len(full_days)}d): {avg_burn:,.0f} credits")
        if runway == float("inf"):
            print("runway: no burn recorded")
        else:
            print(f"runway: {runway:.1f} days (threshold {min_runway:.1f})")
        print("\naccounts:")
        for a in payload["accounts"]:
            renew = f"renews {a['renews_on'][:10]}" if a["renews_on"] else "no renewal date"
            print(f"  {a['label']:32} {a['credits_left']:>8,}  {renew}")

    if runway != float("inf") and runway < min_runway:
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dsn",
        default=os.environ.get("MUSICAPI_DATABASE_URL")
        or os.environ.get("PLATFORM_MUSICAPI_DATABASE_URL")
        or os.environ.get("DATABASE_URL"),
        help="musicapi DB DSN (default: $MUSICAPI_DATABASE_URL)",
    )
    parser.add_argument("--days", type=int, default=4, help="burn window (default 4)")
    parser.add_argument(
        "--min-runway",
        type=float,
        default=2.0,
        help="alert below this many days of runway (default 2)",
    )
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args()

    if not args.dsn:
        print("error: no DSN; pass --dsn or set MUSICAPI_DATABASE_URL", file=sys.stderr)
        return 2
    dsn = str(args.dsn).replace("postgresql+asyncpg://", "postgresql://")

    try:
        return asyncio.run(run(dsn, args.days, args.min_runway, args.json))
    except Exception as exc:  # noqa: BLE001 - CLI boundary
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
