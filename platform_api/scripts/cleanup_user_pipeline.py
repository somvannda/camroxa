"""Delete generation pipeline rows for one user (batches, songs, suno, images).

Keeps account, profiles, prompts, credits, and settings intact.

Usage:
  python platform_api/scripts/cleanup_user_pipeline.py ksomvannda@gmail.com
  python platform_api/scripts/cleanup_user_pipeline.py ksomvannda@gmail.com --apply
"""
from __future__ import annotations

import argparse
import asyncio
import sys

import asyncpg

DEFAULT_DB = "postgresql://postgres:postgres@localhost:5432/platform_db"


async def cleanup(email: str, *, apply: bool) -> None:
    conn = await asyncpg.connect(DEFAULT_DB)
    try:
        user = await conn.fetchrow(
            "SELECT id, email, display_name FROM users WHERE email = $1",
            email.strip().lower(),
        )
        if user is None:
            print(f"User not found: {email}")
            return

        user_id = user["id"]
        print(f"User: {user['display_name']} <{user['email']}> ({user_id})")

        preview = await conn.fetchrow(
            """
            SELECT
                (SELECT COUNT(*)::int FROM batches WHERE user_id = $1) AS batches,
                (SELECT COUNT(*)::int FROM songs WHERE user_id = $1) AS songs,
                (SELECT COUNT(*)::int FROM suno_tasks WHERE user_id = $1) AS suno_tasks,
                (SELECT COUNT(*)::int FROM image_jobs WHERE user_id = $1) AS image_jobs,
                (SELECT COUNT(*)::int FROM youtube_upload_jobs WHERE user_id = $1) AS youtube_upload_jobs
            """,
            user_id,
        )
        print("Will delete:", dict(preview))

        if not apply:
            print("\nDry run only. Re-run with --apply to delete.")
            return

        async with conn.transaction():
            for table, query in (
                ("youtube_upload_jobs", "DELETE FROM youtube_upload_jobs WHERE user_id = $1"),
                ("image_jobs", "DELETE FROM image_jobs WHERE user_id = $1"),
                ("suno_tasks", "DELETE FROM suno_tasks WHERE user_id = $1"),
                ("songs", "DELETE FROM songs WHERE user_id = $1"),
                ("batches", "DELETE FROM batches WHERE user_id = $1"),
            ):
                result = await conn.execute(query, user_id)
                print(f"{table}: {result}")

        after = await conn.fetchrow(
            """
            SELECT
                (SELECT COUNT(*)::int FROM batches WHERE user_id = $1) AS batches,
                (SELECT COUNT(*)::int FROM songs WHERE user_id = $1) AS songs
            """,
            user_id,
        )
        print("Remaining:", dict(after))
        print("Done.")
    finally:
        await conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Cleanup user generation pipeline data")
    parser.add_argument("email", help="User email")
    parser.add_argument("--apply", action="store_true", help="Actually delete rows")
    args = parser.parse_args()
    asyncio.run(cleanup(args.email, apply=args.apply))


if __name__ == "__main__":
    main()
