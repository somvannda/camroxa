#!/usr/bin/env python3
"""Pull production admin fail-absorb UI sources + probe API endpoints."""
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
set -e
echo '=== API listen ==='
ss -lptn | grep -E '8100|8000' || true
echo '=== openapi paths containing absorb/balance ==='
curl -sS http://127.0.0.1:8100/openapi.json | python3 -c "import sys,json; d=json.load(sys.stdin); paths=sorted(d.get('paths',{}));
print('\n'.join(p for p in paths if 'absorb' in p or 'provider-key' in p or 'balance' in p))"
echo '=== provider-key-balances unauthorized body ==='
curl -sS -w '\nHTTP %{http_code}\n' 'http://127.0.0.1:8100/api/v1/admin/provider-key-balances?refresh=true' | tail -20
echo '=== fail-absorb unauthorized ==='
curl -sS -w '\nHTTP %{http_code}\n' 'http://127.0.0.1:8100/api/v1/users/2baeaae8-0121-4d98-872d-eff832237f46/fail-absorb' | tail -10
curl -sS -w '\nHTTP %{http_code}\n' -X POST 'http://127.0.0.1:8100/api/v1/users/2baeaae8-0121-4d98-872d-eff832237f46/fail-absorb/reset' | tail -10
echo '=== admin fail-absorb files ==='
wc -l /opt/camxora/repo/admin_portal/src/hooks/use-fail-absorb.ts /opt/camxora/repo/admin_portal/src/pages/settings/fail-absorb-section.tsx
echo '=== search API for fail absorb routes anywhere ==='
grep -RIn 'fail-absorb\|FailAbsorb\|reset_fail_absorb\|get_fail_absorb' /opt/camxora/repo/platform_api --include='*.py' | head -50
echo '=== recent nginx/admin access for these paths ==='
grep -E 'fail-absorb|provider-key-balances' /var/log/nginx/access.log 2>/dev/null | tail -20 || true
grep -E 'fail-absorb|provider-key-balances' /var/log/nginx/admin* 2>/dev/null | tail -20 || true
ls /var/log/nginx | head
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
        _, stdout, stderr = client.exec_command(CMD, get_pty=True, timeout=120)
        print(stdout.read().decode(errors="replace").encode("ascii", "replace").decode("ascii"))
        err = stderr.read().decode(errors="replace")
        if err.strip():
            print("STDERR:", err.encode("ascii", "replace").decode("ascii"), file=sys.stderr)
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
