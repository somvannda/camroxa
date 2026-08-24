"""Sandbox-only: two real POST /generation/suno calls for the cutover test user.

Refuses production. Spends provider credits. Does not refund.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from uuid import UUID

import asyncpg
import jwt

from platform_api.config import get_settings
from platform_api.dependencies import set_db_pool
from platform_api.services.credit_units import units_to_credits

TEST_EMAIL = "credits-cutover-test@sandbox.camxora.test"
BASE = "https://api.sandbox.camxora.com"
PROD_IP = "82.197.71.248"

JOBS = (
    {
        "title": "Harbor Morning Light",
        "style": "calm acoustic folk, soft guitar, warm vocals",
        "lyrics": (
            "[Verse]\n"
            "Morning light on quiet water\n"
            "I walk the wooden pier alone\n"
            "A harbor breeze is getting softer\n"
            "and every wave feels like home\n"
            "\n"
            "[Chorus]\n"
            "Hold this morning, let it stay\n"
            "Gold on water, far away\n"
            "I will keep this simple day\n"
        ),
    },
    {
        "title": "Quiet River Road",
        "style": "gentle folk pop, acoustic guitar, soft piano",
        "lyrics": (
            "[Verse]\n"
            "Down a quiet river road\n"
            "the trees are leaning into spring\n"
            "I hum a tune I used to know\n"
            "and let the open morning sing\n"
            "\n"
            "[Chorus]\n"
            "Take the long way, take it slow\n"
            "Let the river teach me how to go\n"
        ),
    },
)


def _req(method: str, path: str, *, token: str | None = None, body: dict | None = None, timeout: int = 60):
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(f"{BASE}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
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
            "exp": now + timedelta(minutes=30),
            "iat": now,
            "type": "access",
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


async def _wallet_credits(pool: asyncpg.Pool, user_id: UUID) -> float:
    units = await pool.fetchval(
        "SELECT COALESCE(balance, 0) FROM credit_wallets WHERE user_id = $1",
        user_id,
    )
    return units_to_credits(int(units or 0))


async def _ensure_profile(pool: asyncpg.Pool, user_id: UUID) -> UUID:
    existing = await pool.fetchval(
        "SELECT id FROM channel_profiles WHERE user_id = $1 ORDER BY created_at ASC LIMIT 1",
        user_id,
    )
    if existing is not None:
        return existing
    return await pool.fetchval(
        """
        INSERT INTO channel_profiles (user_id, name, image_config, youtube_config)
        VALUES ($1, 'Cutover Primary', '{}'::jsonb, '{}'::jsonb)
        RETURNING id
        """,
        user_id,
    )


async def _poll_task(token: str, task_id: str, *, attempts: int = 24, delay_sec: float = 8.0) -> dict:
    last: dict = {}
    for attempt in range(1, attempts + 1):
        status, body = _req("GET", f"/api/v1/generation/suno/{task_id}", token=token)
        last = {"http": status, "body": body, "attempt": attempt}
        task_status = str((body or {}).get("status") or "").upper()
        print(f"  poll {attempt}/{attempts} http={status} status={task_status}")
        if task_status in {"SUCCESS", "FAILED", "ERROR"}:
            return last
        time.sleep(delay_sec)
    return last


async def main() -> int:
    settings = get_settings()
    dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=3)
    set_db_pool(pool)
    try:
        user = await pool.fetchrow(
            """
            SELECT id, email, role, status, COALESCE(token_version, 0) AS token_version
            FROM users WHERE email = $1
            """,
            TEST_EMAIL,
        )
        if user is None:
            raise SystemExit(f"Test user missing: {TEST_EMAIL}")
        user_id = user["id"]
        profile_id = await _ensure_profile(pool, user_id)
        token = _token(settings, user)
        before = await _wallet_credits(pool, user_id)
        print(f"USER {user['email']} {user_id}")
        print(f"PROFILE {profile_id}")
        print(f"WALLET_BEFORE {before}")

        results = []
        for index, job in enumerate(JOBS, start=1):
            payload = {
                "model": "V5",
                "title": job["title"],
                "lyrics": job["lyrics"],
                "style": job["style"],
                "instrumental": False,
                "channel_profile_id": str(profile_id),
            }
            print(f"=== SUNO {index} submit {job['title']} ===")
            http_status, body = _req("POST", "/api/v1/generation/suno", token=token, body=payload, timeout=90)
            print(f"  submit http={http_status} body={body}")
            task_id = str((body or {}).get("task_id") or "")
            mid_wallet = await _wallet_credits(pool, user_id)
            print(f"  WALLET_AFTER_SUBMIT {mid_wallet} delta={mid_wallet - before if index == 1 else 'n/a'}")
            poll = {}
            if task_id:
                poll = await _poll_task(token, task_id)
            results.append(
                {
                    "index": index,
                    "title": job["title"],
                    "submit_http": http_status,
                    "task_id": task_id,
                    "wallet_after_submit": mid_wallet,
                    "poll": poll,
                }
            )

        after = await _wallet_credits(pool, user_id)
        charges = await pool.fetch(
            """
            SELECT created_at, direction, amount, reason, ref_id
            FROM credit_transactions
            WHERE user_id = $1
            ORDER BY created_at DESC
            LIMIT 8
            """,
            user_id,
        )
        print(f"WALLET_AFTER {after}")
        print(f"WALLET_DELTA {after - before}")
        for row in charges:
            print(f"LEDGER {dict(row)}")
        print("===SUNO_GENERATE_JSON===")
        print(
            json.dumps(
                {
                    "email": TEST_EMAIL,
                    "user_id": str(user_id),
                    "wallet_before": before,
                    "wallet_after": after,
                    "wallet_delta": after - before,
                    "results": results,
                },
                default=str,
            )
        )
        print("===SUNO_GENERATE_DONE===")
        return 0
    finally:
        await pool.close()


if __name__ == "__main__":
    import asyncio

    raise SystemExit(asyncio.run(main()))
