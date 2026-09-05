"""Read-only smoke of upload-job pagination SQL on the prod DB. Runs on the VPS."""
from __future__ import annotations

import asyncio

import asyncpg

from platform_api.config import get_settings
from platform_api.repositories.streaming_repo import StreamingRepository


async def _main() -> None:
    settings = get_settings()
    dsn = settings.database_url
    if dsn.startswith("postgresql+asyncpg://"):
        dsn = dsn.replace("postgresql+asyncpg://", "postgresql://", 1)
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=2)
    repo = StreamingRepository(pool)

    total_failed = await repo.count_upload_jobs(status="failed")
    total_alt = await repo.count_upload_jobs(status="failed", kind="mp3_alt")
    total_q = await repo.count_upload_jobs(status="failed", q="camxora")
    page1 = await repo.list_upload_jobs(limit=5, status="failed", offset=0)
    page2 = await repo.list_upload_jobs(limit=5, status="failed", offset=5)
    page1_ids = {str(r["id"]) for r in page1}
    page2_ids = {str(r["id"]) for r in page2}
    overlap = page1_ids & page2_ids
    print("SMOKE total_failed=%s total_alt=%s total_q=%s" % (total_failed, total_alt, total_q))
    print("SMOKE page1=%s page2=%s overlap=%s" % (len(page1), len(page2), len(overlap)))
    print("SMOKE newest_page1=%s" % (page1[0]["created_at"] if page1 else None))
    print("SMOKE newest_page2=%s" % (page2[0]["created_at"] if page2 else None))
    monotonic = True
    if page1 and page2:
        monotonic = page1[-1]["created_at"] >= page2[0]["created_at"]
    print("SMOKE monotonic=%s" % monotonic)
    await pool.close()
    print("SMOKE_OK")


if __name__ == "__main__":
    asyncio.run(_main())
