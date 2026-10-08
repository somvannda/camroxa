#!/usr/bin/env python3
"""Recover web_music Version 2 (alt) variants stranded by the first-clip bug.

The old poll marked the task SUCCESS with audio_url_alt empty, so alt was never
B2-ingested and Version 2 stayed on "Waiting" forever. This refreshes each
stranded task from upstream record-info and, with --apply, persists the alt URL
and runs the B2 backfill (which is what makes Version 2 playable).

Default is a dry-run probe: it only reports whether alt is still recoverable.
Pass --apply to make changes. Pass --limit N to cap the number of tasks.
"""

from __future__ import annotations

import asyncio
import os
import sys
from uuid import UUID

sys.path.insert(0, "/opt/camxora/repo")

import asyncpg  # noqa: E402

from platform_api.services.streaming_upload_service import StreamingUploadService  # noqa: E402
from platform_api.services.suno_audio_resolver import (  # noqa: E402
    poll_suno_generate_with_pool,
    refresh_suno_task_download_urls,
)

# success task whose alt variant is not playable (no package, no task-scoped B2 key)
STRANDED_SQL = """
SELECT t.id, lower(u.email) AS email, left(coalesce(t.title, ''), 40) AS title,
       t.external_task_id
FROM suno_tasks t
JOIN users u ON u.id = t.user_id
WHERE t.source = 'web_music'
  AND t.status = 'success'
  AND coalesce(t.package_status_alt, 'none') <> 'ready'
  AND t.packaged_storage_key_alt IS NULL
  AND (t.b2_storage_key_alt IS NULL
       OR position(t.id::text in coalesce(t.b2_storage_key_alt, '')) = 0)
ORDER BY t.created_at DESC
"""


def _flag(name: str) -> bool:
    return name in sys.argv


def _limit() -> int | None:
    if "--limit" in sys.argv:
        try:
            return int(sys.argv[sys.argv.index("--limit") + 1])
        except (IndexError, ValueError):
            return None
    return None


async def main() -> None:
    apply = _flag("--apply")
    limit = _limit()
    dsn = os.environ["PLATFORM_DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://", 1)
    pool = await asyncpg.create_pool(dsn)
    svc = StreamingUploadService(pool)
    try:
        rows = await pool.fetch(STRANDED_SQL)
        if limit is not None:
            rows = rows[:limit]
        print(f"stranded_alt_total={len(rows)} apply={apply}", flush=True)

        recoverable = 0
        unrecoverable = 0
        recovered = 0
        failed = 0

        for index, row in enumerate(rows, start=1):
            task_id = row["id"] if isinstance(row["id"], UUID) else UUID(str(row["id"]))
            external = str(row["external_task_id"] or "").strip()
            if not external:
                unrecoverable += 1
                print(f"[{index}] no_external_task_id {task_id} {row['email']}", flush=True)
                continue

            refreshed = await refresh_suno_task_download_urls(
                external,
                poll_status=lambda task_id: poll_suno_generate_with_pool(pool, task_id),
            )
            if not refreshed.audio_url_alt:
                unrecoverable += 1
                print(
                    f"[{index}] unrecoverable {task_id} {row['email']} {row['title']!r}",
                    flush=True,
                )
                continue

            recoverable += 1
            if not apply:
                print(
                    f"[{index}] recoverable {task_id} {row['email']} {row['title']!r}",
                    flush=True,
                )
                continue

            try:
                await svc._persist_refreshed_audio_urls(
                    suno_task_id=task_id,
                    refreshed=refreshed,
                )
                await svc._run_web_music_b2_backfill(task_id, "alt")
                after = await pool.fetchrow(
                    """
                    SELECT coalesce(package_status_alt, 'none') AS pkg_alt,
                           (b2_storage_key_alt IS NOT NULL) AS b2_alt
                    FROM suno_tasks WHERE id = $1
                    """,
                    task_id,
                )
                ok = str(after["pkg_alt"]) == "ready" or bool(after["b2_alt"])
                if ok:
                    recovered += 1
                    print(f"[{index}] recovered {task_id} {row['email']}", flush=True)
                else:
                    failed += 1
                    print(f"[{index}] not_ready_after {task_id} {dict(after)}", flush=True)
            except Exception as exc:
                failed += 1
                print(f"[{index}] error {task_id} {type(exc).__name__} {exc}", flush=True)

        print(
            "SUMMARY",
            {
                "total": len(rows),
                "recoverable": recoverable,
                "unrecoverable": unrecoverable,
                "recovered": recovered,
                "failed": failed,
                "apply": apply,
            },
            flush=True,
        )
        print("ALT_RECOVER_DONE", flush=True)
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
