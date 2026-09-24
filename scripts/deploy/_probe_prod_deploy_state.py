#!/usr/bin/env python3
"""READ-ONLY: check whether the v3 period-grant fix landed on production."""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_production_secrets, resolve_production_ssh, ssh_connect

PRODUCTION_HOST = "82.197.71.248"

CMD = r"""
set +e
REPO=/opt/camxora/repo/platform_api
echo '--- api active ---'
systemctl is-active camxora-api
echo '--- marker: _resolve_period ---'
grep -c "_resolve_period" $REPO/services/v3/period_grant_service.py
echo '--- marker: consume_lots ---'
grep -c "consume_lots" $REPO/repositories/credit_repo.py
echo '--- mtimes ---'
ls -la --time-style=+%Y-%m-%dT%H:%M:%S $REPO/services/v3/period_grant_service.py $REPO/repositories/credit_repo.py
echo '--- api start time ---'
systemctl show camxora-api -p ExecMainStartTimestamp -p MainPID
echo '--- health ---'
curl -sf http://127.0.0.1:8100/health | head -c 300 || curl -sf http://127.0.0.1:8000/health | head -c 300 || echo HEALTH_FAIL
echo
echo '--- workers ---'
systemctl list-units 'camxora-worker*' --type=service --state=running --no-pager --no-legend | awk '{print $1, $4}' | head -20
echo '--- lingering deploy procs ---'
pgrep -af 'camxora-src|sync_platform|tar -xzf' | head -10 || echo NONE
echo PROBE_DEPLOY_DONE
"""


def run_cmd(client, cmd: str, timeout: int = 90) -> str:
    chan = client.get_transport().open_session()
    chan.settimeout(timeout)
    chan.exec_command(cmd)
    out = b""
    started = time.time()
    while True:
        if chan.recv_ready():
            chunk = chan.recv(65535)
            if not chunk:
                break
            out += chunk
        if chan.exit_status_ready():
            while chan.recv_ready():
                out += chan.recv(65535)
            break
        if time.time() - started > timeout:
            out += b"\nTIMEOUT\n"
            break
        time.sleep(0.1)
    return out.decode("utf-8", errors="replace")


def main() -> int:
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        print(run_cmd(client, CMD, timeout=80), flush=True)
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
