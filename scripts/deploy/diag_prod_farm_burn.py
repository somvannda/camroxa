#!/usr/bin/env python3
"""Read-only: quantify free-credit burn by suspected farm accounts."""
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
SELECT '=== credit_wallets cols ===';
SELECT column_name FROM information_schema.columns WHERE table_name='credit_wallets' ORDER BY ordinal_position;
SELECT '=== credit_transactions cols ===';
SELECT column_name FROM information_schema.columns WHERE table_name='credit_transactions' ORDER BY ordinal_position;
SELECT '=== web_music_daily_usage cols ===';
SELECT column_name FROM information_schema.columns WHERE table_name='web_music_daily_usage' ORDER BY ordinal_position;
SELECT '=== suno_tasks cols (subset) ===';
SELECT column_name FROM information_schema.columns WHERE table_name='suno_tasks' ORDER BY ordinal_position;

SELECT '=== farm users: id/email/wallet ===';
SELECT u.id, u.email, w.credits AS wallet, w.updated_at AS wallet_ts
FROM users u
LEFT JOIN credit_wallets w ON w.user_id = u.id
WHERE u.email ILIKE '%@bowlfuel.com' OR u.email ILIKE '%@beiwoh.com'
   OR u.email ILIKE '%@hutdot.com' OR u.email ILIKE '%@hgbgroup.com';

SELECT '=== farm users: credit_transactions summary ===';
SELECT u.email, t.reason, count(*), coalesce(sum(t.amount),0) AS total_amount
FROM users u
JOIN credit_transactions t ON t.user_id = u.id
WHERE u.email ILIKE '%@bowlfuel.com' OR u.email ILIKE '%@beiwoh.com'
   OR u.email ILIKE '%@hutdot.com' OR u.email ILIKE '%@hgbgroup.com'
GROUP BY u.email, t.reason ORDER BY u.email, t.reason;

SELECT '=== farm users: daily usage + suno tasks ===';
SELECT u.email,
  (SELECT count(*) FROM web_music_daily_usage d WHERE d.user_id = u.id) AS usage_rows,
  (SELECT count(*) FROM suno_tasks s WHERE s.user_id = u.id) AS suno_tasks
FROM users u
WHERE u.email ILIKE '%@bowlfuel.com' OR u.email ILIKE '%@beiwoh.com'
   OR u.email ILIKE '%@hutdot.com' OR u.email ILIKE '%@hgbgroup.com';
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
