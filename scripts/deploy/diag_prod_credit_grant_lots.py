#!/usr/bin/env python3
"""Read-only look at one account's credit grant lots / grants (prod).

Usage (from the repo root, on the operator machine):

    python scripts/deploy/diag_prod_credit_grant_lots.py tepchanpanharith@gmail.com

Explains a ``credit_invariants`` "multiple live grant lots" alert: dumps the
user's wallet, every ``credit_wallet_lots`` row, their active licence / web
subscription, and recent ``v3_period_grant`` ledger rows. **Writes nothing.**
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

REMOTE = r'''
cd /opt/camxora/repo
PYTHONPATH=/opt/camxora/repo/ /opt/camxora/repo/platform_api/.venv/bin/python - <<'PY'
import asyncio, json
import asyncpg
from platform_api.config import get_settings

EMAIL = __EMAIL__

LOTS_SQL = """
SELECT lot.tag, lot.amount_units, lot.remaining_units,
       lot.expires_at, lot.period_start, lot.created_at
FROM credit_wallet_lots lot
JOIN users u ON u.id = lot.user_id
WHERE lower(u.email) = lower($1)
ORDER BY lot.created_at
"""

TX_SQL = """
SELECT ct.created_at, ct.direction, ct.reason, ct.amount, ct.ref_id, ct.metadata
FROM credit_transactions ct
JOIN users u ON u.id = ct.user_id
WHERE lower(u.email) = lower($1)
  AND ct.reason IN ('v3_period_grant', 'v3_daily_grant',
                    'v3_period_grant_clawback', 'v3_grant_expire',
                    'v3_paid_web_reconcile')
ORDER BY ct.created_at DESC
LIMIT 60
"""

WALLET_SQL = """
SELECT u.id::text AS user_id, u.email, u.created_at,
       w.balance,
       (SELECT count(*) FROM licenses l WHERE l.user_id = u.id
          AND l.status = 'active' AND (l.expires_at IS NULL OR l.expires_at > NOW())) AS active_licenses,
       (SELECT count(*) FROM web_subscriptions ws WHERE ws.user_id = u.id
          AND ws.status = 'active' AND ws.current_period_end > NOW()) AS active_web_subs
FROM users u
LEFT JOIN credit_wallets w ON w.user_id = u.id
WHERE lower(u.email) = lower($1)
"""


def cr(units):
    return None if units is None else round(int(units) / 10000.0, 4)


async def main():
    settings = get_settings()
    dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=2)
    try:
        w = await pool.fetchrow(WALLET_SQL, EMAIL)
        if w is None:
            print(f"USER_NOT_FOUND {EMAIL}")
            return
        print("=== USER ===")
        print(f"email={w['email']} id={w['user_id']} created={w['created_at']}")
        print(f"wallet_credits={cr(w['balance'])} active_licenses={w['active_licenses']} "
              f"active_web_subs={w['active_web_subs']}")

        if w["active_licenses"]:
            lic = await pool.fetch(
                "SELECT plan_id, status, activated_at, expires_at FROM licenses "
                "WHERE user_id = $1::uuid ORDER BY activated_at DESC LIMIT 5", w["user_id"])
            print("--- licenses ---")
            for r in lic:
                print(dict(r))

        if w["active_web_subs"]:
            subs = await pool.fetch(
                "SELECT plan_id, plan_type, status, monthly_credits_granted, "
                "current_period_start, current_period_end FROM web_subscriptions "
                "WHERE user_id = $1::uuid ORDER BY current_period_start DESC LIMIT 5", w["user_id"])
            print("--- web_subscriptions ---")
            for r in subs:
                print(dict(r))

        print("=== credit_wallet_lots (all) ===")
        lots = await pool.fetch(LOTS_SQL, EMAIL)
        for r in lots:
            print(
                f"tag={r['tag']:>15} amount={cr(r['amount_units'])} "
                f"remaining={cr(r['remaining_units'])} "
                f"period_start={r['period_start']} expires_at={r['expires_at']} "
                f"created_at={r['created_at']}"
            )
        live_grants = [r for r in lots if r["tag"] == "grant" and int(r["remaining_units"]) > 0]
        print(f"LIVE_GRANT_LOTS={len(live_grants)} "
              f"sum_remaining={sum(cr(r['remaining_units']) for r in live_grants)}")
        for r in live_grants:
            print(f"  live grant: period_start={r['period_start']} "
                  f"remaining={cr(r['remaining_units'])} expires_at={r['expires_at']}")

        print("=== recent grant-related credit_transactions ===")
        txs = await pool.fetch(TX_SQL, EMAIL)
        for r in txs:
            meta = r["metadata"]
            try:
                meta = json.loads(meta) if isinstance(meta, str) else meta
            except Exception:
                pass
            print(
                f"{r['created_at']} {r['direction']:>6} {r['reason']:<26} "
                f"amount={cr(r['amount'])} ref_id={r['ref_id']} meta={meta}"
            )
        print("DIAG_DONE")
    finally:
        await pool.close()


asyncio.run(main())
PY
'''


def load_env(name: str) -> dict[str, str]:
    data: dict[str, str] = {}
    for line in (ROOT / ".deploy" / name).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        data[key.strip()] = value.strip()
    return data


def main() -> int:
    email = sys.argv[1] if len(sys.argv) > 1 else "tepchanpanharith@gmail.com"
    command = REMOTE.replace("__EMAIL__", repr(email))

    secrets = load_env("secrets.production.env")
    host = secrets.get("PRODUCTION_VPS_HOST") or secrets["VPS_HOST"]
    if host != PRODUCTION_HOST:
        raise SystemExit(f"Refusing non-production host: {host}")
    client = ssh_connect(
        host,
        secrets.get("PRODUCTION_VPS_USER") or secrets["VPS_USER"],
        ensure_deploy_key(),
        secrets.get("PRODUCTION_VPS_PASSWORD") or secrets.get("VPS_PASSWORD"),
    )
    try:
        _, stdout, stderr = client.exec_command(command, get_pty=True, timeout=120)
        print(stdout.read().decode(errors="replace").encode("ascii", "replace").decode("ascii"))
        err = stderr.read().decode(errors="replace")
        if err.strip():
            print("STDERR:", err.encode("ascii", "replace").decode("ascii"), file=sys.stderr)
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
