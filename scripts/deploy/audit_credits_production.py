#!/usr/bin/env python3
"""Read-only credit audit on PRODUCTION (host 82.197.71.248).

Answers:
  1. Are credit balances correct? (wallet vs ledger reconciliation)
  2. Who obtained credits? (credit-direction ledger rows by reason/user)
  3. Who are the top credit burners on the WEB surface?

Web-surface attribution (authoritative):
  * Web songs live in ``suno_tasks`` with ``source = 'web_music'``
    (desktop/studio = ``'studio'``) — see telegram_ops_commands.fetch_burncredit_stats.
  * When the web app charges under v3 it stores ``reason = 'v3_<op>'`` and then
    rewrites the debit's ``ref_id`` to the web Suno task id
    (web_music_service._link_generation_debit_reference). ``v3_music`` is shared
    by web AND desktop, so the reason alone cannot separate them — the
    ``ref_id -> suno_tasks(source='web_music')`` linkage does.
  * Legacy (v3 flag off) web debits use ``reason LIKE 'consumed_web_music%'``.

Never writes anything. Refuses to run against any non-production host.

  python scripts/deploy/audit_credits_production.py --i-mean-production
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts" / "deploy"
sys.path.insert(0, str(DEPLOY / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(DEPLOY))

from deploy import ensure_deploy_key, ssh_connect  # noqa: E402

PRODUCTION_HOST = "82.197.71.248"

# A web-music debit is either a legacy web reason, or a v3 debit whose ref_id
# points at a web Suno task (source='web_music').
WEB_DEBIT_PRED = (
    "((t.reason LIKE 'consumed_web_music%') "
    "OR (t.ref_id IN (SELECT tid FROM web_task)))"
)
WEB_REFUND_PRED = "(t.reason LIKE 'refunded_web_music%')"
LEGACY_WEB_WHERE = "(reason LIKE 'consumed_web_music%' OR reason LIKE 'refunded_web_music%')"

QUERIES: list[tuple[str, str]] = [
    (
        "1. LEDGER REASON BREAKDOWN (all directions)",
        """
SELECT COALESCE(reason, '(null)') AS reason, direction,
       COUNT(*) AS n,
       COUNT(DISTINCT user_id) AS users,
       ROUND(SUM(amount) / 10000.0, 2) AS credits
FROM credit_transactions
GROUP BY reason, direction
ORDER BY credits DESC
""",
    ),
    (
        "2. WALLET vs LEDGER RECONCILIATION (mismatches only)",
        """
WITH ledger AS (
  SELECT user_id,
         COALESCE(SUM(amount) FILTER (WHERE direction = 'credit'), 0) AS credit_sum,
         COALESCE(SUM(amount) FILTER (WHERE direction = 'refund'), 0) AS refund_sum,
         COALESCE(SUM(amount) FILTER (WHERE direction = 'debit'), 0) AS debit_sum
  FROM credit_transactions
  GROUP BY user_id
)
SELECT u.email,
       ROUND(COALESCE(w.balance, 0) / 10000.0, 4) AS wallet_credits,
       ROUND((COALESCE(l.credit_sum, 0) + COALESCE(l.refund_sum, 0)
              - COALESCE(l.debit_sum, 0)) / 10000.0, 4) AS ledger_net_credits,
       ROUND((COALESCE(w.balance, 0)
              - (COALESCE(l.credit_sum, 0) + COALESCE(l.refund_sum, 0)
                 - COALESCE(l.debit_sum, 0))) / 10000.0, 4) AS diff_credits
FROM users u
LEFT JOIN credit_wallets w ON w.user_id = u.id
LEFT JOIN ledger l ON l.user_id = u.id
WHERE COALESCE(w.balance, 0)
      <> (COALESCE(l.credit_sum, 0) + COALESCE(l.refund_sum, 0) - COALESCE(l.debit_sum, 0))
ORDER BY ABS(COALESCE(w.balance, 0)
             - (COALESCE(l.credit_sum, 0) + COALESCE(l.refund_sum, 0)
                - COALESCE(l.debit_sum, 0))) DESC
""",
    ),
    (
        "3. WALLET TOTALS (sanity)",
        """
SELECT
  (SELECT COUNT(*) FROM users) AS users,
  (SELECT COUNT(*) FROM credit_wallets) AS wallets,
  ROUND((SELECT COALESCE(SUM(balance), 0) FROM credit_wallets) / 10000.0, 2) AS total_wallet_credits,
  ROUND((SELECT COALESCE(SUM(amount), 0) FROM credit_transactions WHERE direction = 'credit') / 10000.0, 2) AS total_credited,
  ROUND((SELECT COALESCE(SUM(amount), 0) FROM credit_transactions WHERE direction = 'refund') / 10000.0, 2) AS total_refunded,
  ROUND((SELECT COALESCE(SUM(amount), 0) FROM credit_transactions WHERE direction = 'debit') / 10000.0, 2) AS total_debited
""",
    ),
    (
        "4. USERS WHO OBTAINED CREDITS (credit direction, by source)",
        """
