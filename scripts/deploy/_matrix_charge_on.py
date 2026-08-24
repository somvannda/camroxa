"""Sandbox charge-on cases. Assumes credits_only_v3_charge already true."""
from __future__ import annotations
import asyncio
import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import asyncpg
import jwt

from platform_api.config import get_settings
from platform_api.services.credit_units import credits_to_units

BASE = os.environ.get("SMOKE_API_BASE", "https://api.sandbox.camxora.com")


def req(method, path, token=None, body=None):
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as resp:
            raw = resp.read().decode()
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            parsed = json.loads(raw) if raw else {}
        except Exception:
            parsed = raw
        return exc.code, parsed


async def main():
    settings = get_settings()
    dsn = settings.database_url
    if dsn.startswith("postgresql+asyncpg://"):
        dsn = dsn.replace("postgresql+asyncpg://", "postgresql://", 1)
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=2)
    try:
        flag = await pool.fetchval(
            "SELECT value FROM system_settings WHERE key = 'credits_only_v3_charge'"
        )
        print("FLAG_ON_NOW", flag)
        row = await pool.fetchrow(
            """
            SELECT id, email, role, COALESCE(token_version, 0) AS token_version
            FROM users WHERE role = 'admin' AND status = 'active'
            ORDER BY created_at ASC LIMIT 1
            """
        )
        now = datetime.now(timezone.utc)
        token = jwt.encode(
            {
                "user_id": str(row["id"]),
                "email": row["email"],
                "role": "admin",
                "token_version": int(row["token_version"] or 0),
                "exp": now + timedelta(minutes=20),
                "iat": now,
                "type": "access",
            },
            settings.jwt_secret,
            algorithm=settings.jwt_algorithm,
        )
        status, quote = req("POST", "/api/v3/billing/quote", token, {"op": "music"})
        print("QUOTE", status, quote)
        await pool.execute(
            """
            INSERT INTO credit_wallets (user_id, balance, updated_at)
            VALUES ($1::uuid, $2, NOW())
            ON CONFLICT (user_id) DO UPDATE
            SET balance = credit_wallets.balance + EXCLUDED.balance, updated_at = NOW()
            """,
            str(row["id"]),
            credits_to_units(20),
        )
        ref = f"matrix-{uuid4()}"
        status, charged = req("POST", "/api/v3/billing/charge", token, {"op": "music", "ref_id": ref})
        print("CHARGE", status, charged)
        status, refunded = req(
            "POST",
            "/api/v3/billing/refund",
            token,
            {"op": "music", "amount_credits": 10, "ref_id": f"refund-{ref}"},
        )
        print("REFUND", status, refunded)
        status, wallet = req("GET", "/api/v3/me/credits", token)
        keys = {}
        if isinstance(wallet, dict):
            for k in ("balance_credits", "balance", "user_id"):
                if k in wallet:
                    keys[k] = wallet[k]
        print("WALLET", status, keys)
        zero = await pool.fetchrow(
            """
            SELECT u.id, u.email, COALESCE(u.token_version, 0) AS token_version
            FROM users u
            LEFT JOIN credit_wallets w ON w.user_id = u.id
            WHERE u.status = 'active' AND COALESCE(w.balance, 0) = 0 AND u.role <> 'admin'
            LIMIT 1
            """
        )
        if zero:
            ztok = jwt.encode(
                {
                    "user_id": str(zero["id"]),
                    "email": zero["email"],
                    "role": "user",
                    "token_version": int(zero["token_version"] or 0),
                    "exp": now + timedelta(minutes=20),
                    "iat": now,
                    "type": "access",
                },
                settings.jwt_secret,
                algorithm=settings.jwt_algorithm,
            )
            st, body = req("POST", "/api/v3/billing/charge", ztok, {"op": "music", "ref_id": f"zero-{uuid4()}"})
            print("ZERO_CHARGE", st, body)
        else:
            print("ZERO_CHARGE SKIP no zero-balance user")
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
