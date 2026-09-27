#!/usr/bin/env python3
"""READ-ONLY: locate pre-cutover DB backups and credit snapshot CSVs on prod."""

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
echo '=== /opt/camxora/backups ==='
ls -lah /opt/camxora/backups/ 2>/dev/null
echo '=== find *.dump / *.sql / *.tgz ==='
find /opt/camxora -maxdepth 3 \( -name '*.dump' -o -name '*.sql' -o -name '*.tgz' -o -name '*.tar.gz' \) -printf '%TY-%Tm-%Td %TH:%TM  %10s  %p\n' 2>/dev/null | sort | tail -40
echo '=== find credits-snapshot csv ==='
find / -xdev -name 'credits-snapshot*' -printf '%TY-%Tm-%Td %TH:%TM  %10s  %p\n' 2>/dev/null | sort
find / -xdev -name '*credits*csv' -printf '%TY-%Tm-%Td %TH:%TM  %10s  %p\n' 2>/dev/null | sort | tail -20
echo '=== /tmp listing ==='
ls -lah /tmp 2>/dev/null | head -50
echo '=== db size + latest txns ==='
sudo -u postgres psql -d camxora_platform -P pager=off -A -F'|' -c "SELECT pg_size_pretty(pg_database_size('camxora_platform')) AS db_size;"
sudo -u postgres psql -d camxora_platform -P pager=off -A -F'|' -c "SELECT MIN(created_at) AS first_tx, MAX(created_at) AS last_tx, COUNT(*) FROM credit_transactions;"
sudo -u postgres psql -d camxora_platform -P pager=off -A -F'|' -c "SELECT MIN(created_at) AS first_lot, MAX(created_at) AS last_lot, COUNT(*) FROM credit_wallet_lots;"
echo PROBE_SNAPSHOTS_DONE
"""


def run_cmd(client, cmd: str, timeout: int = 120) -> str:
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
        print(run_cmd(client, CMD, timeout=110), flush=True)
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
