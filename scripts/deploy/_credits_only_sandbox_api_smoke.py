"""Sandbox HTTP smoke for credits-only v3 + v1 public filter. Run on the API host."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import asyncpg
import jwt

from platform_api.config import get_settings

BASE = os.environ.get("SMOKE_API_BASE", "https://api.sandbox.camxora.com")
FAILED: list[str] = []
PASSED = 0


def _req(method: str, path: str, *, token: str | None = None, body: dict | None = None) -> tuple[int, object]:
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(f"{BASE}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            if not raw:
                return resp.status, {}
            try:
                return resp.status, json.loads(raw)
            except json.JSONDecodeError:
                return resp.status, raw
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            parsed = raw
        return exc.code, parsed


def check(name: str, ok: bool, detail: str = "") -> None:
    global PASSED
    if ok:
        PASSED += 1
        print(f"PASS {name}")
        return
    FAILED.append(name)
    print(f"FAIL {name} {detail}")


async def mint_admin_token(pool: asyncpg.Pool) -> tuple[str, str]:
    row = await pool.fetchrow(
        """
        SELECT id, email, role, COALESCE(token_version, 0) AS token_version
        FROM users
        WHERE role = 'admin' AND status = 'active'
        ORDER BY created_at ASC
        LIMIT 1
        """
    )
    if row is None:
        raise SystemExit("No admin user on sandbox")
    settings = get_settings()
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
    return token, str(row["id"])


async def add_smoke_credits(pool: asyncpg.Pool, user_id: str, units: int) -> None:
    await pool.execute(
        """
        INSERT INTO credit_wallets (user_id, balance, updated_at)
        VALUES ($1::uuid, $2, NOW())
        ON CONFLICT (user_id) DO UPDATE
        SET balance = credit_wallets.balance + EXCLUDED.balance, updated_at = NOW()
        """,
        user_id,
        units,
    )


async def main() -> int:
    settings = get_settings()
    dsn = settings.database_url
    if dsn.startswith("postgresql+asyncpg://"):
        dsn = dsn.replace("postgresql+asyncpg://", "postgresql://", 1)
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=2)
    try:
        token, admin_id = await mint_admin_token(pool)

        status, docs = _req("GET", "/api/v3/docs")
        check(
            "GET /api/v3/docs",
            status == 200 and isinstance(docs, str) and "swagger" in docs.lower(),
        )

        status, openapi = _req("GET", "/api/v3/openapi.json")
        paths = openapi.get("paths", {}) if isinstance(openapi, dict) else {}
        check(
            "GET /api/v3/openapi.json v3-only",
            status == 200 and bool(paths) and all(str(path).startswith("/api/v3") for path in paths),
        )

        status, v3_public = _req("GET", "/api/v3/plans/public")
        v3_names = {row.get("name") for row in v3_public} if isinstance(v3_public, list) else set()
        check(
            "GET /api/v3/plans/public hides $79",
            status == 200
            and "Monthly · 2-channel" not in v3_names
            and "Free" in v3_names
            and any("starter" in str(name).lower() or name == "Starter" for name in v3_names),
            str(sorted(v3_names)),
        )
        if isinstance(v3_public, list):
            check(
                "v3 public rows are is_public",
                all(bool(row.get("is_public")) and bool(row.get("is_active")) for row in v3_public),
            )

        status, v1_public = _req("GET", "/api/v1/plans/public")
        v1_names = {row.get("name") for row in v1_public} if isinstance(v1_public, list) else set()
        v1_item = v1_public[0] if isinstance(v1_public, list) and v1_public else {}
        check(
            "GET /api/v1/plans/public hides hidden 2-channel",
            status == 200 and "Monthly · 2-channel" not in v1_names,
            str(sorted(v1_names)),
        )
        check(
            "v1 public shape has no music_credits",
            isinstance(v1_item, dict) and "monthly_song_limit" in v1_item and "music_credits" not in v1_item,
        )

        status, plans = _req("GET", "/api/v3/plans", token=token)
        check("GET /api/v3/plans admin", status == 200 and isinstance(plans, list) and len(plans) >= 3)
        hidden = next(
            (row for row in plans if row.get("name") == "Monthly · 2-channel"),
            None,
        ) if isinstance(plans, list) else None
        check(
            "hidden $79 grant fields",
            hidden is not None
            and hidden.get("is_public") is False
            and hidden.get("is_active") is True
            and int(hidden.get("price_cents") or 0) == 7900
            and int(hidden.get("monthly_credits") or 0) == 3000
            and hidden.get("music_credits") == 10,
            str(hidden),
        )

        if hidden:
            status, one = _req("GET", f"/api/v3/admin/plans/{hidden['id']}", token=token)
            check("GET /api/v3/admin/plans/{id}", status == 200 and one.get("id") == hidden["id"])
            status, patched = _req(
                "PATCH",
                f"/api/v3/admin/plans/{hidden['id']}",
                token=token,
                body={"music_credits": 10, "monthly_credits": 3000, "is_public": False},
            )
            check("PATCH /api/v3/admin/plans/{id}", status == 200 and patched.get("music_credits") == 10)

        status, pricing = _req("GET", "/api/v3/credits/pricing", token=token)
        check("GET /api/v3/credits/pricing", status == 200 and isinstance(pricing, list))

        status, me = _req("GET", "/api/v3/me/credits", token=token)
        check(
            "GET /api/v3/me/credits",
            status == 200 and isinstance(me, dict) and "balance_credits" in me,
            str(me),
        )

        status, other = _req("GET", f"/api/v3/users/{admin_id}/credits", token=token)
        check(
            "GET /api/v3/users/{id}/credits",
            status == 200 and isinstance(other, dict) and other.get("user_id") == admin_id,
            str(other),
        )

        status, quote = _req(
            "POST",
            "/api/v3/billing/quote",
            token=token,
            body={"op": "music", "plan_id": hidden["id"]} if hidden else {"op": "music"},
        )
        check(
            "POST /api/v3/billing/quote music=10",
            status == 200 and float((quote or {}).get("amount_credits") or 0) == 10,
            str(quote),
        )

        from platform_api.services.credit_units import credits_to_units

        ref = f"smoke-{uuid4()}"
        await add_smoke_credits(pool, admin_id, credits_to_units(20))
        status, charged = _req(
            "POST",
            "/api/v3/billing/charge",
            token=token,
            body={"op": "music", "plan_id": hidden["id"] if hidden else None, "ref_id": ref},
        )
        check(
            "POST /api/v3/billing/charge",
            status == 200 and charged.get("charged") is True,
            str(charged),
        )
        status, refunded = _req(
            "POST",
            "/api/v3/billing/refund",
            token=token,
            body={"op": "music", "amount_credits": 10, "ref_id": f"refund-{ref}"},
        )
        check(
            "POST /api/v3/billing/refund",
            status == 200 and float((refunded or {}).get("amount_credits") or 0) == 10,
            str(refunded),
        )

        status, dry = _req("POST", "/api/v3/admin/billing/conversion/dry-run", token=token, body={})
        check("POST /api/v3/admin/billing/conversion/dry-run", status == 200 and "rows" in (dry or {}))

        status, apply_denied = _req(
            "POST",
            "/api/v3/admin/billing/conversion/apply",
            token=token,
            body={"confirm": False},
        )
        check(
            "POST conversion/apply without confirm is rejected",
            status in {400, 422},
            str(apply_denied),
        )

        status, grant = _req(
            "POST",
            f"/api/v3/admin/billing/grant-period?user_id={admin_id}",
            token=token,
        )
        check("POST /api/v3/admin/billing/grant-period", status == 200 and "granted" in (grant or {}), str(grant))

        flag = await pool.fetchval(
            "SELECT value FROM system_settings WHERE key = 'credits_only_v3_charge'"
        )
        check("credits_only_v3_charge stays false", str(flag).lower() in {"false", "0", "none", ""})
    finally:
        await pool.close()

    print(f"SMOKE {PASSED} passed, {len(FAILED)} failed")
    if FAILED:
        print("FAILED:", ", ".join(FAILED))
        return 1
    print("CREDITS_ONLY_SANDBOX_API_SMOKE_OK")
    return 0


if __name__ == "__main__":
    import asyncio

    raise SystemExit(asyncio.run(main()))
