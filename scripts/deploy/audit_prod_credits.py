#!/usr/bin/env python3
"""READ-ONLY production credit audit: free + starter_monthly wallets after cutover.

Reports per-user wallet vs ledger reconciliation, grant provenance, daily-grant
stacking, and the iamduke account. No writes.

  python scripts/deploy/audit_prod_credits.py --i-mean-production
"""

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

echo '########## 1. SCHEMA ##########'
$PSQL -c "SELECT table_name, column_name, data_type FROM information_schema.columns WHERE table_name IN ('users','plans','credit_wallets','credit_transactions','credit_wallet_lots','web_subscriptions') ORDER BY table_name, ordinal_position;"

echo '########## 2. SETTINGS ##########'
$PSQL -c "SELECT key, value FROM system_settings WHERE key ILIKE '%credit%' OR key ILIKE '%v3%' OR key ILIKE '%free%' OR key ILIKE '%charge%' ORDER BY 1;"

echo '########## 3. PLANS ##########'
$PSQL -c "SELECT id, name, plan_type, plan_kind, price_cents, billing_cycle_days, monthly_credits, daily_credits, monthly_song_limit, is_public, is_active FROM plans ORDER BY plan_type NULLS FIRST, price_cents;"

echo '########## 4. USER COUNTS BY PLAN ##########'
$PSQL -c "
WITH free_plan AS (
  SELECT id, name FROM plans WHERE lower(name)='free' AND is_active=true ORDER BY updated_at DESC LIMIT 1
),
resolved AS (
  SELECT u.id, COALESCE(
    (SELECT p.name FROM licenses l JOIN plans p ON p.id=l.plan_id
      WHERE l.user_id=u.id AND l.status='active' AND (l.expires_at IS NULL OR l.expires_at>NOW())
      ORDER BY l.activated_at DESC LIMIT 1),
    (SELECT p.name FROM web_subscriptions ws JOIN plans p ON p.id=ws.plan_id
      WHERE ws.user_id=u.id AND ws.status='active' AND ws.current_period_end>NOW() AND p.price_cents>0
      ORDER BY ws.current_period_end DESC LIMIT 1),
    (SELECT name FROM free_plan)
  ) AS plan_name
  FROM users u WHERE COALESCE(u.status,'active') <> 'deleted'
)
SELECT plan_name, COUNT(*) AS users,
  ROUND(COALESCE(SUM((SELECT balance FROM credit_wallets w WHERE w.user_id=r.id)),0)/10000.0,2) AS total_wallet_credits
FROM resolved r GROUP BY plan_name ORDER BY users DESC;
"

echo '########## 5. FREE + STARTER USER AUDIT ##########'
$PSQL -c "
WITH free_plan AS (
  SELECT id, name FROM plans WHERE lower(name)='free' AND is_active=true ORDER BY updated_at DESC LIMIT 1
),
resolved AS (
  SELECT u.id AS user_id, u.email, COALESCE(u.status,'active') AS user_status, u.created_at,
    COALESCE(
      (SELECT p.name FROM licenses l JOIN plans p ON p.id=l.plan_id
        WHERE l.user_id=u.id AND l.status='active' AND (l.expires_at IS NULL OR l.expires_at>NOW())
        ORDER BY l.activated_at DESC LIMIT 1),
      (SELECT p.name FROM web_subscriptions ws JOIN plans p ON p.id=ws.plan_id
        WHERE ws.user_id=u.id AND ws.status='active' AND ws.current_period_end>NOW() AND p.price_cents>0
        ORDER BY ws.current_period_end DESC LIMIT 1),
      (SELECT name FROM free_plan)
    ) AS plan_name
  FROM users u WHERE COALESCE(u.status,'active') <> 'deleted'
)
SELECT
  r.email, r.plan_name,
  ROUND(COALESCE(w.balance,0)/10000.0,2) AS wallet,
  ROUND((COALESCE(tx.minted,0)-COALESCE(tx.debited,0))/10000.0,2) AS minted_minus_debited,
  ROUND((COALESCE(w.balance,0)-(COALESCE(tx.minted,0)-COALESCE(tx.debited,0)))/10000.0,2) AS recon_diff,
  ROUND(COALESCE(lot.grant_rem,0)/10000.0,2) AS lot_grant,
  ROUND(COALESCE(lot.daily_rem,0)/10000.0,2) AS lot_daily,
  ROUND(COALESCE(lot.conv_rem,0)/10000.0,2) AS lot_conv,
  ROUND(COALESCE(lot.pack_rem,0)/10000.0,2) AS lot_pack,
  ROUND(COALESCE(tx.minted,0)/10000.0,2) AS minted,
  ROUND(COALESCE(tx.debited,0)/10000.0,2) AS debited,
  COALESCE(tx.n_credit,0) AS n_credit,
  COALESCE(tx.n_debit,0) AS n_debit
FROM resolved r
LEFT JOIN credit_wallets w ON w.user_id=r.user_id
LEFT JOIN LATERAL (
  SELECT SUM(remaining_units) FILTER (WHERE tag='grant') grant_rem,
         SUM(remaining_units) FILTER (WHERE tag='daily_grant') daily_rem,
         SUM(remaining_units) FILTER (WHERE tag='quota_conversion') conv_rem,
         SUM(remaining_units) FILTER (WHERE tag='pack') pack_rem
  FROM credit_wallet_lots l WHERE l.user_id=r.user_id
) lot ON true
LEFT JOIN LATERAL (
  SELECT SUM(amount) FILTER (WHERE direction='credit') minted,
         SUM(amount) FILTER (WHERE direction='debit') debited,
         COUNT(*) FILTER (WHERE direction='credit') n_credit,
         COUNT(*) FILTER (WHERE direction='debit') n_debit
  FROM credit_transactions t WHERE t.user_id=r.user_id
) tx ON true
WHERE r.plan_name ILIKE 'free%' OR r.plan_name ILIKE 'starter%'
ORDER BY r.plan_name, wallet DESC;
"

