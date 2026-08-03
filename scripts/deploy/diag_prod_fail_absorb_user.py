#!/usr/bin/env python3
"""Diagnose fail/retry absorb budget for a production user."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, ssh_connect  # noqa: E402

PRODUCTION_HOST = "82.197.71.248"
EMAIL = "somvannda@gmail.com"


def load_env(name: str) -> dict[str, str]:
    data: dict[str, str] = {}
    for line in (ROOT / ".deploy" / name).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        data[key.strip()] = value.strip()
    return data


CMD = r'''
cd /opt/camxora/repo
export $(grep -E '^(PLATFORM_DATABASE_URL|PLATFORM_REDIS_URL|PLATFORM_DAILY_FAIL_ABSORB_BUDGET)=' platform_api/.env | xargs -d '\n')
PYTHONPATH=/opt/camxora/repo /opt/camxora/repo/platform_api/.venv/bin/python - <<'PY'
import asyncio, os, json
from datetime import datetime, timezone
import asyncpg
import redis.asyncio as redis

EMAIL = "somvannda@gmail.com"

async def main():
    dsn = os.environ["PLATFORM_DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://", 1)
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=2)
    r = redis.from_url(os.environ["PLATFORM_REDIS_URL"], decode_responses=True)

    user = await pool.fetchrow(
        "SELECT id, email, status FROM users WHERE lower(email)=lower($1)",
        EMAIL,
    )
    if not user:
        print("USER_NOT_FOUND"); await pool.close(); await r.aclose(); return
    uid = str(user["id"])
    print("user", json.dumps({k: (str(v) if v is not None else None) for k,v in dict(user).items()}, default=str))

    # billing_today used by API
    from platform_api.services.billing_calendar import billing_today
    today = billing_today()
    print("billing_today", today.isoformat())
    print("env_daily_fail_absorb_budget", os.environ.get("PLATFORM_DAILY_FAIL_ABSORB_BUDGET"))
    try:
        from platform_api.config import get_settings
        print("settings_daily_fail_absorb_budget", get_settings().daily_fail_absorb_budget)
    except Exception as e:
        print("settings_error", type(e).__name__, str(e)[:120])

    key = f"fail_absorb:{uid}:{today.isoformat()}"
    raw = await r.get(key)
    ttl = await r.ttl(key)
    print("redis_key", key, "value", raw, "ttl", ttl)

    # other recent absorb keys for this user
    cursor = 0
    keys = []
    while True:
        cursor, batch = await r.scan(cursor=cursor, match=f"fail_absorb:{uid}:*", count=100)
        keys.extend(batch)
        if cursor == 0:
            break
    print("all_absorb_keys", keys)
    for k in keys:
        print(" ", k, await r.get(k), "ttl", await r.ttl(k))

    # recent platform_absorb ledger events today (UTC/billing)
    rows = await pool.fetch(
        """
        SELECT created_at, amount, direction, reason,
               metadata->>'operation' AS operation,
               metadata->>'provider' AS provider,
               metadata->>'purpose' AS purpose,
               metadata->>'billing' AS billing,
               metadata->>'outcome' AS outcome
        FROM credit_transactions
        WHERE user_id = $1::uuid
          AND (
            metadata->>'billing' = 'platform_absorb'
            OR metadata->>'platform_absorbed_cost' = 'true'
            OR metadata->>'outcome' = 'failed'
          )
          AND created_at >= (CURRENT_DATE AT TIME ZONE 'UTC')
        ORDER BY created_at DESC
        LIMIT 40
        """,
        user["id"],
    )
    print("today_absorb_or_failed_ledger", len(rows))
    for row in rows[:25]:
        print(dict(row))

    counts = await pool.fetch(
        """
        SELECT metadata->>'operation' AS operation, count(*)::int AS n
        FROM credit_transactions
        WHERE user_id = $1::uuid
          AND metadata->>'billing' = 'platform_absorb'
          AND created_at >= (CURRENT_DATE AT TIME ZONE 'UTC')
        GROUP BY 1
        ORDER BY n DESC
        """,
        user["id"],
    )
    print("absorb_by_operation", [dict(c) for c in counts])

    # quota snapshot
    usage = await pool.fetch(
        """
        SELECT operation_type, usage_date, daily_count, period_start, monthly_count
        FROM usage_counts
        WHERE user_id = $1::uuid
          AND usage_date >= CURRENT_DATE - 1
        ORDER BY usage_date DESC, operation_type
        LIMIT 40
        """,
        user["id"],
    )
    print("recent_usage_counts", [dict(u) for u in usage])

    sub = await pool.fetchrow(
        """
        SELECT s.status, s.current_period_start, s.current_period_end,
               p.name AS plan_name, p.profile_allowance,
               p.monthly_song_limit, p.monthly_image_limit, p.monthly_draft_limit
        FROM subscriptions s
        JOIN plans p ON p.id = s.plan_id
        WHERE s.user_id = $1::uuid
        ORDER BY s.created_at DESC
        LIMIT 1
        """,
        user["id"],
    )
    print("subscription", dict(sub) if sub else None)

    profiles = await pool.fetch(
        """
        SELECT id, display_name, status
        FROM channel_profiles
        WHERE user_id = $1::uuid
        ORDER BY created_at
        LIMIT 20
        """,
        user["id"],
    )
    print("profiles", [{**dict(p), "id": str(p["id"])} for p in profiles])

    wallet = await pool.fetchrow(
        "SELECT balance FROM credit_wallets WHERE user_id = $1::uuid",
        user["id"],
    )
    print("wallet_balance_units", int(wallet["balance"]) if wallet else None)

    await pool.close()
    await r.aclose()

asyncio.run(main())
PY
'''


def main() -> int:
    secrets = load_env("secrets.production.env")
    host = secrets.get("PRODUCTION_VPS_HOST") or secrets["VPS_HOST"]
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    client = ssh_connect(
        host,
        secrets.get("PRODUCTION_VPS_USER") or secrets["VPS_USER"],
        ensure_deploy_key(),
        secrets.get("PRODUCTION_VPS_PASSWORD") or secrets.get("VPS_PASSWORD"),
    )
    try:
        _, stdout, stderr = client.exec_command(CMD, get_pty=True, timeout=120)
        out = stdout.read().decode(errors="replace")
        err = stderr.read().decode(errors="replace")
        print(out.encode("ascii", errors="replace").decode("ascii"))
        if err.strip():
            print("STDERR:", err.encode("ascii", errors="replace").decode("ascii"), file=sys.stderr)
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
