#!/usr/bin/env python3
"""Probe production for admin routes that used to work (pipeline, job-queue, balances, fail-absorb)."""
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
set -e
python3 - <<'PY'
import json, subprocess, urllib.request
from pathlib import Path

def http(path: str) -> tuple[int, str]:
    try:
        req = urllib.request.Request('http://127.0.0.1:8100' + path, method='GET')
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read().decode('utf-8', errors='replace')
            return resp.status, body
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        return e.code, body
    except Exception as e:
        return 0, str(e)

print('=== openapi matching paths ===')
try:
    with urllib.request.urlopen('http://127.0.0.1:8100/openapi.json', timeout=30) as resp:
        d = json.load(resp)
    paths = sorted(d.get('paths', {}))
    for p in paths:
        if any(n in p for n in ('fail-absorb', 'provider-key-balances', 'job-queue', 'pipeline')):
            print(p)
    print('TOTAL_PATHS', len(paths))
except Exception as e:
    print('openapi_error', type(e).__name__, e)

print('=== HTTP no-auth ===')
for path in [
    '/api/v1/admin/job-queue/metrics',
    '/api/v1/admin/pipeline/board?limit=50&active_only=true',
    '/api/v1/admin/provider-key-balances?refresh=true',
    '/api/v1/users/2baeaae8-0121-4d98-872d-eff832237f46/fail-absorb',
]:
    code, body = http(path)
    print(code, path)
    print(body[:240].replace('\n', ' '))

print('=== files ===')
base = Path('/opt/camxora/repo/platform_api')
for rel in [
    'routers/admin_pipeline.py',
    'services/admin_pipeline_service.py',
    'services/provider_key_balance_service.py',
    'repositories/job_queue_repo.py',
    'worker.py',
    'main.py',
    'wire_dependencies.py',
    'routers/admin.py',
    'routers/users.py',
]:
    p = base / rel
    print(('OK' if p.is_file() else 'MISSING'), rel, p.stat().st_size if p.is_file() else 0)

print('=== main include_router / imports ===')
main = (base / 'main.py').read_text(errors='replace')
for needle in ['admin_pipeline', 'include_router', 'job_queue', 'provider_key']:
    for i, line in enumerate(main.splitlines(), 1):
        if needle in line:
            print(f'main:{i}:{line.strip()[:160]}')

print('=== admin route markers ===')
admin = (base / 'routers/admin.py').read_text(errors='replace')
for needle in ['provider-key-balances', 'job-queue/metrics', 'pipeline', 'fail-absorb']:
    print(needle, needle in admin)

print('=== users fail-absorb ===')
users = (base / 'routers/users.py').read_text(errors='replace')
print('fail-absorb in users.py', 'fail-absorb' in users)

print('=== wire admin_pipeline ===')
wire = (base / 'wire_dependencies.py').read_text(errors='replace')
print('admin_pipeline in wire', 'admin_pipeline' in wire)
PY

echo '=== journal recent relevant ==='
journalctl -u camxora-api --since '6 hours ago' --no-pager | grep -iE 'job-queue|pipeline/board|provider-key|fail-absorb|Traceback|Error while|500' | tail -80
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
        _, stdout, stderr = client.exec_command(CMD, get_pty=True, timeout=120)
        out = stdout.read().decode(errors="replace")
        err = stderr.read().decode(errors="replace")
        print(out.encode("ascii", "replace").decode("ascii"))
        if err.strip():
            print("STDERR:", err.encode("ascii", "replace").decode("ascii")[:3000], file=sys.stderr)
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