echo '########## 6. RECONCILIATION MISMATCHES (ALL USERS) ##########'
$PSQL -c "
SELECT u.email,
  ROUND(COALESCE(w.balance,0)/10000.0,2) AS wallet,
  ROUND((COALESCE(tx.minted,0)-COALESCE(tx.debited,0))/10000.0,2) AS ledger_net,
  ROUND((COALESCE(w.balance,0)-(COALESCE(tx.minted,0)-COALESCE(tx.debited,0)))/10000.0,2) AS recon_diff
FROM users u
LEFT JOIN credit_wallets w ON w.user_id=u.id
LEFT JOIN LATERAL (
  SELECT SUM(amount) FILTER (WHERE direction='credit') minted,
         SUM(amount) FILTER (WHERE direction='debit') debited
  FROM credit_transactions t WHERE t.user_id=u.id
) tx ON true
WHERE COALESCE(u.status,'active') <> 'deleted'
  AND ABS(COALESCE(w.balance,0)-(COALESCE(tx.minted,0)-COALESCE(tx.debited,0))) > 1
ORDER BY ABS(COALESCE(w.balance,0)-(COALESCE(tx.minted,0)-COALESCE(tx.debited,0))) DESC;
"

echo '########## 7. DAILY GRANT STACKING (ALL USERS, BY DAY) ##########'
$PSQL -c "
SELECT u.email, (t.created_at AT TIME ZONE 'Asia/Phnom_Penh')::date AS day,
  COUNT(*) AS grants, ROUND(SUM(t.amount)/10000.0,2) AS credits
FROM credit_transactions t JOIN users u ON u.id=t.user_id
WHERE t.reason='v3_daily_grant' AND t.direction='credit'
GROUP BY 1,2 HAVING COUNT(*) > 1 OR SUM(t.amount) > 500000
ORDER BY grants DESC, credits DESC LIMIT 100;
"

echo '########## 8. CREDIT TXNS BY REASON (ALL USERS) ##########'
$PSQL -c "
SELECT reason, direction, COUNT(*) AS n, ROUND(SUM(amount)/10000.0,2) AS credits
FROM credit_transactions GROUP BY 1,2 ORDER BY credits DESC LIMIT 60;
"

echo '########## 9. IAMDUKE DETAIL ##########'
$PSQL -c "SELECT id, email, COALESCE(status,'active') AS status, created_at FROM users WHERE email='iamduke1987@gmail.com';"
$PSQL -c "SELECT w.user_id, ROUND(w.balance/10000.0,2) AS wallet_credits, w.updated_at FROM credit_wallets w JOIN users u ON u.id=w.user_id WHERE u.email='iamduke1987@gmail.com';"
$PSQL -c "SELECT l.id, l.tag, ROUND(l.amount_units/10000.0,2) AS amount, ROUND(l.remaining_units/10000.0,2) AS remaining, l.expires_at, l.period_start, l.created_at FROM credit_wallet_lots l JOIN users u ON u.id=l.user_id WHERE u.email='iamduke1987@gmail.com' ORDER BY l.created_at;"
$PSQL -c "SELECT t.created_at, t.direction, t.reason, ROUND(t.amount/10000.0,2) AS credits, t.ref_id FROM credit_transactions t JOIN users u ON u.id=t.user_id WHERE u.email='iamduke1987@gmail.com' ORDER BY t.created_at;"
$PSQL -c "SELECT l.id, p.name AS plan_name, l.status, l.activated_at, l.expires_at FROM licenses l LEFT JOIN plans p ON p.id=l.plan_id JOIN users u ON u.id=l.user_id WHERE u.email='iamduke1987@gmail.com';"
$PSQL -c "SELECT ws.id, p.name AS plan_name, ws.status, ws.monthly_credits_granted, ws.monthly_credits_used, ws.topup_credits_balance, ws.current_period_start, ws.current_period_end FROM web_subscriptions ws LEFT JOIN plans p ON p.id=ws.plan_id JOIN users u ON u.id=ws.user_id WHERE u.email='iamduke1987@gmail.com';"

echo '########## 10. BILLING CONVERSION RUNS ##########'
$PSQL -c "SELECT u.email, r.leftover_packages, r.credits_minted, ROUND(r.amount_units/10000.0,2) AS credits, r.status, r.dry_run, r.created_at FROM billing_conversion_runs r JOIN users u ON u.id=r.user_id ORDER BY r.created_at;"

echo AUDIT_DONE
"""


def run_cmd(client, cmd: str, timeout: int = 180) -> str:
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
    if "--i-mean-production" not in sys.argv:
        print("Read-only production credit audit. Re-run with --i-mean-production")
        return 2
    secrets = load_production_secrets()
    host, user, password = resolve_production_ssh(secrets)
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    print(f"READ-ONLY credit audit on {user}@{host}", flush=True)
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        print(run_cmd(client, CMD, timeout=170), flush=True)
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
