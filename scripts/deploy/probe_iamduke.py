#!/usr/bin/env python3
"""iamduke account state + SubscriptionService.get_user_subscription datetime bug."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import (
    ensure_deploy_key,
    load_production_secrets,
    resolve_production_ssh,
    ssh_connect,
)

PRODUCTION_HOST = "82.197.71.248"

REMOTE_CMD = r"""
set +e
REPO=/opt/camxora/repo/platform_api
echo '=== get_user_subscription impl (datetime compare bug?) ==='
grep -n -A 80 'async def get_user_subscription' $REPO/services/v2/subscription_service.py 2>/dev/null | head -110
echo
echo '=== callers of _refresh_subscription_state / get_user_subscription ==='
grep -rn '_refresh_subscription_state\|get_user_subscription' $REPO/services/v2/credit_service.py $REPO/services/v2/subscription_service.py $REPO/routers 2>/dev/null | grep -v '.bak' | head -25
echo
echo '=== iamduke1987 account ==='
cd $REPO && env PYTHONPATH=/opt/camxora/repo .venv/bin/python - <<'PYEOF'
import asyncio, os
import asyncpg

async def main():
    from dotenv import load_dotenv
    load_dotenv("/opt/camxora/repo/platform_api/.env")
    dsn = os.environ.get("PLATFORM_DATABASE_URL")
    if dsn and dsn.startswith("postgresql+asyncpg://"):
        dsn = dsn.replace("postgresql+asyncpg://", "postgresql://", 1)
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=2)
    row = await pool.fetchrow("SELECT id, email, status FROM users WHERE email='iamduke1987@gmail.com'")
    if not row:
        print("NO USER"); return
    print("USER:", row["id"], row["status"])
    subs = await pool.fetch("SELECT id, status, payment_provider, monthly_credits_granted, monthly_credits_used, current_period_end FROM web_subscriptions WHERE user_id=$1", row["id"])
    print("SUBS:", [dict(s, current_period_end=str(s["current_period_end"])) for s in subs])
    lics = await pool.fetch("SELECT id, plan_id, status, expires_at FROM licenses WHERE user_id=$1", row["id"])
    print("LICENSES:", [dict(l, expires_at=str(l["expires_at"])) for l in lics])
    plan = await pool.fetchrow("SELECT id, name FROM plans WHERE id = (SELECT plan_id FROM web_subscriptions WHERE user_id=$1 AND status='active' LIMIT 1)", row["id"])
    print("PLAN:", dict(plan) if plan else None)
    await pool.close()

asyncio.run(main())
PYEOF
echo IAMDUKE_DONE
"""


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        _, stdout, stderr = client.exec_command(REMOTE_CMD, get_pty=False, timeout=150)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
        if err.strip():
            sys.stderr.write("STDERR: " + err[-1500:] + "\n")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
