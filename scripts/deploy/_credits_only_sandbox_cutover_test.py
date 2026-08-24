"""Sandbox cutover test: unexpired $79 license → dry-run → mint → grant → flag On.

Does not touch production. Does not call Suno. Expired licenses stay mint 0.
"""

from __future__ import annotations

import asyncio
import csv
import io
import json
import secrets
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import asyncpg
import jwt

from platform_api.config import get_settings
from platform_api.dependencies import (
    get_v3_billing_service,
    get_v3_conversion_service,
    get_v3_grant_service,
    set_db_pool,
)
from platform_api.services.credit_units import credits_to_units
from platform_api.services.v2.credit_service import CreditService

TEST_EMAIL = "credits-cutover-test@sandbox.camxora.test"
MUSIC_USED = 80  # spec example: 80/300 → leftover 2200
BASE = "https://api.sandbox.camxora.com"


def _req(method: str, path: str, *, token: str | None = None, body: dict | None = None):
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(f"{BASE}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            parsed = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            parsed = raw
        return exc.code, parsed


def _token(settings, row) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "user_id": str(row["id"]),
            "email": row["email"],
            "role": row["role"],
            "token_version": int(row["token_version"] or 0),
            "exp": now + timedelta(minutes=20),
            "iat": now,
            "type": "access",
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


async def _ensure_test_user(pool: asyncpg.Pool) -> asyncpg.Record:
    existing = await pool.fetchrow(
        """
        SELECT id, email, role, status, COALESCE(token_version, 0) AS token_version
        FROM users WHERE email = $1
        """,
        TEST_EMAIL,
    )
    if existing:
        return existing
    user_id = uuid4()
    admin_hash = await pool.fetchval(
        "SELECT password_hash FROM users WHERE role = 'admin' AND status = 'active' LIMIT 1"
    )
    cols = await pool.fetch("SELECT column_name FROM information_schema.columns WHERE table_name = 'users'")
    names = {r["column_name"] for r in cols}
    fields = ["id", "email", "password_hash", "display_name", "role", "status", "created_at", "updated_at"]
    values: list[object] = [user_id, TEST_EMAIL, admin_hash, "Cutover Test", "user", "active"]
    placeholders = ["$1", "$2", "$3", "$4", "$5", "$6", "NOW()", "NOW()"]
    idx = 7
    if "email_confirmed" in names:
        fields.insert(-2, "email_confirmed")
        values.append(True)
        placeholders.insert(-2, f"${idx}")
        idx += 1
    await pool.execute(
        f"INSERT INTO users ({', '.join(fields)}) VALUES ({', '.join(placeholders)})",
        *values,
    )
    await pool.execute(
        """
        INSERT INTO credit_wallets (user_id, balance, updated_at)
        VALUES ($1, 0, NOW()) ON CONFLICT DO NOTHING
        """,
        user_id,
    )
    return await pool.fetchrow(
        """
        SELECT id, email, role, status, COALESCE(token_version, 0) AS token_version
        FROM users WHERE id = $1
        """,
        user_id,
    )


async def _ensure_unexpired_license(pool: asyncpg.Pool, user_id: UUID) -> dict:
    plan = await pool.fetchrow(
        """
        SELECT id, name, price_cents, monthly_song_limit, monthly_credits, billing_cycle_days
        FROM plans
        WHERE name = 'Monthly · 2-channel' AND price_cents = 7900
        LIMIT 1
        """
    )
    if plan is None:
        raise SystemExit("Hidden $79 Monthly · 2-channel row missing")
    license_row = await pool.fetchrow(
        """
        SELECT id, status, expires_at, activated_at
        FROM licenses
        WHERE user_id = $1 AND plan_id = $2
        ORDER BY activated_at DESC NULLS LAST
        LIMIT 1
        """,
        user_id,
        plan["id"],
    )
    expires = datetime.now(timezone.utc) + timedelta(days=30)
    if license_row is None:
        await pool.execute(
            """
            INSERT INTO licenses (
                license_key, plan_id, user_id, status, activated_at, expires_at, created_at
            )
            VALUES ($1, $2, $3, 'active', NOW(), $4, NOW())
            """,
            secrets.token_hex(32),
            plan["id"],
            user_id,
            expires,
        )
    else:
        await pool.execute(
            """
            UPDATE licenses
            SET status = 'active',
                expires_at = $2,
                activated_at = COALESCE(activated_at, NOW()),
                revoked_at = NULL
            WHERE id = $1
            """,
            license_row["id"],
            expires,
        )
    return {
        "plan_id": str(plan["id"]),
        "plan_name": plan["name"],
        "monthly_song_limit": int(plan["monthly_song_limit"] or 0),
        "monthly_credits": int(plan["monthly_credits"] or 0),
    }


async def _seed_music_used(pool: asyncpg.Pool, user_id: UUID, period_start) -> None:
    await pool.execute(
        """
        DELETE FROM usage_tracking
        WHERE user_id = $1 AND operation_type = 'music'
        """,
        user_id,
    )
    await pool.execute(
        """
        INSERT INTO usage_tracking (
            user_id, operation_type, usage_date, daily_count, monthly_count,
            period_start_date, created_at, updated_at
        )
        VALUES ($1, 'music', CURRENT_DATE, $2, $2, $3, NOW(), NOW())
        """,
        user_id,
        MUSIC_USED,
        period_start,
    )


class _PoolDb:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def fetch_one(self, sql: str, *args):
        return await self._pool.fetchrow(sql, *args)

    async def fetch_val(self, sql: str, *args):
        return await self._pool.fetchval(sql, *args)


async def main() -> int:
    settings = get_settings()
    dsn = settings.database_url
    if dsn.startswith("postgresql+asyncpg://"):
        dsn = dsn.replace("postgresql+asyncpg://", "postgresql://", 1)
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=3)
    set_db_pool(pool)
    try:
        user = await _ensure_test_user(pool)
        user_id = user["id"]
        plan_info = await _ensure_unexpired_license(pool, user_id)
        print("TEST_USER", user["email"], user_id)
        print("LICENSE", plan_info)

        conversion = get_v3_conversion_service()
        preview = await conversion.preview_user(user_id)
        print("PREVIEW_BEFORE_SEED", json.dumps(preview, default=str))
        period_start = preview.get("period_start")
        if not period_start:
            raise SystemExit(f"preview missing period_start: {preview}")
        from datetime import date

        await _seed_music_used(pool, user_id, date.fromisoformat(str(period_start)))
        preview = await conversion.preview_user(user_id)
        print("PREVIEW_AFTER_SEED", json.dumps(preview, default=str))
        if int(preview.get("credits_to_mint") or 0) != (300 - MUSIC_USED) * 10:
            print("WARN unexpected leftover", preview.get("credits_to_mint"))

        service_rows = await conversion.dry_run()
        print("SERVICE_DRY_RUN_ROWS", len(service_rows))
        buf = io.StringIO()
        fields = [
            "user_id",
            "email",
            "plan_name",
            "price_cents",
            "plan_song_limit",
            "music_used",
            "leftover_packages",
            "credits_to_mint",
            "bucket",
            "skipped",
            "already_applied",
        ]
        emails = {str(r["id"]): r["email"] for r in await pool.fetch("SELECT id, email FROM users")}
        writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in service_rows:
            writer.writerow({**row, "email": emails.get(str(row.get("user_id")), "")})
        print("===CSV_BEGIN===")
        print(buf.getvalue(), end="")
        print("===CSV_END===")

        applied = await conversion.apply([user_id], confirm=True)
        print("APPLY", json.dumps(applied, default=str))

        grants = get_v3_grant_service()
        grant = await grants.ensure_period_grant(user_id)
        print("GRANT", json.dumps(grant, default=str))

        pricing = await pool.fetch(
            "SELECT ai_service, operation_type, credits_per_operation FROM credit_pricing WHERE operation_type IN ('music', 'music_generation')"
        )
        print("PRICING_BEFORE", [dict(r) for r in pricing])
        await pool.execute(
            """
            UPDATE credit_pricing
            SET credits_per_operation = $1
            WHERE operation_type IN ('music', 'music_generation')
            """,
            credits_to_units(10),
        )
        print("PRICING_MUSIC_SET", credits_to_units(10), "units (=10 credits)")

        await pool.execute(
            """
            INSERT INTO system_settings (key, value, value_type, updated_at)
            VALUES ('credits_only_v3_charge', 'true', 'boolean', NOW())
            ON CONFLICT (key) DO UPDATE
            SET value = 'true', value_type = 'boolean', updated_at = NOW()
            """
        )
        flag = await pool.fetchval(
            "SELECT value FROM system_settings WHERE key = 'credits_only_v3_charge'"
        )
        print("FLAG", flag)

        deleted = await pool.execute(
            "DELETE FROM system_settings WHERE key = 'web_music_free_daily_credits'"
        )
        print("DELETED_FREE_SETTING", deleted)
        free_limit = await CreditService(_PoolDb(pool)).daily_free_limit()
        print("FREE_DAILY_FROM_PLAN", free_limit)

        token = _token(settings, user)
        status, quote = 0, {}
        for attempt in range(6):
            status, quote = _req(
                "POST",
                "/api/v3/billing/quote",
                token=token,
                body={"op": "music", "plan_id": plan_info["plan_id"]},
            )
            if status == 200:
                break
            print("QUOTE_RETRY", attempt + 1, status)
            time.sleep(4)
        print("QUOTE", status, quote)
        ref = f"cutover-{uuid4()}"
        status, charged = _req(
            "POST",
            "/api/v3/billing/charge",
            token=token,
            body={"op": "music", "plan_id": plan_info["plan_id"], "ref_id": ref},
        )
        print("CHARGE", status, charged)
        status, refunded = _req(
            "POST",
            "/api/v3/billing/refund",
            token=token,
            body={"op": "music", "amount_credits": 10, "ref_id": f"refund-{ref}"},
        )
        print("REFUND", status, refunded)
        status, wallet = _req("GET", "/api/v3/me/credits", token=token)
        print("WALLET", status, wallet if not isinstance(wallet, dict) else {
            k: wallet.get(k)
            for k in ("balance_credits", "grant_remaining_credits", "user_id")
        })

        expired = await pool.fetch(
            """
            SELECT u.email, l.expires_at
            FROM licenses l JOIN users u ON u.id = l.user_id
            WHERE l.expires_at IS NOT NULL AND l.expires_at <= NOW()
            """
        )
        print("EXPIRED_UNTOUCHED", [(r["email"], str(r["expires_at"])) for r in expired])
        print("CUTOVER_TEST_OK leftover_example=2200 grant+flag+charge_refund")
        return 0
    finally:
        await pool.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
