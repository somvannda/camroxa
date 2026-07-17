#!/usr/bin/env python3
"""Refresh and fulfill pending CutLuy credit-pack payments on sandbox."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from deploy import ensure_deploy_key, load_secrets, ssh_connect  # noqa: E402

EMAIL = "somvannda@gmail.com"


def main() -> int:
    remote_py = f"""
import asyncio, asyncpg, httpx, json, os
from datetime import datetime
from uuid import UUID, uuid4

EMAIL = {EMAIL!r}

def parse_cutluy_ts(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    raw = str(value).strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None

async def load_setting(conn, key):
    row = await conn.fetchrow("SELECT value FROM system_settings WHERE key = $1", key)
    if row is None or row["value"] is None:
        return None
    text = str(row["value"]).strip()
    return text or None

async def refresh_cutluy(conn, row):
    status = str(row["status"])
    if status in {{"paid", "expired", "failed"}} or str(row["provider"]) != "cutluy":
        return row
    api_key = await load_setting(conn, "billing.cutluy.secret_key")
    api_base = (await load_setting(conn, "billing.cutluy.api_base_url")) or "https://cutluy.com"
    api_base = api_base.rstrip("/")
    if not api_key:
        raise RuntimeError("CutLuy secret key missing in system_settings")
    url = f"{{api_base}}/v1/payments/{{row['external_payment_id']}}"
    async with httpx.AsyncClient(timeout=httpx.Timeout(20.0, connect=10.0)) as client:
        response = await client.get(url, headers={{"Authorization": f"Bearer {{api_key}}"}})
        response.raise_for_status()
        payload = response.json()
    updated = await conn.fetchrow(
        '''
        UPDATE billing_payments
        SET status = $2,
            approved_at = CASE
                WHEN $3::timestamptz IS NULL THEN approved_at
                ELSE $3::timestamptz
            END,
            raw_response = $4::jsonb,
            updated_at = NOW()
        WHERE id = $1
        RETURNING *
        ''',
        row["id"],
        payload.get("status", row["status"]),
        parse_cutluy_ts(payload.get("approved_at")),
        json.dumps(payload),
    )
    return updated or row

async def fulfill_credit_pack(conn, row):
    if row["fulfilled_at"] is not None or str(row["status"]) != "paid":
        return row
    metadata = row["metadata"] or {{}}
    if isinstance(metadata, str):
        metadata = json.loads(metadata)
    pack_id = str(metadata.get("pack_id") or "").strip()
    if not pack_id:
        raise RuntimeError("Missing pack_id in payment metadata")
    pack = await conn.fetchrow("SELECT * FROM credit_packs WHERE id = $1", UUID(pack_id))
    if pack is None or not pack.get("is_active", False):
        raise RuntimeError(f"Credit pack not found or inactive: {{pack_id}}")
    credits = int(pack["song_credits"] or 0)
    user_id = row["user_id"]
    payment_ref = str(row.get("external_payment_id") or row["id"])
    async with conn.transaction():
        locked = await conn.fetchrow(
            "SELECT * FROM billing_payments WHERE id = $1 AND user_id = $2 FOR UPDATE",
            row["id"],
            user_id,
        )
        if locked is None or locked["fulfilled_at"] is not None or str(locked["status"]) != "paid":
            return locked or row
        current = await conn.fetchval(
            "SELECT balance FROM credit_wallets WHERE user_id = $1 FOR UPDATE",
            user_id,
        )
        if current is None:
            current = 0
            await conn.execute(
                "INSERT INTO credit_wallets (user_id, balance, updated_at) VALUES ($1, 0, NOW())",
                user_id,
            )
        new_balance = int(current) + credits
        await conn.execute(
            "UPDATE credit_wallets SET balance = $2, updated_at = NOW() WHERE user_id = $1",
            user_id,
            new_balance,
        )
        await conn.execute(
            '''
            INSERT INTO credit_transactions
                (id, user_id, amount, direction, reason, ref_id, pack_id, payment_ref, created_at)
            VALUES ($1, $2, $3, 'credit', 'credit_pack_purchase', $4, $5, $6, NOW())
            ''',
            uuid4(),
            user_id,
            credits,
            pack_id,
            UUID(pack_id),
            payment_ref,
        )
        fulfilled = await conn.fetchrow(
            '''
            UPDATE billing_payments
            SET fulfilled_at = NOW(), updated_at = NOW()
            WHERE id = $1 AND fulfilled_at IS NULL
            RETURNING *
            ''',
            locked["id"],
        )
        print(" CREDITS_ADDED", credits, "NEW_BALANCE", new_balance)
        return fulfilled or locked

async def run():
    dsn = os.environ.get("PLATFORM_DATABASE_URL", "").replace("postgresql+asyncpg://", "postgresql://", 1).strip()
    if not dsn:
        print("PLATFORM_DATABASE_URL missing")
        return
    conn = await asyncpg.connect(dsn)
    try:
        user = await conn.fetchrow("SELECT id, email FROM users WHERE lower(email)=lower($1)", EMAIL)
        if not user:
            print("USER_NOT_FOUND")
            return
        rows = await conn.fetch(
            '''
            SELECT * FROM billing_payments
            WHERE user_id = $1
              AND metadata->>'product_type' = 'credit_pack'
            ORDER BY created_at DESC
            LIMIT 5
            ''',
            user["id"],
        )
        print("FOUND", len(rows), "credit_pack payments")
        for row in rows:
            print("PROCESS", row["id"], row["status"], row["external_payment_id"], row["fulfilled_at"])
            try:
                refreshed = await refresh_cutluy(conn, row)
                print(" REFRESHED_STATUS", refreshed["status"], refreshed.get("approved_at"))
            except Exception as exc:
                print(" REFRESH_ERROR", type(exc).__name__, str(exc)[:300])
                refreshed = row
            if str(refreshed["status"]) == "paid" and refreshed["fulfilled_at"] is None:
                try:
                    fulfilled = await fulfill_credit_pack(conn, refreshed)
                    print(" FULFILLED", fulfilled["fulfilled_at"] if fulfilled else None)
                except Exception as exc:
                    print(" FULFILL_ERROR", type(exc).__name__, str(exc)[:300])
            elif refreshed["fulfilled_at"]:
                print(" ALREADY_FULFILLED")
        wallet = await conn.fetchrow("SELECT balance FROM credit_wallets WHERE user_id=$1", user["id"])
        print("WALLET_BALANCE", wallet["balance"] if wallet else None)
    finally:
        await conn.close()

asyncio.run(run())
"""

    secrets = load_secrets()
    client = ssh_connect(secrets["VPS_HOST"], secrets["VPS_USER"], ensure_deploy_key(), None)
    sftp = client.open_sftp()
    with sftp.file("/tmp/fulfill_credit_pack.py", "w") as f:
        f.write(remote_py)
    sftp.close()

    cmd = (
        "sudo -u camxora bash -lc 'cd /opt/camxora/repo && set -a && source platform_api/.env && "
        "set +a && /opt/camxora/repo/platform_api/.venv/bin/python /tmp/fulfill_credit_pack.py'"
    )
    _, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    print(out)
    if err.strip():
        print("STDERR:", err)
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
