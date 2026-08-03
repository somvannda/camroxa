#!/usr/bin/env python3
"""Re-check restored admin routes after API restart."""
from __future__ import annotations

import sys
import time
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
sleep 10
python3 - <<'PY'
import urllib.request, urllib.error

def hit(path):
    try:
        with urllib.request.urlopen('http://127.0.0.1:8100'+path, timeout=30) as r:
            return r.status, r.read()[:180].decode('utf-8','replace')
    except urllib.error.HTTPError as e:
        return e.code, e.read()[:220].decode('utf-8','replace')
    except Exception as e:
        return 0, str(e)

for p in [
  '/api/v1/admin/job-queue/metrics',
  '/api/v1/admin/pipeline/board?limit=5&active_only=true',
  '/api/v1/admin/provider-key-balances',
  '/api/v1/users/2baeaae8-0121-4d98-872d-eff832237f46/fail-absorb',
]:
    code, body = hit(p)
    print(code, p)
    print(body.replace('\n',' '))

from platform_api.dependencies import get_job_queue_repo
print('get_job_queue_repo_ok', callable(get_job_queue_repo))
PY
systemctl is-active camxora-api
journalctl -u camxora-api -n 40 --no-pager | tail -40
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
        print(stdout.read().decode(errors="replace").encode("ascii", "replace").decode("ascii"))
        err = stderr.read().decode(errors="replace")
        if err.strip():
            print("STDERR:", err.encode("ascii", "replace").decode("ascii")[:3000], file=sys.stderr)
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
