#!/usr/bin/env python3
"""Diagnose billing payment 500 on sandbox."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_secrets, ssh_connect  # noqa: E402

PAYMENT_ID = "482de7df-b6e5-4812-abfa-88beb8f9422a"


def main() -> int:
    secrets = load_secrets()
    client = ssh_connect(secrets["VPS_HOST"], secrets["VPS_USER"], ensure_deploy_key(), None)

    remote_py = f"""
import asyncio
import asyncpg
from pathlib import Path

PAYMENT_ID = "{PAYMENT_ID}"

def load_env():
    env = {{}}
    for path in [Path("/opt/camxora/repo/platform_api/.env"), Path("/opt/camxora/.env")]:
        if not path.exists():
            continue
        for line in path.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"')
    return env

async def main():
    env = load_env()
    dsn = env.get("DATABASE_URL") or env.get("PLATFORM_DATABASE_URL")
    conn = await asyncpg.connect(dsn)
    row = await conn.fetchrow(
        '''
        SELECT id, status, provider, external_payment_id, amount_cents,
               fulfilled_at, plan_id, user_id, metadata, reference_id
        FROM billing_payments
        WHERE id = $1
        ''',
        PAYMENT_ID,
    )
    print("payment:", dict(row) if row else "NOT FOUND")
    if row:
        lic = await conn.fetchrow(
            "SELECT id, plan_id, status FROM licenses WHERE user_id = $1 ORDER BY created_at DESC LIMIT 3",
            row["user_id"],
        )
        print("latest_license:", dict(lic) if lic else None)
    await conn.close()

asyncio.run(main())
"""

    cmd = f"""
journalctl -u camxora-api -n 300 --no-pager | grep -iE '{PAYMENT_ID[:8]}|fulfill|billing/payments|Traceback|ERROR|Exception|grant_included' | tail -60
echo '--- payment row ---'
/opt/camxora/repo/platform_api/.venv/bin/python - <<'PYEOF'
{remote_py}
PYEOF
"""
    _, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    print(out)
    if err.strip():
        print("STDERR:", err)
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
