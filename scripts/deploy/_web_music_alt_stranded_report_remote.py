#!/usr/bin/env python3
"""Read-only report: web_music tasks whose Version 2 (alt) is not playable.

Stranded by the old "first-clip success" bug, which marked the task SUCCESS with
audio_url_alt empty, so alt was never B2-ingested. This script only reports; it
makes no changes.
"""

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, "/opt/camxora/repo")

import asyncpg  # noqa: E402

# alt variant not playable: no packaged copy, no task-scoped B2 key.
ALT_NOT_PLAYABLE = """
  t.source = 'web_music'
  AND coalesce(t.package_status_alt, 'none') <> 'ready'
  AND t.packaged_storage_key_alt IS NULL
  AND (t.b2_storage_key_alt IS NULL
       OR position(t.id::text in coalesce(t.b2_storage_key_alt, '')) = 0)
"""

COUNTS = f"""
SELECT t.status,
       count(*) AS total,
       count(*) FILTER (WHERE btrim(coalesce(t.audio_url_alt, '')) <> '') AS with_alt_url,
       count(*) FILTER (WHERE btrim(coalesce(t.audio_url_alt, '')) = '') AS without_alt_url
FROM suno_tasks t
WHERE {ALT_NOT_PLAYABLE}
GROUP BY t.status
ORDER BY t.status
"""

SAMPLE = f"""
SELECT t.id, lower(u.email) AS email, left(coalesce(t.title, ''), 40) AS title,
       t.status,
       btrim(coalesce(t.audio_url_alt, '')) <> '' AS has_alt_url,
       t.external_task_id,
       t.created_at
FROM suno_tasks t
JOIN users u ON u.id = t.user_id
WHERE {ALT_NOT_PLAYABLE}
  AND t.status = 'success'
ORDER BY t.created_at DESC
LIMIT 25
"""


async def main() -> None:
    dsn = os.environ["PLATFORM_DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://", 1)
    pool = await asyncpg.create_pool(dsn)
    try:
        print("=== alt-not-playable counts by status ===", flush=True)
        for row in await pool.fetch(COUNTS):
            print(dict(row), flush=True)

        rows = await pool.fetch(SAMPLE)
        print(f"=== recent stranded success sample ({len(rows)}) ===", flush=True)
        for row in rows:
            print(
                row["created_at"].isoformat(),
                str(row["id"]),
                row["email"],
                "alt_url=" + ("yes" if row["has_alt_url"] else "no"),
                repr(row["title"]),
                flush=True,
            )
        print("REPORT_DONE", flush=True)
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
