#!/usr/bin/env python3
"""Read-only: inspect the flagged airhemp.com account."""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_production_secrets, resolve_production_ssh, ssh_connect

PRODUCTION_HOST = "82.197.71.248"

CMD = r"""
sudo -u postgres psql -d camxora_platform -P pager=off -c "
SELECT u.email, u.status, u.email_confirmed, u.products, u.created_at,
       (SELECT count(*) FROM suno_tasks s WHERE s.user_id = u.id) AS suno_tasks,
       (SELECT count(*) FROM credit_transactions t WHERE t.user_id = u.id) AS txn_rows,
       (SELECT w.balance FROM credit_wallets w WHERE w.user_id = u.id) AS wallet
FROM users u
WHERE u.id = '08e5ed29-011e-4257-8ac1-664a4525ee0b';
"
echo '=== any other @airhemp.com users? ==='
sudo -u postgres psql -d camxora_platform -P pager=off -c "
SELECT email, status, created_at FROM users
WHERE deleted_at IS NULL AND lower(split_part(email,'@',2)) = 'airhemp.com' ORDER BY created_at;
"
echo '=== airhemp on the guard blocked list? ==='
sudo -u postgres psql -d camxora_platform -P pager=off -t -c "
SELECT CASE WHEN value::text LIKE '%airhemp.com%' THEN 'blocked' ELSE 'NOT blocked' END
FROM system_settings WHERE key = 'signup_blocked_email_domains';
"
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