SELECT u.email,
       ROUND(SUM(t.amount) / 10000.0, 2) AS total_credited,
       COUNT(*) AS credit_rows,
       ROUND(SUM(t.amount) FILTER (WHERE t.reason = 'v3_daily_grant') / 10000.0, 2) AS daily_grant,
       ROUND(SUM(t.amount) FILTER (WHERE t.reason = 'v3_period_grant') / 10000.0, 2) AS period_grant,
       ROUND(SUM(t.amount) FILTER (WHERE t.reason = 'v3_quota_conversion') / 10000.0, 2) AS quota_conversion,
       ROUND(SUM(t.amount) FILTER (WHERE t.reason = 'v3_web_remaining') / 10000.0, 2) AS web_leftover,
       ROUND(SUM(t.amount) FILTER (WHERE t.reason = 'v3_pack') / 10000.0, 2) AS packs,
       ROUND(SUM(t.amount) FILTER (WHERE t.reason LIKE 'admin%') / 10000.0, 2) AS admin
FROM credit_transactions t
JOIN users u ON u.id = t.user_id
WHERE t.direction = 'credit'
GROUP BY u.email
ORDER BY total_credited DESC
""",
    ),
    (
        "5. WEB vs STUDIO ATTRIBUTION of v3 debits (via suno_tasks.source linkage)",
        """
SELECT t.reason,
       CASE WHEN st.id IS NULL THEN 'unlinked'
            WHEN st.source = 'web_music' THEN 'web'
            ELSE COALESCE(st.source, 'studio') END AS surface,
       COUNT(*) AS n,
       COUNT(DISTINCT t.user_id) AS users,
       ROUND(SUM(t.amount) / 10000.0, 2) AS credits
FROM credit_transactions t
LEFT JOIN suno_tasks st ON st.id::text = t.ref_id::text
WHERE t.direction = 'debit' AND t.reason LIKE 'v3_%'
GROUP BY 1, 2
ORDER BY credits DESC
""",
    ),
    (
        "6. TOP WEB BURNERS (web ref_id linkage + legacy web reasons; debits minus refunds)",
        f"""
WITH web_task AS (
  SELECT id::text AS tid FROM suno_tasks WHERE source = 'web_music'
),
burn AS (
  SELECT t.user_id,
         SUM(t.amount) FILTER (WHERE t.direction = 'debit' AND {WEB_DEBIT_PRED}) AS debit_sum,
         SUM(t.amount) FILTER (WHERE {WEB_REFUND_PRED}) AS refund_sum,
         COUNT(*) FILTER (WHERE t.direction = 'debit' AND {WEB_DEBIT_PRED}) AS debit_events
  FROM credit_transactions t
  GROUP BY t.user_id
)
SELECT u.email,
       ROUND((COALESCE(b.debit_sum, 0) - COALESCE(b.refund_sum, 0)) / 10000.0, 2) AS web_net_credits,
       COALESCE(b.debit_events, 0) AS web_debit_events,
       ROUND(COALESCE(b.debit_sum, 0) / 10000.0, 2) AS web_debits,
       ROUND(COALESCE(b.refund_sum, 0) / 10000.0, 2) AS web_refunds,
       (SELECT COUNT(*) FROM suno_tasks st
         WHERE st.user_id = u.id AND st.source = 'web_music') AS web_songs
FROM users u
JOIN burn b ON b.user_id = u.id
WHERE COALESCE(b.debit_sum, 0) > 0
ORDER BY web_net_credits DESC
""",
    ),
    (
        "7. WEB SONGS CREATED per user (suno_tasks.source = 'web_music') — surface cross-check",
        """
SELECT u.email, COUNT(*) AS web_songs,
       MIN(st.created_at)::date AS first_song,
       MAX(st.created_at)::date AS last_song
FROM suno_tasks st
JOIN users u ON u.id = st.user_id
WHERE st.source = 'web_music'
GROUP BY u.email
ORDER BY web_songs DESC
""",
    ),
    (
        "8. ATTRIBUTION EDGE CHECK — web-song creators with UNLINKED v3_music debits",
        """
WITH wt AS (SELECT id::text AS tid, user_id FROM suno_tasks WHERE source = 'web_music')
SELECT u.email,
       (SELECT COUNT(*) FROM wt WHERE wt.user_id = u.id) AS web_songs,
       COUNT(*) FILTER (WHERE t.reason = 'v3_music' AND t.ref_id IN (SELECT tid FROM wt)) AS music_web_n,
       COUNT(*) FILTER (WHERE t.reason = 'v3_music' AND t.ref_id NOT IN (SELECT tid FROM wt)) AS music_other_n,
       ROUND(SUM(t.amount) FILTER (WHERE t.reason = 'v3_music' AND t.ref_id NOT IN (SELECT tid FROM wt)) / 10000.0, 2) AS music_other_credits
