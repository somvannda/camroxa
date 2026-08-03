#!/usr/bin/env python3
"""Probe SLAI /dashboard/billing without loading full Settings (cors_origins quirk)."""
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
# Strip problematic list env that breaks pydantic when sourced into shell
export $(grep -E '^(PLATFORM_DATABASE_URL|PLATFORM_REDIS_URL|PLATFORM_ENCRYPTION_MASTER_KEY|PLATFORM_SLAI_API_BASE_URL|PLATFORM_JWT_SECRET)=' platform_api/.env | xargs -d '\n')
PYTHONPATH=/opt/camxora/repo /opt/camxora/repo/platform_api/.venv/bin/python - <<'PY'
import asyncio, json, os, re
import asyncpg, httpx
from platform_api.services.key_encryption import KeyEncryption

async def main():
    dsn = os.environ["PLATFORM_DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://", 1)
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=2)
    enc = KeyEncryption(os.environ["PLATFORM_ENCRYPTION_MASTER_KEY"])
    rows = await pool.fetch(
        """
        SELECT id, label, encrypted_key_value, status
        FROM api_key_entries
        WHERE provider='slai'
        ORDER BY priority ASC, created_at ASC
        LIMIT 2
        """
    )
    if not rows:
        print("NO_SLAI_KEYS"); await pool.close(); return
    row = rows[0]
    api_key = enc.decrypt(row["encrypted_key_value"])
    print("using", row["label"], "status", row["status"])
    base = (os.environ.get("PLATFORM_SLAI_API_BASE_URL") or "https://api.slai.shop").rstrip("/")
    print("configured_base", base)
    hosts = [
        base[:-3] if base.endswith("/v1") else base,
        "https://api.slai.shop",
        "https://slai.shop",
        "https://www.slai.shop",
        "https://app.slai.shop",
        "https://console.slai.shop",
        "https://platform.slai.shop",
    ]
    paths = [
        "/dashboard/billing",
        "/dashboard/usage",
        "/dashboard/api-key",
        "/v1/dashboard/billing",
        "/api/dashboard/billing",
        "/api/v1/dashboard/billing",
        "/dashboard/billing.json",
        "/api/billing",
        "/api/v1/billing",
        "/api/v1/billing/credits",
        "/api/v1/credits",
        "/v1/credits",
        "/credits",
        "/api/v1/account",
        "/api/v1/me",
        "/v1/me",
        "/user/balance",
        "/v1/user/balance",
    ]
    headers_list = [
        {"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
        {"Authorization": f"Bearer {api_key}", "Accept": "application/json", "Content-Type": "application/json"},
        {"X-API-Key": api_key, "Accept": "application/json"},
        {"Authorization": api_key, "Accept": "application/json"},
    ]
    hits = []
    async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
        for host in hosts:
            for path in paths:
                url = host.rstrip("/") + path
                for headers in headers_list:
                    try:
                        resp = await client.get(url, headers=headers)
                    except Exception as e:
                        print("ERR", url, type(e).__name__)
                        break
                    ctype = resp.headers.get("content-type", "")
                    text = (resp.text or "")[:250].replace("\n", " ")
                    if resp.status_code in {401, 403, 200, 302} or ("json" in ctype and resp.status_code < 500):
                        auth = next(iter(headers))
                        print(f"{resp.status_code} {auth} {url}")
                        print(" ", ctype[:50], "|", text[:200])
                    if resp.status_code == 200 and "json" in ctype:
                        try:
                            payload = resp.json()
                        except Exception:
                            continue
                        print(" JSON", json.dumps(payload)[:600])
                        hits.append(url)
                        # keep scanning a bit but note hit
                        break
    print("HITS", hits or "none")
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
        out = stdout.read().decode(errors="replace")
        sys.stdout.write(out)
        err = stderr.read().decode(errors="replace")
        if err.strip():
            sys.stderr.write(err[-3000:])
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
