"""Reset admin password to the known local-dev default."""

from __future__ import annotations

import asyncio
import os

import asyncpg
import bcrypt

ADMIN_EMAIL = "admin@mgfaceless.com"
ADMIN_PASSWORD = "112233aB!!@@"
DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/platform_db"


async def main() -> None:
    dsn = os.environ.get("PLATFORM_DATABASE_URL", DATABASE_URL)
    if dsn.startswith("postgresql+asyncpg://"):
        dsn = dsn.replace("postgresql+asyncpg://", "postgresql://", 1)

    conn = await asyncpg.connect(dsn)
    try:
        row = await conn.fetchrow(
            "SELECT id, email, role, status, password_hash, token_version "
            "FROM users WHERE email = $1",
            ADMIN_EMAIL,
        )
        if row is None:
            print("NOT_FOUND")
            return

        matched = bcrypt.checkpw(
            ADMIN_PASSWORD.encode("utf-8"),
            row["password_hash"].encode("utf-8"),
        )
        print(f"id={row['id']}")
        print(f"role={row['role']} status={row['status']} token_version={row['token_version']}")
        print(f"password_matched_before_reset={matched}")

        new_hash = bcrypt.hashpw(
            ADMIN_PASSWORD.encode("utf-8"),
            bcrypt.gensalt(rounds=12),
        ).decode("utf-8")
        await conn.execute(
            "UPDATE users SET password_hash = $1, updated_at = NOW() WHERE email = $2",
            new_hash,
            ADMIN_EMAIL,
        )
        print("password_reset_done=True")
    finally:
        await conn.close()

    # Clear Redis lockout / failure counters if Redis is up.
    try:
        from redis.asyncio import Redis

        redis = Redis.from_url("redis://localhost:6379/0", decode_responses=True)
        deleted = await redis.delete(
            f"auth:lockout:{ADMIN_EMAIL}",
            f"auth:failures:{ADMIN_EMAIL}",
        )
        await redis.aclose()
        print(f"redis_lockout_keys_cleared={deleted}")
    except Exception as exc:  # noqa: BLE001
        print(f"redis_clear_skipped={exc}")


if __name__ == "__main__":
    asyncio.run(main())
