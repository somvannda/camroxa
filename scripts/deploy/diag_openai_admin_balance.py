#!/usr/bin/env python3
"""Probe OpenAI admin-key endpoints for remaining credits on production keys."""
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
export $(grep -E '^(PLATFORM_DATABASE_URL|PLATFORM_ENCRYPTION_MASTER_KEY)=' platform_api/.env | xargs -d '\n')
PYTHONPATH=/opt/camxora/repo /opt/camxora/repo/platform_api/.venv/bin/python - <<'PY'
import asyncio, json, os
from datetime import datetime, timedelta, timezone
import asyncpg, httpx
from platform_api.services.key_encryption import KeyEncryption

async def main():
    dsn = os.environ["PLATFORM_DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://", 1)
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=2)
    enc = KeyEncryption(os.environ["PLATFORM_ENCRYPTION_MASTER_KEY"])
    rows = await pool.fetch(
        "SELECT label, encrypted_key_value, status FROM api_key_entries WHERE provider='openai' ORDER BY created_at DESC"
    )
    print("openai_keys", len(rows))
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=30)
    urls = [
        "https://api.openai.com/v1/organization/costs?start_time={}&limit=1".format(int((datetime.now(timezone.utc)-timedelta(days=1)).timestamp())),
        "https://api.openai.com/v1/dashboard/billing/credit_grants",
        "https://api.openai.com/v1/dashboard/billing/subscription",
        "https://api.openai.com/dashboard/billing/credit_grants",
        "https://api.openai.com/v1/organization/usage/completions?start_time={}&limit=1".format(int((datetime.now(timezone.utc)-timedelta(days=1)).timestamp())),
    ]
    # also try costs with start_date style
    urls += [
        f"https://api.openai.com/v1/organization/costs?start_time={int(datetime(end.year, end.month, 1, tzinfo=timezone.utc).timestamp())}",
    ]
    async with httpx.AsyncClient(timeout=25.0) as client:
        for row in rows:
            key = enc.decrypt(row["encrypted_key_value"]).strip()
            print(f"=== {row['label']} status={row['status']} prefix={key[:12]}... ===")
            headers = {"Authorization": f"Bearer {key}", "Accept": "application/json"}
            for url in urls:
                resp = await client.get(url, headers=headers)
                print(resp.status_code, url.split("openai.com")[-1][:80])
                print(" ", (resp.text or "")[:280].replace("\n"," "))
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
