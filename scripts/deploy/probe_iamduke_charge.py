#!/usr/bin/env python3
"""READ-ONLY: iamduke wallet + recent generate charges/refunds."""

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
PSQL="sudo -u postgres psql -d camxora_platform -P pager=off -A -F| "
E=iamduke1987@gmail.com
echo '=== wallet ==='
$PSQL -c "SELECT ROUND(w.balance/10000.0,2) AS wallet, w.updated_at FROM credit_wallets w JOIN users u ON u.id=w.user_id WHERE u.email='$E';"
echo '=== last 30 credit_transactions ==='
$PSQL -c "SELECT t.created_at, t.direction, t.reason, ROUND(t.amount/10000.0,4) AS credits, t.ref_id, t.metadata FROM credit_transactions t JOIN users u ON u.id=t.user_id WHERE u.email='$E' ORDER BY t.created_at DESC LIMIT 30;"
echo '=== lots ==='
$PSQL -c "SELECT l.tag, ROUND(l.amount_units/10000.0,2) AS amount, ROUND(l.remaining_units/10000.0,2) AS remaining, l.period_start, l.expires_at FROM credit_wallet_lots l JOIN users u ON u.id=l.user_id WHERE u.email='$E' ORDER BY l.created_at;"
echo '=== web_music_daily_usage ==='
$PSQL -c "SELECT usage_date, generation_count, credits_used FROM web_music_daily_usage d JOIN users u ON u.id=d.user_id WHERE u.email='$E' ORDER BY usage_date DESC LIMIT 10;"
echo '=== recent suno_tasks ==='
$PSQL -c "SELECT id, status, created_at, updated_at FROM suno_tasks s JOIN users u ON u.id=s.user_id WHERE u.email='$E' ORDER BY s.created_at DESC LIMIT 10;"
echo '=== credit_pricing for music ==='
$PSQL -c "SELECT ai_service, operation_type, sub_model, ROUND(credits_per_operation/10000.0,4) AS credits FROM credit_pricing WHERE operation_type IN ('music','song') ORDER BY ai_service, sub_model;"
echo PROBE_IAMDUKE_CHARGE_DONE
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
