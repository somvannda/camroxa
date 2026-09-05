"""Production retry-all failed-mp3 sweep starter. Runs on the VPS (camxora).

Detached via systemd-run so it survives the SSH session. Uses the SAME
StreamingUploadService path the API uses; progress + heartbeat are written to
system_settings (DB), so the admin page shows live progress from any worker.
Exits when the sweep finishes. Re-runnable; a click on the admin button while
this runs just reports "already running".
"""

from __future__ import annotations

import asyncio

import asyncpg

from platform_api.config import get_settings
from platform_api.repositories.streaming_repo import StreamingRepository
from platform_api.services.streaming_upload_service import StreamingUploadService


async def _main() -> None:
    settings = get_settings()
    dsn = settings.database_url
    if dsn.startswith("postgresql+asyncpg://"):
        dsn = dsn.replace("postgresql+asyncpg://", "postgresql://", 1)
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=4)

    svc = StreamingUploadService(pool)
    result = await svc.start_failed_mp3_retry_sweep()
    print("START_RESULT", result, flush=True)

    repo = StreamingRepository(pool)
    last_scan = -1
    while True:
        await asyncio.sleep(20)
        state = await repo.get_retry_sweep_state() or {}
        scanned = int(state.get("scanned") or 0)
        if scanned != last_scan:
            last_scan = scanned
            print(
                "PROGRESS scanned=%s total=%s ok=%s failed=%s running=%s"
                % (scanned, state.get("total"), state.get("succeeded"), state.get("still_failed"), state.get("running")),
                flush=True,
            )
        if not state.get("running"):
            print("SWEEP_FINISHED", state, flush=True)
            break
    await pool.close()


if __name__ == "__main__":
    asyncio.run(_main())
