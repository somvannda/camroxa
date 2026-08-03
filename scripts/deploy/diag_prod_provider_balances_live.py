#!/usr/bin/env python3
"""Diagnose provider-key-balances on production with live service call."""
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


CMD = r"""
cd /opt/camxora/repo
set -a
# load PLATFORM_* without breaking on spaces poorly; use python dotenv-ish
set +a
PYTHONPATH=/opt/camxora/repo /opt/camxora/repo/platform_api/.venv/bin/python - <<'PY'
import asyncio, json, os, re
from pathlib import Path

# Load .env manually
env_path = Path('platform_api/.env')
for line in env_path.read_text(encoding='utf-8', errors='replace').splitlines():
    line=line.strip()
    if not line or line.startswith('#') or '=' not in line:
        continue
    k, _, v = line.partition('=')
    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

from platform_api.dependencies import (
    get_db_pool,
    get_provider_key_balance_service,
    get_redis,
)

async def boot():
    # mimic API lifespan pool init if needed
    import platform_api.dependencies as deps
    if getattr(deps, '_db_pool', None) is None:
        import asyncpg
        dsn = os.environ['PLATFORM_DATABASE_URL'].replace('postgresql+asyncpg://','postgresql://',1)
        deps._db_pool = await asyncpg.create_pool(dsn, min_size=1, max_size=2)
    if getattr(deps, '_redis', None) is None:
        import redis.asyncio as redis
        deps._redis = redis.from_url(os.environ['PLATFORM_REDIS_URL'], decode_responses=True)

async def main():
    await boot()
    svc = get_provider_key_balance_service()
    print('service', type(svc))
    data = await svc.get_all_balances(force_refresh=True)
    print('checked_at', data.get('checked_at'))
    providers = data.get('providers') or []
    print('provider_groups', len(providers))
    for g in providers:
        print('GROUP', g.get('provider'), 'error', g.get('error'), 'keys', len(g.get('keys') or []))
        for k in (g.get('keys') or []):
            print(' ', {
                'label': k.get('label'),
                'fetch_status': k.get('fetch_status'),
                'balance': k.get('balance'),
                'display': k.get('display'),
                'unit': k.get('unit'),
                'error': (k.get('error') or '')[:180],
            })
    # also hit HTTP route shape via openapi presence
    import urllib.request, urllib.error
    try:
        with urllib.request.urlopen('http://127.0.0.1:8100/api/v1/admin/provider-key-balances?refresh=true', timeout=20) as r:
            print('HTTP', r.status)
    except urllib.error.HTTPError as e:
        print('HTTP', e.code, e.read()[:120].decode())

asyncio.run(main())
PY
"""


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
        _, stdout, stderr = client.exec_command(CMD, get_pty=True, timeout=180)
        out = stdout.read().decode(errors="replace")
        err = stderr.read().decode(errors="replace")
        print(out.encode("ascii", "replace").decode("ascii"))
        if err.strip():
            print("STDERR:", err.encode("ascii", "replace").decode("ascii")[:4000], file=sys.stderr)
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
