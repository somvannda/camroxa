"""Seed a Studio account into whichever platform DB the running API uses.

Local development only. Usage:
    python scripts/seed_sandbox_user.py [email] [password]

Reads PLATFORM_DATABASE_URL (async URL accepted) or defaults to the sandbox DB the
`postforme-publishing` API worktree uses.
"""

from __future__ import annotations

import asyncio
import os
import sys
from uuid import uuid4

import asyncpg
import bcrypt

DEFAULT_DB = "postgresql://postgres:postgres@localhost:5432/camxora_pfm_sandbox"


async def main() -> int:
    email = sys.argv[1] if len(sys.argv) > 1 else "somvannda@gmail.com"
    password = sys.argv[2] if len(sys.argv) > 2 else "StudioLocal!2026"

    url = os.environ.get("PLATFORM_DATABASE_URL", DEFAULT_DB).replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(url)
    try:
        cols = {
            r["column_name"]
            for r in await conn.fetch(
                "select column_name from information_schema.columns where table_name='users'"
            )
        }
        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()

        existing = await conn.fetchrow("select id from users where lower(email)=lower($1)", email)
        if existing:
            await conn.execute(
                "update users set password_hash=$1, email_confirmed=true, status='active', updated_at=now() where id=$2",
                hashed,
                existing["id"],
            )
            print(f"updated password for {email}")
            return 0

        payload = {
            "id": uuid4(),
            "email": email,
            "password_hash": hashed,
            "display_name": "Somvannda",
            "email_confirmed": True,
            "role": "user",
            "status": "active",
            "products": ["music_web", "studio"],
        }
        keys = [k for k in payload if k in cols]
        placeholders = ", ".join(f"${i + 1}" for i in range(len(keys)))
        await conn.execute(
            f"insert into users ({', '.join(keys)}) values ({placeholders})",
            *[payload[k] for k in keys],
        )
        print(f"created {email} in {url.rsplit('/', 1)[-1]} (password: {password})")
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
