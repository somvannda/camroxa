#!/usr/bin/env python3
"""READ-ONLY: quantify the Free-plan daily period-grant leak in production."""

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

echo '=== A. Free-plan grant lots per user ==='
$PSQL -c "
SELECT u.email,
  COUNT(l.*) AS grant_lots,
  ROUND(SUM(l.amount_units)/10000.0,2) AS granted_credits,
  ROUND(SUM(l.remaining_units)/10000.0,2) AS lot_remaining,
  MIN(l.period_start) AS first_period, MAX(l.period_start) AS last_period
FROM credit_wallet_lots l JOIN users u ON u.id=l.user_id
WHERE l.tag='grant'
GROUP BY u.email ORDER BY grant_lots DESC, granted_credits DESC;
"

echo '=== B. Daily mint rate (all grant lots, by period_start) ==='
$PSQL -c "
SELECT period_start, COUNT(*) AS lots, COUNT(DISTINCT user_id) AS users,
  ROUND(SUM(amount_units)/10000.0,2) AS credits_minted
FROM credit_wallet_lots WHERE tag='grant'
GROUP BY period_start ORDER BY period_start DESC LIMIT 30;
"

echo '=== C. v3_period_grant totals ==='
$PSQL -c "
SELECT COUNT(*) AS txns, COUNT(DISTINCT user_id) AS users,
  ROUND(SUM(amount)/10000.0,2) AS credits
FROM credit_transactions WHERE reason='v3_period_grant' AND direction='credit';
"

echo '=== D. Free users who spent (debits) + outstanding ==='
$PSQL -c "
WITH free_plan AS (SELECT id FROM plans WHERE lower(name)='free' AND is_active=true ORDER BY updated_at DESC LIMIT 1),
resolved AS (
  SELECT u.id, COALESCE(
    (SELECT 1 FROM licenses l WHERE l.user_id=u.id AND l.status='active' AND (l.expires_at IS NULL OR l.expires_at>NOW()) LIMIT 1),
    (SELECT 1 FROM web_subscriptions ws JOIN plans p ON p.id=ws.plan_id WHERE ws.user_id=u.id AND ws.status='active' AND ws.current_period_end>NOW() AND p.price_cents>0 LIMIT 1)
  ) AS has_paid
  FROM users u WHERE COALESCE(u.status,'active') <> 'deleted'
)
SELECT
  COUNT(*) FILTER (WHERE r.has_paid IS NULL) AS free_users,
  COUNT(*) FILTER (WHERE r.has_paid IS NULL AND COALESCE(w.balance,0)>0) AS free_with_balance,
  ROUND(COALESCE(SUM(w.balance) FILTER (WHERE r.has_paid IS NULL),0)/10000.0,2) AS free_outstanding_credits,
  ROUND(COALESCE(SUM(t.amt) FILTER (WHERE r.has_paid IS NULL),0)/10000.0,2) AS free_lifetime_spent
FROM resolved r
LEFT JOIN credit_wallets w ON w.user_id=r.id
LEFT JOIN LATERAL (SELECT SUM(amount) AS amt FROM credit_transactions t WHERE t.user_id=r.id AND t.direction='debit') t ON true;
"

echo '=== E. starter_monthly grants ==='
$PSQL -c "
SELECT u.email, ROUND(w.balance/10000.0,2) AS wallet,
  (SELECT COUNT(*) FROM credit_wallet_lots l WHERE l.user_id=u.id AND l.tag='grant') AS grant_lots,
  (SELECT ROUND(COALESCE(SUM(l.amount_units),0)/10000.0,2) FROM credit_wallet_lots l WHERE l.user_id=u.id AND l.tag='grant') AS granted
FROM users u JOIN credit_wallets w ON w.user_id=u.id
JOIN web_subscriptions ws ON ws.user_id=u.id AND ws.status='active'
JOIN plans p ON p.id=ws.plan_id AND p.name='starter_monthly';
"

echo '=== F. Grant lots created per day (all tags) ==='
$PSQL -c "
SELECT (created_at AT TIME ZONE 'Asia/Phnom_Penh')::date AS day, tag, COUNT(*) AS lots,
  ROUND(SUM(amount_units)/10000.0,2) AS credits
FROM credit_wallet_lots WHERE created_at >= NOW() - INTERVAL '20 days'
GROUP BY 1,2 ORDER BY 1 DESC, 2;
"

echo FREE_LEAK_DONE
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
    print(f"READ-ONLY free-leak audit on {user}@{host}", flush=True)
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        print(run_cmd(client, CMD, timeout=160), flush=True)
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
