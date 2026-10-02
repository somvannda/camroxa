#!/usr/bin/env python3
"""Inspect router-level guards that probes bypass: freeze + rate limit.
+ freeze flag + pich IP counters in redis."""
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
echo '=== enforce_generation_freeze source ==='
grep -n -A 25 'def enforce_generation_freeze' $REPO/services/generation_freeze.py 2>/dev/null | head -40
echo
echo '=== reject_probe_payload source ==='
grep -n -A 30 'def reject_probe_payload' $REPO/services/generation_freeze.py 2>/dev/null | head -45
echo
echo '=== enforce_rate_limit source ==='
grep -n -A 30 'async def enforce_rate_limit\b\|def enforce_rate_limit' $REPO/middleware/rate_limit.py 2>/dev/null | head -45
echo
echo '=== freeze / rate settings in system_settings ==='
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
    rows = await pool.fetch("SELECT key, value FROM system_settings WHERE key ILIKE '%freeze%' OR key ILIKE '%rate%' OR key ILIKE '%music%'")
    for r in rows:
        print("SETTING:", r["key"], "=", str(r["value"])[:300])
    await pool.close()

asyncio.run(main())
PYEOF
echo
echo '=== pich IP redis counters (db1) ==='
redis-cli -n 1 --scan --pattern '*203.147.139.59*' 2>/dev/null | head -20
echo GUARDS_DONE
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
