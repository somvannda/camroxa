#!/usr/bin/env python3
"""One-off recovery: re-submit songs whose only stored Suno task is `failed`.

Why this exists
---------------
`platform_api/services/generation_service.py` dedupes submissions on
`(user_id, request_hash)` via `batch_repo.find_by_hash`, which does **not**
filter on status:

    SELECT ... FROM suno_tasks WHERE user_id = $1 AND request_hash = $2

So when the retry sweep (`retry_song_suno` -> `_submit_song_to_suno`) re-runs a
song whose stored task already `failed` with the same content hash, `submit()`
returns the *existing failed task* instead of creating a new one. The retry has
already charged 10 credits by then, so the user is charged for a generation that
never happens -- and no refund is issued, because `submit()` "succeeded".

This script works around that without a code deploy: it neutralises the stale
`request_hash` on the failed rows so the next retry misses the dedupe and
creates a fresh task, then enqueues `retry_song_suno` jobs.

Safety
------
* Dry-run by default; pass ``--apply`` to write.
* Refuses to enqueue a retry for a song that already has a live (non-failed)
  task with the same hash.
* Touches only `suno_tasks.request_hash` and `job_queue`. It never touches
  billing. Each real retry will charge the normal 10 credits for a generation
  it actually performs; spurious charges from earlier no-op retries must be
  refunded separately (see the accompanying issue).

Usage (on the host, with the platform venv):
    cd /opt/camxora/repo/platform_api && source .venv/bin/activate
    python ../scripts/deploy/resubmit_failed_suno_songs.py --email sophay@camxora.com
    python ../scripts/deploy/resubmit_failed_suno_songs.py --email sophay@camxora.com --apply
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

try:
    import asyncpg
except ImportError:  # pragma: no cover - operator guidance
    print("asyncpg is required: run this with the platform_api venv (source .venv/bin/activate).")
    raise SystemExit(2)

ENV_FILE = Path(os.environ.get("PLATFORM_ENV_FILE", "/opt/camxora/repo/platform_api/.env"))


def load_dsn() -> str:
    """Read PLATFORM_DATABASE_URL from the platform .env and make it asyncpg-safe."""
    if not ENV_FILE.is_file():
        raise SystemExit(f"env file not found: {ENV_FILE}")
    for raw in ENV_FILE.read_text(encoding="utf-8", errors="replace").splitlines():
        if raw.startswith("PLATFORM_DATABASE_URL="):
            url = raw.split("=", 1)[1].strip().strip('"').strip("'")
            return url.replace("postgresql+asyncpg://", "postgresql://")
    raise SystemExit("PLATFORM_DATABASE_URL not found in env file")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--email", required=True, help="owning user's email")
    p.add_argument("--apply", action="store_true", help="write changes (default: dry-run)")
    p.add_argument("--max", type=int, default=0, help="cap the number of songs processed (0 = all)")
    return p.parse_args()


async def run(args: argparse.Namespace) -> int:
    dsn = load_dsn()
    conn = await asyncpg.connect(dsn)
    try:
        user_id = await conn.fetchval(
            "SELECT id FROM users WHERE lower(email) = lower($1)", args.email
        )
        if user_id is None:
            print(f"user not found: {args.email}")
            return 1

        songs = await conn.fetch(
            """
            SELECT s.id, s.batch_id, s.batch_index, s.title, s.updated_at
            FROM songs s
            WHERE s.user_id = $1 AND s.status = 'suno_failed'
            ORDER BY s.updated_at DESC
            """,
            user_id,
        )
        if args.max:
            songs = songs[: args.max]

        mode = "APPLY" if args.apply else "DRY-RUN"
        print(f"[{mode}] user={args.email} ({user_id}) failed_songs={len(songs)}")

        queued = skipped = no_tasks = 0
        for song in songs:
            tasks = await conn.fetch(
                """
                SELECT id, request_hash, external_task_id, updated_at
                FROM suno_tasks
                WHERE song_id = $1 AND status = 'failed'
                """,
                song["id"],
            )
            if not tasks:
                no_tasks += 1
                print(f"  skip song {song['id']} (batch {song['batch_id']}): no failed task row")
                continue

            # Guard: never enqueue if a live task with the same hash already exists.
            live = False
            for task in tasks:
                live_count = await conn.fetchval(
                    """
                    SELECT count(*) FROM suno_tasks
                    WHERE user_id = $1 AND request_hash = $2 AND status <> 'failed'
                    """,
                    user_id,
                    task["request_hash"],
                )
                if live_count:
                    live = True
                    break
            if live:
                skipped += 1
                print(f"  skip song {song['id']} (batch {song['batch_id']}): a live task already exists")
                continue

            print(
                f"  queue song {song['id']} (batch {song['batch_id']}) "
                f"title={song['title']!r} failed_tasks={len(tasks)}"
            )

            if args.apply:
                async with conn.transaction():
                    for task in tasks:
                        # Neutralise the dedupe key so the retry creates a fresh task.
                        await conn.execute(
                            """
                            UPDATE suno_tasks
                            SET request_hash = request_hash || ':retry:' || substr(md5(random()::text), 1, 8),
                                updated_at = now()
                            WHERE id = $1
                            """,
                            task["id"],
                        )
                    await conn.execute(
                        """
                        INSERT INTO job_queue
                            (user_id, batch_id, song_id, job_type, status, priority, payload)
                        VALUES
                            ($1, $2, $3, 'retry_song_suno', 'queued', 20,
                             jsonb_build_object(
                                 'song_id', $3::text,
                                 'user_id', $1::text,
                                 'batch_id', $2::text,
                                 'title', NULL, 'album', NULL, 'lyrics', NULL))
                        """,
                        user_id,
                        song["batch_id"],
                        song["id"],
                    )
            queued += 1

        print(f"[{mode}] queued={queued} skipped_live={skipped} no_task_row={no_tasks}")
        if not args.apply:
            print("Dry-run only. Re-run with --apply to write.")
        return 0
    finally:
        await conn.close()


def main() -> int:
    args = parse_args()
    if sys.version_info < (3, 10):
        print("Python 3.10+ required")
        return 2
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
