#!/usr/bin/env python3
"""READ-ONLY: detail for accounts whose wallet does not reconcile to the ledger."""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_production_secrets, resolve_production_ssh, ssh_connect

PRODUCTION_HOST = "82.197.71.248"
EMAILS = (
    "edmbass1@gmail.com",
    "somvannda@gmail.com",
    "tepchanpanharith@gmail.com",
    "sophay@camxora.com",
)

CMD = r"""
set +e
PSQL="sudo -u postgres psql -d camxora_platform -P pager=off -A -F| "
for E in edmbass1@gmail.com somvannda@gmail.com tepchanpanharith@gmail.com sophay@camxora.com; do
  echo "##### $E #####"
  $PSQL -c "SELECT u.id, u.email, COALESCE(u.status,'active') AS status FROM users u WHERE u.email='$E';"
  $PSQL -c "SELECT ROUND(w.balance/10000.0,2) AS wallet_credits, w.updated_at FROM credit_wallets w JOIN users u ON u.id=w.user_id WHERE u.email='$E';"
  echo '--- transactions ---'
  $PSQL -c "SELECT t.created_at, t.direction, t.reason, ROUND(t.amount/10000.0,2) AS credits, t.ref_id FROM credit_transactions t JOIN users u ON u.id=t.user_id WHERE u.email='$E' ORDER BY t.created_at;"
  echo '--- lots ---'
  $PSQL -c "SELECT l.tag, ROUND(l.amount_units/10000.0,2) AS amount, ROUND(l.remaining_units/10000.0,2) AS remaining, l.period_start, l.created_at FROM credit_wallet_lots l JOIN users u ON u.id=l.user_id WHERE u.email='$E' ORDER BY l.created_at;"
  echo '--- conversion runs ---'
  $PSQL -c "SELECT r.leftover_packages, r.credits_minted, ROUND(r.amount_units/10000.0,2) AS credits, r.status, r.dry_run, r.created_at FROM billing_conversion_runs r JOIN users u ON u.id=r.user_id WHERE u.email='$E' ORDER BY r.created_at;"
  echo '--- licenses ---'
  $PSQL -c "SELECT p.name AS plan_name, l.status, l.activated_at, l.expires_at FROM licenses l LEFT JOIN plans p ON p.id=l.plan_id JOIN users u ON u.id=l.user_id WHERE u.email='$E';"
  echo '--- web_subs ---'
  $PSQL -c "SELECT p.name AS plan_name, ws.status, ws.monthly_credits_granted, ws.monthly_credits_used, ws.topup_credits_balance, ws.current_period_end FROM web_subscriptions ws LEFT JOIN plans p ON p.id=ws.plan_id JOIN users u ON u.id=ws.user_id WHERE u.email='$E';"
done
echo RECON_DETAIL_DONE
"""


def run_cmd(client, cmd: str, timeout: int = 170) -> str:
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
        print(run_cmd(client, CMD, timeout=160), flush=True)
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
