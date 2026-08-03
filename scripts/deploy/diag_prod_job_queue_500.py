#!/usr/bin/env python3
"""Capture authenticated job-queue metrics failure details from production logs."""
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
echo '=== main.py admin_pipeline markers ==='
grep -n 'admin_pipeline' /opt/camxora/repo/platform_api/main.py || echo NONE
echo '=== wire markers ==='
grep -n 'admin_pipeline' /opt/camxora/repo/platform_api/wire_dependencies.py || echo NONE
echo '=== job-queue metrics impl head ==='
sed -n '1320,1450p' /opt/camxora/repo/platform_api/routers/admin.py
echo '=== journal job-queue 500 with traceback ==='
journalctl -u camxora-api --since '24 hours ago' --no-pager | grep -n -i 'job-queue\|JobQueue\|metrics' | tail -40
echo '--- last traceback block ---'
journalctl -u camxora-api --since '24 hours ago' --no-pager | grep -A 40 'job-queue/metrics' | tail -80
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
        _, stdout, stderr = client.exec_command(CMD, get_pty=True, timeout=90)
        print(stdout.read().decode(errors="replace").encode("ascii", "replace").decode("ascii"))
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
