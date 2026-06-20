"""Seed an admin user into the platform database.

Usage:
    python -m platform_api.scripts.seed_admin

Requires: bcrypt, asyncpg (already installed as platform_api dependencies).
"""

import asyncio
import sys
from uuid import uuid4

import asyncpg
import bcrypt


ADMIN_EMAIL = "admin@mgfaceless.com"
ADMIN_PASSWORD = "112233aB!!@@"
ADMIN_DISPLAY_NAME = "Admin"
ADMIN_ROLE = "admin"
ADMIN_STATUS = "active"

# Database connection — matches the platform_api default config.
# Override with PLATFORM_DATABASE_URL env var if different.
DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/platform_db"


def hash_password(password: str) -> str:
    """Hash a password using bcrypt with work factor 12 (same as AuthService)."""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


async def main() -> None:
    import os

    dsn = os.environ.get("PLATFORM_DATABASE_URL", DATABASE_URL)
    # Strip asyncpg driver prefix if present
    if dsn.startswith("postgresql+asyncpg://"):
        dsn = dsn.replace("postgresql+asyncpg://", "postgresql://", 1)

    conn = await asyncpg.connect(dsn)
    try:
        # Check if admin already exists
        existing = await conn.fetchval(
            "SELECT id FROM users WHERE email = $1",
            ADMIN_EMAIL,
        )
        if existing:
            print(f"Admin user '{ADMIN_EMAIL}' already exists (id: {existing}). Skipping.")
            return

        # Insert admin user
        user_id = uuid4()
        password_hash = hash_password(ADMIN_PASSWORD)

        async with conn.transaction():
            await conn.execute(
                """
                INSERT INTO users (id, email, password_hash, display_name, role, status, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, NOW(), NOW())
                """,
                user_id,
                ADMIN_EMAIL,
                password_hash,
                ADMIN_DISPLAY_NAME,
                ADMIN_ROLE,
                ADMIN_STATUS,
            )
            # Initialize credit wallet
            await conn.execute(
                """
                INSERT INTO credit_wallets (user_id, balance, updated_at)
                VALUES ($1, 0, NOW())
                """,
                user_id,
            )

        print(f"Admin user created successfully!")
        print(f"  Email: {ADMIN_EMAIL}")
        print(f"  ID:    {user_id}")
        print(f"  Role:  {ADMIN_ROLE}")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
