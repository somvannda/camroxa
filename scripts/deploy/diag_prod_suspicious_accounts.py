#!/usr/bin/env python3
"""Read-only: inspect suspected disposable-domain accounts + paid markers."""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_production_secrets, resolve_production_ssh, ssh_connect

PRODUCTION_HOST = "82.197.71.248"

CMD = r"""
sudo -u postgres psql -d camxora_platform -P pager=off <<'SQL'
SELECT '=== distinct product tags ===';
SELECT DISTINCT unnest(products) AS product FROM users ORDER BY product;
SELECT '=== licenses by status ===';
SELECT status, count(*) FROM licenses GROUP BY status;
SELECT '=== suspicious domain accounts ===';
SELECT email, status, email_confirmed, products, created_at
FROM users
WHERE email ILIKE '%@bowlfuel.com' OR email ILIKE '%@beiwoh.com'
   OR email ILIKE '%@hutdot.com' OR email ILIKE '%@hgbgroup.com'
ORDER BY created_at;
SELECT '=== relevant ledger/wallet/task tables ===';
SELECT table_name FROM information_schema.tables
WHERE table_name ILIKE '%ledger%' OR table_name ILIKE '%wallet%'
   OR table_name ILIKE '%credit%' OR table_name ILIKE '%music%'
   OR table_name ILIKE '%suno%'
ORDER BY table_name;
SQL
"""


def run_cmd(client, cmd: str, timeout: int = 45) -> str:
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
        print(run_cmd(client, CMD, timeout=45), flush=True)
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
