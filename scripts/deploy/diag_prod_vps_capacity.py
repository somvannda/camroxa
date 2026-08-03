#!/usr/bin/env python3
"""Quick production VPS capacity snapshot for worker sizing."""
from __future__ import annotations

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
echo === CPU ===
nproc
lscpu | egrep 'Model name|CPU\(s\)|Thread|Core|Socket' | head -20
echo === MEM ===
free -h
echo === LOAD/DISK ===
uptime
df -h / /opt 2>/dev/null | head -10
echo === CURRENT WORKERS/API ===
systemctl is-active camxora-api camxora-worker 2>/dev/null
systemctl list-units 'camxora-worker*' --no-pager --no-legend 2>/dev/null | head -40
ps -eo rss,pcpu,cmd | grep -E 'platform_api.worker|uvicorn platform_api' | grep -v grep
echo === REDIS/PG ===
systemctl is-active redis-server postgresql 2>/dev/null || systemctl is-active redis postgresql 2>/dev/null
free -m | awk '/Mem:/{printf "mem_used_pct=%.0f\n", ($3/$2)*100}'
echo DONE
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
        _, stdout, stderr = client.exec_command(CMD, get_pty=True)
        sys.stdout.write(stdout.read().decode(errors="replace"))
        err = stderr.read().decode(errors="replace")
        if err.strip():
            sys.stderr.write(err)
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
