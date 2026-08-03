#!/usr/bin/env python3
"""Fetch fail-absorb admin UI sources and sample provider balance payload on prod."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, ssh_connect  # noqa: E402

PRODUCTION_HOST = "82.197.71.248"
OUT = ROOT / "tmp" / "prod_admin_fail_absorb"


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
set -e
python3 - <<'PY'
from pathlib import Path
files = [
  'admin_portal/src/hooks/use-fail-absorb.ts',
  'admin_portal/src/pages/settings/fail-absorb-section.tsx',
]
# also extract relevant user-detail snippets via sed ranges if needed
for rel in files:
    p = Path('/opt/camxora/repo')/rel
    print('=====FILE', rel, '=====')
    print(p.read_text())
PY

echo '=== sample provider balances via service ==='
cd /opt/camxora/repo
export $(grep -E '^(PLATFORM_DATABASE_URL|PLATFORM_REDIS_URL|PLATFORM_ENCRYPTION_MASTER_KEY)=' platform_api/.env | xargs -d '\n')
PYTHONPATH=/opt/camxora/repo /opt/camxora/repo/platform_api/.venv/bin/python - <<'PY'
import asyncio, json, os
from platform_api.db import create_pool
from platform_api.services.key_encryption import KeyEncryption
from platform_api.services.provider_key_balance_service import ProviderKeyBalanceService
from platform_api.repositories.key_pool_repo import KeyPoolRepository
import redis.asyncio as redis

async def main():
    # Prefer constructing like wire_dependencies if possible; fall back to service internals
    try:
        from platform_api.wire_dependencies import build_provider_key_balance_service
        svc = await build_provider_key_balance_service()
        data = await svc.get_all_balances(force_refresh=True)
        print(json.dumps(data, indent=2, default=str)[:6000])
        return
    except Exception as e:
        print('wire_failed', type(e).__name__, e)

    # Minimal probe: import module and call class if easy
    print('trying direct')
    from platform_api.config import get_settings
    settings = get_settings()
    print('ok settings')

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
        _, stdout, stderr = client.exec_command(CMD, get_pty=True, timeout=180)
        out = stdout.read().decode(errors="replace")
        err = stderr.read().decode(errors="replace")
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "probe.txt").write_text(out + "\n---STDERR---\n" + err, encoding="utf-8")
        print(out.encode("ascii", "replace").decode("ascii")[:12000])
        if err.strip():
            print("STDERR:", err.encode("ascii", "replace").decode("ascii")[:3000], file=sys.stderr)
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
