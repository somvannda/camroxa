"""Sandbox-only: prove Free users cannot hit /generation/suno."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

import asyncpg
import jwt

from platform_api.config import get_settings

BASE = "https://api.sandbox.camxora.com"


def _req(method: str, path: str, *, token: str, body: dict | None = None):
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
        "X-Camxora-Client": "desktop",
    }
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


async def main() -> int:
    settings = get_settings()
    dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=2)
    try:
        free = await pool.fetchrow(
            """
            SELECT u.id, u.email, u.role, COALESCE(u.token_version, 0) AS token_version
            FROM users u
            WHERE u.status = 'active'
              AND COALESCE(u.email_confirmed, true) = true
              AND NOT EXISTS (
                SELECT 1 FROM licenses l
                JOIN plans p ON p.id = l.plan_id
                WHERE l.user_id = u.id
                  AND l.status = 'active'
                  AND (l.expires_at IS NULL OR l.expires_at > NOW())
                  AND COALESCE(p.price_cents, 0) > 0
            )
            AND NOT EXISTS (
                SELECT 1 FROM web_subscriptions ws
                JOIN plans p ON p.id = ws.plan_id
                WHERE ws.user_id = u.id
                  AND ws.status = 'active'
                  AND ws.current_period_end > NOW()
                  AND COALESCE(p.price_cents, 0) > 0
            )
            ORDER BY u.created_at DESC
            LIMIT 1
            """
        )
        if free is None:
            raise SystemExit("no free user found for desktop gate probe")

        def token(row) -> str:
            now = datetime.now(timezone.utc)
            return jwt.encode(
                {
                    "user_id": str(row["id"]),
                    "email": row["email"],
                    "role": row["role"],
                    "token_version": int(row["token_version"] or 0),
                    "exp": now + timedelta(minutes=10),
                    "iat": now,
                    "type": "access",
                },
                settings.jwt_secret,
                algorithm=settings.jwt_algorithm,
            )

        body = {
            "model": "V5",
            "title": "Gate Probe",
            "lyrics": "[Verse]\nprobe",
            "style": "folk",
        }
        free_status, free_body = _req("POST", "/api/v1/generation/suno", token=token(free), body=body)
        print("FREE", free["email"], free_status, free_body)
        if free_status != 403:
            raise SystemExit(f"expected 403 for free user, got {free_status}")
        code = (free_body or {}).get("error", {}).get("code")
        if code != "DESKTOP_PLAN_REQUIRED":
            raise SystemExit(f"expected DESKTOP_PLAN_REQUIRED, got {code}")
        print("DESKTOP_GATE_PROBE_OK")
        return 0
    finally:
        await pool.close()


if __name__ == "__main__":
    import asyncio

    raise SystemExit(asyncio.run(main()))
