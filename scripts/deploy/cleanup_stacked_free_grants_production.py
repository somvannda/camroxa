#!/usr/bin/env python3
"""Production cleanup: remove Free-plan credits over-minted by the daily period-grant bug.

Free users were granted 50 credits/day (stacking, 30-day expiry) instead of
50/month. This zeroes the extra grant lots and claws the excess back from the
wallet, then rebuilds one correct current-month grant lot per affected user.

Dry-run by default. Pass --apply (with --i-mean-production) to write.

  python scripts/deploy/cleanup_stacked_free_grants_production.py --i-mean-production
  python scripts/deploy/cleanup_stacked_free_grants_production.py --i-mean-production --apply
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_production_secrets, resolve_production_ssh, ssh_connect

PRODUCTION_HOST = "82.197.71.248"

REMOTE = r'''
set -e
API=/opt/camxora/repo/platform_api
export $(grep -E '^PLATFORM_DATABASE_URL=' $API/.env | xargs -d '\n')
APPLY="%APPLY%"
PYTHONPATH=/opt/camxora/repo $API/.venv/bin/python - "$APPLY" <<'PY'
import asyncio, os, sys, uuid
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import asyncpg

APPLY = sys.argv[1] == "apply"
TZ = ZoneInfo("Asia/Phnom_Penh")
CREDIT_SCALE = 10000
FREE_MONTHLY_CREDITS = 50
FREE_MONTHLY_UNITS = FREE_MONTHLY_CREDITS * CREDIT_SCALE


def month_bounds(now):
    start = now.replace(day=1)
    if start.month == 12:
        nxt = start.replace(year=start.year + 1, month=1)
    else:
        nxt = start.replace(month=start.month + 1)
    return start, nxt


async def main():
    dsn = os.environ["PLATFORM_DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://", 1)
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=2)
    now = datetime.now(TZ)
    month_start, next_month = month_bounds(now)
    month_start_d = month_start.date()
    expires_at = next_month.astimezone(timezone.utc)

    free_plan = await pool.fetchrow(
        "SELECT id FROM plans WHERE lower(name)='free' AND is_active=true ORDER BY updated_at DESC LIMIT 1"
    )
    if free_plan is None:
        print("NO_FREE_PLAN")
        return

    rows = await pool.fetch(
        """
        SELECT u.id, u.email, COALESCE(w.balance, 0) AS balance,
               COALESCE((SELECT SUM(l.remaining_units) FROM credit_wallet_lots l
                         WHERE l.user_id = u.id AND l.tag = 'grant'), 0) AS grant_remaining,
               COALESCE((SELECT COUNT(*) FROM credit_wallet_lots l
                         WHERE l.user_id = u.id AND l.tag = 'grant'), 0) AS grant_lots
        FROM users u
        LEFT JOIN credit_wallets w ON w.user_id = u.id
        WHERE COALESCE(u.status, 'active') <> 'deleted'
          AND NOT EXISTS (SELECT 1 FROM licenses l WHERE l.user_id = u.id
                          AND l.status = 'active' AND (l.expires_at IS NULL OR l.expires_at > NOW()))
          AND NOT EXISTS (SELECT 1 FROM web_subscriptions ws JOIN plans p ON p.id = ws.plan_id
                          WHERE ws.user_id = u.id AND ws.status = 'active'
                            AND ws.current_period_end > NOW() AND p.price_cents > 0)
        ORDER BY u.email
        """
    )

    print(f"MODE={'apply' if APPLY else 'dry-run'} month_start={month_start_d} free_monthly={FREE_MONTHLY_CREDITS}")
    affected = 0
    total_claw = 0
    for r in rows:
        grant_remaining = int(r["grant_remaining"])
        if grant_remaining <= FREE_MONTHLY_UNITS:
            continue
        affected += 1
        wallet = int(r["balance"])
        excess = grant_remaining - FREE_MONTHLY_UNITS
        claw = min(excess, wallet)
        wallet_after = wallet - claw
        total_claw += claw
        print(
            f"USER {r['email']} lots={r['grant_lots']} wallet={wallet/CREDIT_SCALE:.2f} "
            f"grant_remaining={grant_remaining/CREDIT_SCALE:.2f} excess={excess/CREDIT_SCALE:.2f} "
            f"claw={claw/CREDIT_SCALE:.2f} wallet_after={wallet_after/CREDIT_SCALE:.2f}"
        )
        if not APPLY:
            continue
        async with pool.acquire() as conn:
            async with conn.transaction():
                if claw > 0:
                    await conn.execute(
                        "UPDATE credit_wallets SET balance = balance - $2, updated_at = NOW() WHERE user_id = $1",
                        r["id"], claw,
                    )
                    await conn.execute(
                        """
                        INSERT INTO credit_transactions
                            (id, user_id, amount, direction, reason, metadata, created_at)
                        VALUES ($1, $2, $3, 'debit', 'v3_cleanup_stacked_grant', $4::jsonb, NOW())
                        """,
                        uuid.uuid4(), r["id"], claw,
                        '{"source": "v3", "billing": "cleanup", "reason": "stacked_free_period_grant"}',
                    )
                await conn.execute(
                    "UPDATE credit_wallet_lots SET remaining_units = 0 WHERE user_id = $1 AND tag = 'grant'",
                    r["id"],
                )
                kept = min(FREE_MONTHLY_UNITS, wallet_after)
                if kept > 0:
                    await conn.execute(
                        """
                        INSERT INTO credit_wallet_lots
                            (id, user_id, tag, amount_units, remaining_units, expires_at, period_start, created_at)
                        VALUES ($1, $2, 'grant', $3, $4, $5, $6, NOW())
                        """,
                        uuid.uuid4(), r["id"], FREE_MONTHLY_UNITS, kept, expires_at, month_start_d,
                    )
    print(f"SUMMARY affected={affected} total_claw={total_claw/CREDIT_SCALE:.2f} apply={APPLY}")
    await pool.close()


asyncio.run(main())
PY
echo CLEANUP_DONE
'''


def main() -> int:
    if "--i-mean-production" not in sys.argv:
        print("Refusing. Re-run with --i-mean-production [--apply]")
        return 2
    apply = "--apply" in sys.argv
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    print(f"Cleanup stacked Free grants on {host} apply={apply}", flush=True)
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        cmd = REMOTE.replace("%APPLY%", "apply" if apply else "dry-run")
        _, stdout, stderr = client.exec_command(cmd, get_pty=False, timeout=180)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
        if err.strip():
            sys.stderr.write("STDERR: " + err[-2000:] + "\n")
        return 0 if "CLEANUP_DONE" in out else 1
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
