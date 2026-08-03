#!/usr/bin/env python3
"""Check fal key-pool balances on production after new key added."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, ssh_connect  # noqa: E402

PRODUCTION_HOST = "82.197.71.248"
CMD = r'''
cd /opt/camxora/repo
export $(grep -E '^(PLATFORM_DATABASE_URL|PLATFORM_REDIS_URL|PLATFORM_ENCRYPTION_MASTER_KEY|PLATFORM_JWT_SECRET)=' platform_api/.env | xargs -d '\n')
PYTHONPATH=/opt/camxora/repo /opt/camxora/repo/platform_api/.venv/bin/python - <<'PY'
import asyncio, json, os
import asyncpg, httpx
from platform_api.services.key_encryption import KeyEncryption

async def main():
    dsn = os.environ["PLATFORM_DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://", 1)
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=2)
    enc = KeyEncryption(os.environ["PLATFORM_ENCRYPTION_MASTER_KEY"])
    rows = await pool.fetch(
        """
        SELECT id, label, encrypted_key_value, status, priority, created_at
        FROM api_key_entries
        WHERE provider='fal'
        ORDER BY created_at DESC
        """
    )
    print(f"fal_keys={len(rows)}")
    async with httpx.AsyncClient(timeout=20.0) as client:
        for row in rows:
            key = enc.decrypt(row["encrypted_key_value"]).strip().strip('"').strip("'")
            has_colon = ":" in key
            print(f"--- {row['label']} status={row['status']} priority={row['priority']} format={'id:secret' if has_colon else 'single-token'} len={len(key)}")
            for auth in (f"Key {key}", key, f"Bearer {key}"):
                resp = await client.get(
                    "https://api.fal.ai/v1/account/billing",
                    params={"expand": "credits"},
                    headers={"Authorization": auth, "Accept": "application/json"},
                )
                print(f"  {resp.status_code} auth={auth.split()[0] if ' ' in auth else 'raw'} body={(resp.text or '')[:220]}")
                if resp.status_code == 200:
                    try:
                        data = resp.json()
                        credits = (data.get("credits") or {})
                        print(f"  BALANCE={credits.get('current_balance')} {credits.get('currency')}")
                    except Exception as e:
                        print("  parse_err", e)
                    break
    await pool.close()

asyncio.run(main())
PY
'''


def load_production() -> dict[str, str]:
    data: dict[str, str] = {}
    for line in (ROOT / ".deploy" / "secrets.production.env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        data[key.strip()] = value.strip()
    return data


def main() -> int:
    secrets = load_production()
    host = secrets.get("PRODUCTION_VPS_HOST") or secrets["VPS_HOST"]
    user = secrets.get("PRODUCTION_VPS_USER") or secrets["VPS_USER"]
    password = secrets.get("PRODUCTION_VPS_PASSWORD") or secrets.get("VPS_PASSWORD")
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        _, stdout, stderr = client.exec_command(CMD, get_pty=True)
        sys.stdout.write(stdout.read().decode(errors="replace"))
        err = stderr.read().decode(errors="replace")
        if err.strip():
            sys.stderr.write(err[-1500:])
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
