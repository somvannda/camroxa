#!/usr/bin/env python3
"""Probe real Suno/Fal balance response shapes on production (admin keys)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, ssh_connect  # noqa: E402

PRODUCTION_HOST = "82.197.71.248"
CMD = r"""
set +e
python3 - <<'PY'
import asyncio, json, os, sys
sys.path.insert(0, "/opt/camxora/repo")
os.chdir("/opt/camxora/repo")

async def main():
    from platform_api.config import get_settings
    from platform_api.dependencies import set_db_pool, set_redis, get_key_pool_service
    import asyncpg, redis.asyncio as redis_async
    import httpx

    settings = get_settings()
    dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=2)
    set_db_pool(pool)
    try:
        r = redis_async.from_url(settings.redis_url, encoding="utf-8", decode_responses=True)
        await r.ping()
        set_redis(r)
    except Exception as e:
        print("redis fail", e)

    kp = get_key_pool_service()
    for provider in ("suno", "fal"):
        keys = await kp.list_keys(provider)
        if not keys:
            print(provider, "NO_KEYS")
            continue
        entry = keys[0]
        api_key = await kp.get_decrypted_key_value(entry.id)
        print("===", provider, entry.label, "===")
        if provider == "suno":
            url = settings.suno_api_base_url.rstrip("/") + "/api/v1/generate/credit"
            headers_list = [
                {"Authorization": f"Bearer {api_key}"},
                {"Authorization": api_key},
            ]
            async with httpx.AsyncClient(timeout=20.0) as client:
                for h in headers_list:
                    resp = await client.get(url, headers={**h, "Accept": "application/json"})
                    print("suno status", resp.status_code, "auth", list(h)[0], list(h.values())[0][:12]+"...")
                    print(resp.text[:800])
                    break
        if provider == "fal":
            url = "https://api.fal.ai/v1/account/billing"
            headers_list = [
                {"Authorization": f"Key {api_key}"},
                {"Authorization": f"Key {api_key.strip()}"},
                {"Authorization": api_key},
                {"Authorization": f"Bearer {api_key}"},
            ]
            async with httpx.AsyncClient(timeout=20.0) as client:
                for h in headers_list:
                    resp = await client.get(url, params={"expand": "credits"}, headers={**h, "Accept": "application/json"})
                    print("fal status", resp.status_code, "hdr", h["Authorization"][:20])
                    print(resp.text[:500])
                    if resp.status_code == 200:
                        break
    await pool.close()

asyncio.run(main())
PY
"""


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
        _, stdout, stderr = client.exec_command(
            "cd /opt/camxora/repo && PLATFORM_ENV_FILE=/opt/camxora/repo/platform_api/.env "
            "set -a; . /opt/camxora/repo/platform_api/.env; set +a; "
            + "bash -lc " + repr(CMD),
            get_pty=True,
        )
        # Simpler: run via systemd env
        cmd2 = (
            "set -a; source /opt/camxora/repo/platform_api/.env; set +a; "
            "cd /opt/camxora/repo; "
            "PYTHONPATH=/opt/camxora/repo /opt/camxora/repo/platform_api/.venv/bin/python - <<'PY'\n"
            "import asyncio, os, sys\n"
            "sys.path.insert(0, '/opt/camxora/repo')\n"
            "async def main():\n"
            "    from platform_api.config import get_settings\n"
            "    from platform_api.dependencies import set_db_pool, set_redis, get_key_pool_service\n"
            "    import asyncpg, redis.asyncio as redis_async, httpx\n"
            "    settings = get_settings()\n"
            "    dsn = settings.database_url.replace('postgresql+asyncpg://', 'postgresql://', 1)\n"
            "    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=2)\n"
            "    set_db_pool(pool)\n"
            "    try:\n"
            "        r = redis_async.from_url(settings.redis_url, encoding='utf-8', decode_responses=True)\n"
            "        await r.ping(); set_redis(r)\n"
            "    except Exception as e:\n"
            "        print('redis', e)\n"
            "    kp = get_key_pool_service()\n"
            "    for provider in ('suno', 'fal'):\n"
            "        keys = await kp.list_keys(provider)\n"
            "        if not keys:\n"
            "            print(provider, 'NO_KEYS'); continue\n"
            "        entry = keys[0]\n"
            "        api_key = await kp.get_decrypted_key_value(entry.id)\n"
            "        print('===', provider, entry.label, '===')\n"
            "        if provider == 'suno':\n"
            "            url = settings.suno_api_base_url.rstrip('/') + '/api/v1/generate/credit'\n"
            "            async with httpx.AsyncClient(timeout=20.0) as client:\n"
            "                for auth in (f'Bearer {api_key}', api_key):\n"
            "                    resp = await client.get(url, headers={'Authorization': auth, 'Accept': 'application/json'})\n"
            "                    print('suno', resp.status_code, auth.split()[0] if ' ' in auth else 'raw')\n"
            "                    print(resp.text[:1000])\n"
            "                    if resp.status_code == 200: break\n"
            "        if provider == 'fal':\n"
            "            url = 'https://api.fal.ai/v1/account/billing'\n"
            "            async with httpx.AsyncClient(timeout=20.0) as client:\n"
            "                for auth in (f'Key {api_key}', api_key, f'Bearer {api_key}'):\n"
            "                    resp = await client.get(url, params={'expand':'credits'}, headers={'Authorization': auth, 'Accept':'application/json'})\n"
            "                    print('fal', resp.status_code, auth[:18])\n"
            "                    print(resp.text[:600])\n"
            "                    if resp.status_code == 200: break\n"
            "    await pool.close()\n"
            "asyncio.run(main())\n"
            "PY"
        )
        _, stdout, stderr = client.exec_command(cmd2, get_pty=True)
        sys.stdout.write(stdout.read().decode(errors="replace"))
        err = stderr.read().decode(errors="replace")
        if err.strip():
            sys.stderr.write(err)
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
