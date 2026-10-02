"""Reproduce the admin retry-all status handler on prod venv (root, env)."""
from __future__ import annotations

import asyncio

import asyncpg

from platform_api.config import get_settings
from platform_api.services.streaming_upload_service import StreamingUploadService


async def _main() -> None:
    settings = get_settings()
    dsn = settings.database_url
    if dsn.startswith("postgresql+asyncpg://"):
        dsn = dsn.replace("postgresql+asyncpg://", "postgresql://", 1)
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=3)
    svc = StreamingUploadService(pool)
    try:
        result = await svc.failed_mp3_retry_sweep_status()
        print("STATUS_OK", result)
    except Exception as exc:
        import traceback

        print("STATUS_RAISED")
        traceback.print_exc()
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(_main())
