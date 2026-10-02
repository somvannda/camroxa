#!/usr/bin/env python3
"""Compare iamduke1987 vs pich accounts + find 'Subscription refresh failed' source."""
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
echo '=== where is "Subscription refresh failed" logged? ==='
grep -rn 'Subscription refresh failed' $REPO 2>/dev/null | head -10
echo
echo '=== DB: both accounts ==='
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
    for email in ("pich.sou11@gmail.com", "iamduke1987@gmail.com"):
        row = await pool.fetchrow("SELECT id, email, status, created_at FROM users WHERE email=$1", email)
        if not row:
            print(email, "-> NO USER")
            continue
        print("USER:", email, "| id:", row["id"], "| status:", row["status"])
        sub = await pool.fetchrow(
            "SELECT plan_name, status, current_period_end, monthly_credits_granted, monthly_credits_used, "
            "created_at, updated_at FROM web_subscriptions WHERE user_id=$1 ORDER BY updated_at DESC LIMIT 1",
            row["id"],
        )
        print("  WEB_SUB:", dict(sub) if sub else None)
        lic = await pool.fetchrow("SELECT id, plan_id, status, expires_at FROM licenses WHERE user_id=$1 AND status='active' LIMIT 1", row["id"])
        print("  LICENSE:", dict(lic) if lic else None)
    await pool.close()

asyncio.run(main())
PYEOF
echo ACCOUNTS_DONE
"""


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        _, stdout, stderr = client.exec_command(REMOTE_CMD, get_pty=False, timeout=120)
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
