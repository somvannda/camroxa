#!/usr/bin/env python3
"""Report per-user music usage against the daily cap.

The cap blocks a charge when the day's spend plus one song (10 credits) would
exceed it, so anyone at or above ``cap - 10`` is effectively blocked for the
rest of the day. This shows who is close, who is blocked, and whether the limit
is doing anything at all.

Reads the effective cap the same way the billing service does:
``system_settings.music_daily_credit_cap`` then ``MUSIC_DAILY_CREDIT_CAP``.

Read-only.

Exit codes: 0 = nobody at the cap, 1 = at least one user is blocked, 2 = error.
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
SETTING_KEY = "music_daily_credit_cap"

USAGE_SQL = """
SELECT u.email,
       sum(ct.amount) AS units,
       count(*) AS songs
FROM credit_transactions ct
JOIN users u ON u.id = ct.user_id
WHERE ct.reason = 'v3_music'
  AND ct.direction = 'debit'
  AND ct.created_at >= date_trunc('day', now())
GROUP BY u.email
ORDER BY sum(ct.amount) DESC;
"""


def _credits(units: object) -> float:
    return float(Decimal(str(units or 0)) / UNITS_PER_CREDIT)


async def run(dsn: str, env_default: int, as_json: bool) -> int:
    conn = await asyncpg.connect(dsn=dsn)
    try:
        raw = await conn.fetchval(
            "SELECT value FROM system_settings WHERE key = $1", SETTING_KEY
        )
        rows = await conn.fetch(USAGE_SQL)
    finally:
        await conn.close()

    try:
        cap = max(0, int(str(raw).strip())) if raw not in (None, "") else env_default
    except ValueError:
        cap = env_default

    usage = [
        {"email": r["email"], "credits": _credits(r["units"]), "songs": int(r["songs"] or 0)}
        for r in rows
    ]
    if cap <= 0:
        blocked = []
        near = []
    else:
        blocked = [u for u in usage if u["credits"] >= cap - 10]
        near = [u for u in usage if cap - 50 <= u["credits"] < cap - 10]

    if as_json:
        print(
            json.dumps(
                {
                    "cap_credits": cap,
                    "cap_disabled": cap <= 0,
                    "users_today": len(usage),
                    "blocked_users": blocked,
                    "near_cap_users": near,
                },
                indent=2,
            )
        )
    else:
        source = "admin setting" if raw not in (None, "") else f"env default ({env_default})"
        print(f"daily music cap: {cap} credits ({source})")
        if cap <= 0:
            print("cap disabled - no limit is enforced")
        print(f"users with music spend today: {len(usage)}")
        for u in usage[:10]:
            flag = ""
            if cap > 0 and u["credits"] >= cap - 10:
                flag = "  <== blocked"
            elif cap > 0 and u["credits"] >= cap - 50:
                flag = "  <== near cap"
            print(f"  {u['email']:34} {u['credits']:>8.2f} cr  {u['songs']:>4} songs{flag}")
        if cap > 0:
            print(f"\nblocked (>= cap-10): {len(blocked)}   near (cap-50..cap-10): {len(near)}")

    return 1 if blocked else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dsn",
        default=os.environ.get("PLATFORM_DATABASE_URL"),
        help="platform DB DSN (default: $PLATFORM_DATABASE_URL)",
    )
    parser.add_argument(
        "--env-default",
        type=int,
        default=int(os.environ.get("MUSIC_DAILY_CREDIT_CAP", "500") or 500),
        help="fallback cap when no admin setting exists (default 500)",
    )
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args()

    if not args.dsn:
        print("error: no DSN; pass --dsn or set PLATFORM_DATABASE_URL", file=sys.stderr)
        return 2
    dsn = str(args.dsn).replace("postgresql+asyncpg://", "postgresql://")

    try:
        return asyncio.run(run(dsn, args.env_default, args.json))
    except Exception as exc:  # noqa: BLE001 - CLI boundary
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
