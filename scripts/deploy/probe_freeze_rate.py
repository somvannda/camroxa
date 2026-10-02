#!/usr/bin/env python3
"""Check: freeze keys for pich user/IP, rate limiter behavior, latest nginx burst."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import (
    ensure_deploy_key,
    load_production_secrets,
    resolve_production_ssh,
    ssh_connect,
)

PRODUCTION_HOST = "82.197.71.248"

REMOTE_CMD = r"""
set +e
echo '=== freeze keys in redis db1 (user/ip) ==='
redis-cli -n 1 --scan --pattern 'abuse:freeze*' 2>/dev/null | head -30
redis-cli -n 1 --scan --pattern '*freeze*' 2>/dev/null | head -30
echo
echo '=== values for pich ip daily ==='
redis-cli -n 1 get 'abuse:ip_daily:203.147.139.59:2026-09-05' 2>/dev/null
redis-cli -n 1 get 'abuse:ip_daily:203.147.139.59:2026-09-04' 2>/dev/null
echo
echo '=== rate limiter implementation (check method + status codes) ==='
grep -n -B2 -A 45 'class .*RateLimiter\|async def check\b' /opt/camxora/repo/platform_api/services/rate_limiter_service.py 2>/dev/null | head -80
grep -rn 'configure_rate_limiter' /opt/camxora/repo/platform_api/middleware/rate_limit.py 2>/dev/null | head -5
echo
echo '=== nginx: pich generate burst last 10 min ==='
grep '05/Sep/2026:18' /var/log/nginx/access.log 2>/dev/null | grep 'web-music/generate' | tail -15
echo
echo '=== api journal last 3 min (raw) ==='
journalctl -u camxora-api --since "3 minutes ago" --no-pager 2>/dev/null | grep -vE 'get_balance|Balance query|Returning balance' | tail -40
echo FROZEN_CHECK_DONE
"""


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        _, stdout, stderr = client.exec_command(REMOTE_CMD, get_pty=False, timeout=150)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
        if err.strip():
            sys.stderr.write("STDERR: " + err[-1500:] + "\n")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
