"""Production-only: re-run plan payment fulfillment for paid-but-unfulfilled rows.

Run this **after** deploying the connection fix
(`docs/changelog/2026-10-02-billing-fulfillment-connection-period-grant.md`).
It replays ``_fulfill_paid_payment`` on the server using the deployed code, so
it is idempotent: rows that are already fulfilled are skipped.

    python scripts/deploy/repair_unfulfilled_plan_payments_production.py

Refuses to run against the sandbox host. Prints one line per payment and a
``REPAIR_DONE`` marker.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, ssh_connect  # noqa: E402

PRODUCTION_HOST = "82.197.71.248"
SANDBOX_HOST = "46.250.235.83"

REMOTE = r'''
import asyncio
from pathlib import Path

env = {}
for line in Path('/opt/camxora/repo/platform_api/.env').read_text().splitlines():
    line = line.strip()
    if line and not line.startswith('#') and '=' in line:
        key, _, value = line.partition('=')
        env[key.strip()] = value.strip()

dsn = (env.get('DATABASE_URL') or env.get('PLATFORM_DATABASE_URL') or '').replace(
    'postgresql+asyncpg', 'postgresql'
)
if not dsn:
    raise SystemExit('No DATABASE_URL in platform_api/.env')

import asyncpg
from platform_api.routers.billing import _fulfill_paid_payment


async def main():
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=2)
    try:
        rows = await pool.fetch(
            """
            SELECT *
            FROM billing_payments bp
            WHERE bp.status = 'paid'
              AND bp.fulfilled_at IS NULL
              AND COALESCE(bp.metadata->>'product_type', 'plan') = 'plan'
            ORDER BY bp.created_at
            """
        )
        print('CANDIDATES', len(rows))
        for row in rows:
            external_id = str(row['external_payment_id'])
            try:
                result = await _fulfill_paid_payment(pool, row)
                print('FULFILLED', external_id, '->', result['fulfilled_at'])
            except Exception as exc:  # noqa: BLE001
                print('FAILED', external_id, type(exc).__name__, str(exc))
    finally:
        await pool.close()


asyncio.run(main())
print('REPAIR_DONE')
'''


def load_production() -> dict[str, str]:
    path = ROOT / ".deploy" / "secrets.production.env"
    if not path.is_file():
        raise SystemExit(f"No production secrets at {path}")
    data: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        data[key.strip()] = value.strip()
    return data


def main() -> int:
    secrets = load_production()
    host = secrets.get("PRODUCTION_VPS_HOST") or secrets["VPS_HOST"]
    if host == SANDBOX_HOST or host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    user = secrets.get("PRODUCTION_VPS_USER") or secrets["VPS_USER"]
    password = secrets.get("PRODUCTION_VPS_PASSWORD") or secrets.get("VPS_PASSWORD")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        cmd = (
            "cd /opt/camxora/repo && PYTHONPATH=/opt/camxora/repo "
            "/opt/camxora/repo/platform_api/.venv/bin/python - <<'PY'\n"
            + REMOTE
            + "\nPY\n"
        )
        _, stdout, _ = client.exec_command(cmd, get_pty=False, timeout=300)
        out = stdout.read().decode("utf-8", errors="replace")
        sys.stdout.write(out)
        if "REPAIR_DONE" not in out:
            raise SystemExit("Repair did not finish cleanly.")
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
