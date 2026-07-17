#!/usr/bin/env python3
"""Diagnose credit pack payment fulfillment on sandbox."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_secrets, ssh_connect  # noqa: E402

EMAIL = "somvannda@gmail.com"


def main() -> int:
    secrets = load_secrets()
    client = ssh_connect(secrets["VPS_HOST"], secrets["VPS_USER"], ensure_deploy_key(), None)

    remote_py = f"""
import asyncio, asyncpg, json, os

EMAIL = {EMAIL!r}

async def main():
    dsn=os.environ["PLATFORM_DATABASE_URL"].replace("postgresql+asyncpg://","postgresql://",1)
    conn=await asyncpg.connect(dsn)
    user=await conn.fetchrow("SELECT id, email FROM users WHERE lower(email)=lower($1)", EMAIL)
    if not user:
        print("USER_NOT_FOUND", EMAIL)
        await conn.close()
        return
    uid=user["id"]
    print("USER", user["email"], str(uid))

    wallet=await conn.fetchrow("SELECT balance FROM credit_wallets WHERE user_id=$1", uid)
    print("WALLET_BALANCE", wallet["balance"] if wallet else None)

    packs=await conn.fetch("SELECT id, name, song_credits, price_cents, is_active FROM credit_packs ORDER BY song_credits")
    print("CREDIT_PACKS", len(packs))
    for p in packs:
        print(" pack", p["id"], p["name"], "credits=", p["song_credits"], "price=", p["price_cents"], "active=", p["is_active"])

    sql = (
        "SELECT id, status, amount_cents, provider, external_payment_id, "
        "fulfilled_at, approved_at, created_at, updated_at, metadata, checkout_url "
        "FROM billing_payments WHERE user_id = $1 ORDER BY created_at DESC LIMIT 15"
    )
    payments=await conn.fetch(sql, uid)
    print("PAYMENTS", len(payments))
    for p in payments:
        meta=p["metadata"]
        if isinstance(meta, str):
            meta=json.loads(meta)
        print("---")
        print("id", p["id"])
        print("status", p["status"], "fulfilled_at", p["fulfilled_at"])
        print("amount_cents", p["amount_cents"], "provider", p["provider"])
        print("external", p["external_payment_id"])
        print("product_type", (meta or {{}}).get("product_type"))
        print("pack_id", (meta or {{}}).get("pack_id"))
        print("created", p["created_at"], "approved", p["approved_at"])

    tx_sql = (
        "SELECT id, amount, direction, reason, ref_id, metadata, created_at "
        "FROM credit_transactions WHERE user_id = $1 ORDER BY created_at DESC LIMIT 15"
    )
    txs=await conn.fetch(tx_sql, uid)
    print("CREDIT_TX", len(txs))
    for t in txs:
        print("---")
        print(t["created_at"], t["direction"], t["amount"], t["reason"], t["ref_id"])

    await conn.close()

asyncio.run(main())
"""

    sftp = client.open_sftp()
    with sftp.file("/tmp/diag_credit_pack.py", "w") as f:
        f.write(remote_py)
    sftp.close()

    cmd = (
        "sudo -u camxora bash -lc 'set -a && source /opt/camxora/repo/platform_api/.env && "
        "set +a && /opt/camxora/repo/platform_api/.venv/bin/python /tmp/diag_credit_pack.py' && "
        "echo '=== recent billing journal ===' && "
        "journalctl -u camxora-api -n 250 --no-pager | grep -iE 'credit|cutluy|webhook|fulfill|purchase_pack|billing' | tail -50"
    )
    _, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
    if err.strip():
        sys.stdout.buffer.write(b"\nSTDERR:\n")
        sys.stdout.buffer.write(err.encode("utf-8", errors="replace"))
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
