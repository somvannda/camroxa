#!/usr/bin/env python3
"""Read-only: production schema facts for the signup email-domain guard hotfix."""
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
SELECT '=== value_type samples ===';
SELECT DISTINCT value_type FROM system_settings;
SELECT '=== existing signup/block/domain keys ===';
SELECT key, value_type, left(value, 160) AS value FROM system_settings
WHERE key ILIKE '%signup%' OR key ILIKE '%block%' OR key ILIKE '%domain%' OR key ILIKE '%disposable%';
SELECT '=== users columns ===';
SELECT column_name, data_type FROM information_schema.columns
WHERE table_name = 'users' ORDER BY ordinal_position;
SELECT '=== users.email index / products ===';
SELECT column_name, data_type FROM information_schema.columns
WHERE table_name = 'user_products' ORDER BY ordinal_position;
SELECT '=== paid tables present? ===';
SELECT table_name FROM information_schema.tables
WHERE table_name IN ('licenses','subscriptions','plans','entitlements','user_products','usage_periods');
SELECT '=== top email domains by active users ===';
SELECT split_part(email, '@', 2) AS domain, count(*) AS n
FROM users WHERE deleted_at IS NULL
GROUP BY domain ORDER BY n DESC LIMIT 25;
SELECT '=== licenses columns ===';
SELECT column_name FROM information_schema.columns WHERE table_name = 'licenses' ORDER BY ordinal_position;
SELECT '=== subscriptions columns ===';
SELECT column_name FROM information_schema.columns WHERE table_name = 'subscriptions' ORDER BY ordinal_position;
SQL
echo '=== status values licenses/subscriptions ==='
sudo -u postgres psql -d camxora_platform -P pager=off -c "
SELECT 'licenses', status, count(*) FROM licenses GROUP BY status
UNION ALL SELECT 'subscriptions', status, count(*) FROM subscriptions GROUP BY status;
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
