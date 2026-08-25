#!/usr/bin/env python3
"""Backfill stuck web_music SUCCESS clips that never reached B2."""

from __future__ import annotations

import asyncio
import os
import sys
from uuid import UUID

sys.path.insert(0, "/opt/camxora/repo")

import asyncpg

from platform_api.services.streaming_upload_service import StreamingUploadService

STUCK_SQL = """
SELECT t.id,
       lower(u.email) AS email,
       left(coalesce(t.title, ''), 40) AS title
FROM suno_tasks t
JOIN users u ON u.id = t.user_id
WHERE t.source = 'web_music'
  AND t.status = 'success'
  AND (
    (
      coalesce(t.package_status_ok, 'none') <> 'ready'
      AND t.packaged_storage_key_ok IS NULL
      AND (t.b2_storage_key_ok IS NULL OR position(t.id::text in coalesce(t.b2_storage_key_ok, '')) = 0)
      AND coalesce(btrim(t.audio_url_ok), '') <> ''
    )
    OR
    (
      coalesce(t.package_status_alt, 'none') <> 'ready'
      AND t.packaged_storage_key_alt IS NULL
      AND (t.b2_storage_key_alt IS NULL OR position(t.id::text in coalesce(t.b2_storage_key_alt, '')) = 0)
      AND coalesce(btrim(t.audio_url_alt), '') <> ''
    )
  )
"""


async def main() -> None:
    email = (sys.argv[1] if len(sys.argv) > 1 else "").strip().lower()
    if email in {"", "all", "--all"}:
        email = ""
    dsn = os.environ["PLATFORM_DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://", 1)
    pool = await asyncpg.create_pool(dsn)
    svc = StreamingUploadService(pool)
    try:
        if email:
            rows = await pool.fetch(STUCK_SQL + " AND lower(u.email) = $1 ORDER BY t.created_at DESC", email)
        else:
            rows = await pool.fetch(STUCK_SQL + " ORDER BY u.email, t.created_at DESC")
        print("stuck_count", len(rows), flush=True)
        ok = 0
        failed = 0
        for index, row in enumerate(rows, start=1):
            task_id = row["id"] if isinstance(row["id"], UUID) else UUID(str(row["id"]))
            print(
                f"backfill {index}/{len(rows)} {row['email']} {task_id} {row['title']!r}",
                flush=True,
            )
            try:
                await svc._run_web_music_b2_backfill(task_id, None)
            except Exception as exc:
                failed += 1
                print("error", task_id, type(exc).__name__, exc, flush=True)
                continue
            after = await pool.fetchrow(
                """
                SELECT coalesce(package_status_ok, 'none') AS pkg_ok,
                       coalesce(package_status_alt, 'none') AS pkg_alt,
                       (b2_storage_key_ok IS NOT NULL) AS b2_ok,
                       (b2_storage_key_alt IS NOT NULL) AS b2_alt
                FROM suno_tasks WHERE id = $1
                """,
                task_id,
            )
            ready = str(after["pkg_ok"]) == "ready" or bool(after["b2_ok"])
            if ready:
                ok += 1
            else:
                failed += 1
            print("after", dict(after), flush=True)
        print("BACKFILL_SUMMARY", {"ready": ok, "not_ready": failed, "total": len(rows)}, flush=True)
        print("BACKFILL_DONE", flush=True)
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