FROM users u
JOIN credit_transactions t ON t.user_id = u.id
WHERE u.id IN (SELECT user_id FROM wt)
GROUP BY u.id, u.email
HAVING COUNT(*) FILTER (WHERE t.reason = 'v3_music' AND t.ref_id NOT IN (SELECT tid FROM wt)) > 0
ORDER BY music_other_credits DESC
""",
    ),
    (
        "9. LEGACY-ONLY WEB BURN (consumed_web_music% / refunded_web_music%) — cross-check",
        f"""
SELECT u.email,
       ROUND((COALESCE(SUM(t.amount) FILTER (WHERE t.direction = 'debit'), 0)
              - COALESCE(SUM(t.amount) FILTER (WHERE t.direction <> 'debit'), 0)) / 10000.0, 2) AS web_net_credits,
       COUNT(*) FILTER (WHERE t.direction = 'debit') AS debit_events
FROM credit_transactions t
JOIN users u ON u.id = t.user_id
WHERE {LEGACY_WEB_WHERE}
GROUP BY u.email
ORDER BY web_net_credits DESC
""",
    ),
    (
        "10. GRANT PROVENANCE — every credit row for the named accounts",
        """
SELECT u.email,
       t.reason,
       ROUND(t.amount / 10000.0, 2) AS credits,
       t.direction,
       t.ref_id,
       COALESCE(t.metadata::text, '') AS metadata,
       to_char(t.created_at, 'YYYY-MM-DD HH24:MI') AS created_at
FROM credit_transactions t
JOIN users u ON u.id = t.user_id
WHERE u.email IN (
    'pich.sou11@gmail.com', 'rinmakara2050@gmail.com', 'iamduke1987@gmail.com',
    'ponlorkleav168@gmail.com', 'khunmao.kh@gmail.com', 'vaththary@gmail.com',
    'hinseyha92@gmail.com', 'sommakara84@gmail.com'
)
ORDER BY u.email, t.created_at
""",
    ),
    (
        "11. WALLET BALANCE + grant/debit summary — sommakara84 & the named accounts",
        """
SELECT u.email,
       ROUND(COALESCE(w.balance, 0) / 10000.0, 2) AS wallet_credits,
       ROUND(COALESCE(SUM(t.amount) FILTER (WHERE t.direction = 'credit'), 0) / 10000.0, 2) AS credited,
       ROUND(COALESCE(SUM(t.amount) FILTER (WHERE t.direction = 'debit'), 0) / 10000.0, 2) AS debited,
       ROUND(COALESCE(SUM(t.amount) FILTER (WHERE t.direction = 'refund'), 0) / 10000.0, 2) AS refunded
FROM users u
LEFT JOIN credit_wallets w ON w.user_id = u.id
LEFT JOIN credit_transactions t ON t.user_id = u.id
WHERE u.email IN (
    'pich.sou11@gmail.com', 'rinmakara2050@gmail.com', 'iamduke1987@gmail.com',
    'ponlorkleav168@gmail.com', 'khunmao.kh@gmail.com', 'vaththary@gmail.com',
    'hinseyha92@gmail.com', 'sommakara84@gmail.com'
)
GROUP BY u.email, w.balance
ORDER BY wallet_credits DESC
""",
    ),
]


def load_production() -> dict[str, str]:
    data: dict[str, str] = {}
    for line in (ROOT / ".deploy" / "secrets.production.env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        data[key.strip()] = value.strip()
    return data


def run_sql(client, sql: str) -> str:
    escaped = sql.replace("'", "'\\''")
    cmd = (
        "sudo -u postgres psql -d camxora_platform -v ON_ERROR_STOP=1 "
        f"-A -F, -P footer=off -c '{escaped}'"
    )
    _, stdout, stderr = client.exec_command(cmd, timeout=300)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    status = stdout.channel.recv_exit_status()
    if status != 0:
        return f"ERROR ({status}): {err.strip()[:2000]}"
    return out.rstrip("\n")


def main() -> int:
    if "--i-mean-production" not in sys.argv:
        print(__doc__)
        print("Refusing to run without --i-mean-production.")
        return 2

    secrets = load_production()
    host = secrets.get("PRODUCTION_VPS_HOST") or secrets["VPS_HOST"]
    user = secrets.get("PRODUCTION_VPS_USER") or secrets["VPS_USER"]
    password = secrets.get("PRODUCTION_VPS_PASSWORD") or secrets.get("VPS_PASSWORD")
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")

    print(f"=== CREDIT AUDIT — PRODUCTION {host} (read-only) ===\n")
    client = ssh_connect(host, user, ensure_deploy_key(), password)
    try:
        guard = (
            "if ! ip -4 addr | grep -q '82.197.71.248'; then "
            "echo 'Refusing: not the production host'; exit 1; fi; echo OK"
        )
        _, g_out, _ = client.exec_command(guard)
        if "OK" not in g_out.read().decode(errors="replace"):
            raise SystemExit("Host safety check failed.")

        for title, sql in QUERIES:
            print(f"----- {title} -----")
            print(run_sql(client, sql))
            print()
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
