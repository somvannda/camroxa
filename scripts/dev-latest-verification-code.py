"""Local development helper: print the latest unused email verification code.

Usage (from the repo root):
  python scripts/dev-latest-verification-code.py user@example.com
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncpg  # noqa: E402

from platform_api.config import get_settings  # noqa: E402


async def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python scripts/dev-latest-verification-code.py <email>")
        return 2

    email = sys.argv[1].strip()
    settings = get_settings()
    dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(dsn)
    try:
        row = await conn.fetchrow(
            """
            SELECT ev.code, ev.purpose, ev.expires_at, ev.used
            FROM email_verifications ev
            JOIN users u ON u.id = ev.user_id
            WHERE lower(u.email) = lower($1)
              AND ev.purpose IN ('register', 'password_reset')
            ORDER BY ev.created_at DESC
            LIMIT 1
            """,
            email,
        )
        if row is None:
            print(f"No verification code found for {email}")
            return 1
        print(f"email: {email}")
        print(f"purpose: {row['purpose']}")
        print(f"code: {row['code']}")
        print(f"expires_at: {row['expires_at']}")
        print(f"used: {row['used']}")
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
