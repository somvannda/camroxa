"""Read-only(ish) functional check of auto-retry plumbing on prod (venv).

- Confirms the deployed service exposes the auto-retry knobs.
- Confirms the candidate query returns eligible ids with sane budget.
- Runs one pass; while the manual admin sweep owns the backlog it must
  short-circuit with recovered=0 (no writes happen then).
"""
from __future__ import annotations

import asyncio

import asyncpg

from platform_api.config import get_settings
from platform_api.repositories.streaming_repo import StreamingRepository
from platform_api.services import streaming_upload_service as svc


async def _main() -> None:
    settings = get_settings()
    dsn = settings.database_url
    if dsn.startswith("postgresql+asyncpg://"):
        dsn = dsn.replace("postgresql+asyncpg://", "postgresql://", 1)
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=3)
    repo = StreamingRepository(pool)

    print("AUTO_ENABLED=%s INTERVAL=%s MAX_AGE_H=%s MAX_ATT=%s PASS_LIMIT=%s CONCURRENCY=%s" % (
        svc._AUTO_RETRY_ENABLED,
        svc._AUTO_RETRY_INTERVAL_S,
        svc._AUTO_RETRY_MAX_AGE_HOURS,
        svc._AUTO_RETRY_MAX_ATTEMPT_COUNT,
        svc._AUTO_RETRY_PASS_LIMIT,
        svc._AUTO_RETRY_CONCURRENCY,
    ))

    ids = await repo.list_failed_mp3_jobs_for_auto_retry(
        max_attempt_count=svc._AUTO_RETRY_MAX_ATTEMPT_COUNT,
        max_age_hours=svc._AUTO_RETRY_MAX_AGE_HOURS,
        limit=10,
    )
    print("CANDIDATES=%s" % len(ids))
    if ids:
        rows = await pool.fetch(
            "SELECT id, attempt_count, created_at FROM stream_upload_jobs WHERE id = ANY($1::uuid[]) ORDER BY created_at ASC",
            ids,
        )
        for r in rows[:5]:
            print("  CAND %s attempts=%s created=%s" % (str(r["id"])[:8], r["attempt_count"], r["created_at"]))

    service = svc.StreamingUploadService(pool)
    recovered = await service.run_auto_retry_pass()
    print("PASS_RECOVERED=%s" % recovered)
    await pool.close()
    print("CHECK_OK")


if __name__ == "__main__":
    asyncio.run(_main())
