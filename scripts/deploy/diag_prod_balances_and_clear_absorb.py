#!/usr/bin/env python3
"""Sample cached provider key balances + clear fail-absorb for one user."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, ssh_connect  # noqa: E402

PRODUCTION_HOST = "82.197.71.248"


def load_env(name: str) -> dict[str, str]:
    data: dict[str, str] = {}
    for line in (ROOT / ".deploy" / name).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        data[key.strip()] = value.strip()
    return data


CMD = r'''
cd /opt/camxora/repo
export $(grep -E '^(PLATFORM_REDIS_URL)=' platform_api/.env | xargs -d '\n')
PYTHONPATH=/opt/camxora/repo /opt/camxora/repo/platform_api/.venv/bin/python - <<'PY'
import asyncio, json, os, redis.asyncio as redis

async def main():
    r = redis.from_url(os.environ["PLATFORM_REDIS_URL"], decode_responses=True)
    cursor=0
    keys=[]
    while True:
        cursor, batch = await r.scan(cursor=cursor, match='provider_key_balance:*', count=200)
        keys.extend(batch)
        if cursor==0: break
    print('balance_cache_keys', len(keys))
    for k in sorted(keys)[:40]:
        raw = await r.get(k)
        try:
            data=json.loads(raw) if raw else None
        except Exception:
            data=raw
        if isinstance(data, dict):
            print(k, {
                'label': data.get('label'),
                'fetch_status': data.get('fetch_status'),
                'balance': data.get('balance'),
                'display': data.get('display'),
                'error': (data.get('error') or '')[:120],
            })
        else:
            print(k, str(data)[:160])

    # clear fail absorb for somvannda today
    uid='2baeaae8-0121-4d98-872d-eff832237f46'
    day_keys=[]
    cursor=0
    while True:
        cursor, batch = await r.scan(cursor=cursor, match=f'fail_absorb:{uid}:*', count=50)
        day_keys.extend(batch)
        if cursor==0: break
    print('before_clear', {k: await r.get(k) for k in day_keys})
    for k in day_keys:
        if k.endswith(':2026-08-03'):
            await r.delete(k)
            print('deleted', k)
    print('after_clear', {k: await r.get(k) for k in day_keys})
    await r.aclose()

asyncio.run(main())
PY
'''


def main() -> int:
    secrets = load_env("secrets.production.env")
    host = secrets.get("PRODUCTION_VPS_HOST") or secrets["VPS_HOST"]
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    client = ssh_connect(
        host,
        secrets.get("PRODUCTION_VPS_USER") or secrets["VPS_USER"],
        ensure_deploy_key(),
        secrets.get("PRODUCTION_VPS_PASSWORD") or secrets.get("VPS_PASSWORD"),
    )
    try:
        _, stdout, stderr = client.exec_command(CMD, get_pty=True, timeout=90)
        print(stdout.read().decode(errors="replace").encode("ascii", "replace").decode("ascii"))
        err = stderr.read().decode(errors="replace")
        if err.strip():
            print("STDERR:", err.encode("ascii", "replace").decode("ascii"), file=sys.stderr)
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
