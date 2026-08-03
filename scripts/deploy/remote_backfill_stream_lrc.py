#!/usr/bin/env python3
"""Backfill karaoke LRC onto stream_tracks missing timestamps (run on API host)."""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path


def _load_env() -> str:
    dsn = ""
    for path in (
        Path("/opt/camxora/repo/platform_api/.env"),
        Path("/opt/camxora/repo/.env"),
    ):
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip("\"'")
            os.environ.setdefault(key, value)
            if key in {"DATABASE_URL", "PLATFORM_DATABASE_URL"} and not dsn:
                dsn = value
    if not dsn:
        raise SystemExit("no database url")
    if dsn.startswith("postgresql+asyncpg://"):
        dsn = "postgresql://" + dsn.split("://", 1)[1]
    return dsn


async def main() -> None:
    import asyncpg
    from platform_api.services.suno_audio_resolver import fetch_timestamped_lrc_with_pool
    from platform_api.services.suno_lrc import looks_like_lrc

    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    dsn = _load_env()
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=2)
    rows = await pool.fetch(
        """
        SELECT st.id, st.title, st.suno_audio_id, t.external_task_id
        FROM stream_tracks st
        JOIN suno_tasks t ON t.id = st.suno_task_id
        WHERE st.suno_audio_id IS NOT NULL AND st.suno_audio_id <> ''
          AND t.external_task_id IS NOT NULL AND t.external_task_id <> ''
          AND NOT (coalesce(st.lyrics, '') ~ '\\[[0-9]{1,2}:[0-9]{2}')
        ORDER BY st.created_at DESC
        LIMIT $1
        """,
        limit,
    )
    print(f"CANDIDATES {len(rows)}")
    ok = 0
    fail = 0
    for row in rows:
        lrc = await fetch_timestamped_lrc_with_pool(
            pool,
            external_task_id=str(row["external_task_id"]),
            audio_id=str(row["suno_audio_id"]),
            attempts=3,
            delay_seconds=1.5,
        )
        if not looks_like_lrc(lrc):
            fail += 1
            print(f"FAIL {row['id']} {row['title'][:40]}")
            continue
        await pool.execute(
            """
            UPDATE stream_tracks
            SET lyrics = $2, updated_at = NOW()
            WHERE id = $1
            """,
            row["id"],
            lrc,
        )
        ok += 1
        print(f"OK {row['id']} {row['title'][:40]} lrc_len={len(lrc)}")
    print(f"DONE ok={ok} fail={fail}")
    await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
