"""Create the platform_db database and run the initial schema migration, then seed admin user.

Usage:
    python platform_api/scripts/setup_db.py
"""

import asyncio
from uuid import uuid4

import asyncpg
import bcrypt


POSTGRES_DSN = "postgresql://postgres:postgres@localhost:5432/postgres"
PLATFORM_DSN = "postgresql://postgres:postgres@localhost:5432/platform_db"

ADMIN_EMAIL = "admin@mgfaceless.com"
ADMIN_PASSWORD = "112233aB!!@@"
ADMIN_DISPLAY_NAME = "Admin"


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


async def create_database():
    conn = await asyncpg.connect(POSTGRES_DSN)
    try:
        exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = 'platform_db'"
        )
        if not exists:
            await conn.execute("CREATE DATABASE platform_db")
            print("[DB] Created database 'platform_db'")
        else:
            print("[DB] Database 'platform_db' already exists")
    finally:
        await conn.close()


async def create_tables():
    conn = await asyncpg.connect(PLATFORM_DSN)
    try:
        # Check if users table exists
        exists = await conn.fetchval(
            "SELECT 1 FROM information_schema.tables WHERE table_name = 'users'"
        )
        if exists:
            print("[DB] Tables already exist, skipping schema creation")
            return

        # Create users table
        await conn.execute("""
            CREATE TABLE users (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                email VARCHAR(255) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                display_name VARCHAR(50) NOT NULL,
                role VARCHAR(20) NOT NULL DEFAULT 'user',
                status VARCHAR(20) NOT NULL DEFAULT 'active',
                suspension_reason TEXT,
                deleted_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)

        # Create refresh_tokens table
        await conn.execute("""
            CREATE TABLE refresh_tokens (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID NOT NULL REFERENCES users(id),
                token_hash VARCHAR(64) NOT NULL UNIQUE,
                expires_at TIMESTAMPTZ NOT NULL,
                revoked_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)

        # Create credit_wallets table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS credit_wallets (
                user_id UUID PRIMARY KEY REFERENCES users(id),
                balance INTEGER NOT NULL DEFAULT 0,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)

        print("[DB] Created tables: users, refresh_tokens, credit_wallets")
    finally:
        await conn.close()


async def seed_admin():
    conn = await asyncpg.connect(PLATFORM_DSN)
    try:
        existing = await conn.fetchval(
            "SELECT id FROM users WHERE email = $1", ADMIN_EMAIL
        )
        if existing:
            print(f"[SEED] Admin '{ADMIN_EMAIL}' already exists (id: {existing})")
            return

        user_id = uuid4()
        pw_hash = hash_password(ADMIN_PASSWORD)

        async with conn.transaction():
            await conn.execute(
                """
                INSERT INTO users (id, email, password_hash, display_name, role, status, created_at, updated_at)
                VALUES ($1, $2, $3, $4, 'admin', 'active', NOW(), NOW())
                """,
                user_id,
                ADMIN_EMAIL,
                pw_hash,
                ADMIN_DISPLAY_NAME,
            )
            await conn.execute(
                """
                INSERT INTO credit_wallets (user_id, balance, updated_at)
                VALUES ($1, 0, NOW())
                """,
                user_id,
            )

        print(f"[SEED] Admin user created!")
        print(f"       Email: {ADMIN_EMAIL}")
        print(f"       ID:    {user_id}")
    finally:
        await conn.close()


async def main():
    await create_database()
    await create_tables()
    await seed_admin()
    print("\nDone! You can now start the platform API and log in.")


if __name__ == "__main__":
    asyncio.run(main())
