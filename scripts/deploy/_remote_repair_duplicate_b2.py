#!/usr/bin/env python3
"""Force re-upload web-music ok/alt MP3s when B2 objects are identical."""

from __future__ import annotations

import asyncio
import os
import sys
from uuid import UUID

TASK = os.environ.get("REPAIR_TASK_ID", "a41873ce-3956-4377-9032-5ac0e5b88ca8")


def _etag(client, bucket: str, key: str) -> tuple[int, str]:
    head = client.head_object(Bucket=bucket, Key=str(key))
    return int(head["ContentLength"]), str(head.get("ETag", "")).strip('"')


async def main() -> int:
    sys.path.insert(0, "/opt/camxora/repo")
    import asyncpg
    from platform_api.services.storage_service import StorageService
    from platform_api.services.streaming_config_service import resolve_streaming_storage_config
    from platform_api.services.streaming_upload_service import StreamingUploadService

    dsn = os.environ["PLATFORM_DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://", 1)
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=4)
    try:
        config = await resolve_streaming_storage_config(pool)
        storage = StorageService.from_config(config)
        client = storage._client()
        service = StreamingUploadService(pool)
        rows = await pool.fetch(
            """
            SELECT id, b2_storage_key_ok, b2_storage_key_alt
            FROM suno_tasks
            WHERE source = 'web_music'
              AND status = 'SUCCESS'
              AND COALESCE(b2_storage_key_ok, '') <> ''
              AND COALESCE(b2_storage_key_alt, '') <> ''
            ORDER BY updated_at DESC
            LIMIT 40
            """
        )
        targets: list[UUID] = [UUID(TASK)]
        for row in rows:
            try:
                size_ok, etag_ok = await asyncio.to_thread(
                    _etag, client, config.bucket, str(row["b2_storage_key_ok"])
                )
                size_alt, etag_alt = await asyncio.to_thread(
                    _etag, client, config.bucket, str(row["b2_storage_key_alt"])
                )
            except Exception as exc:
                print("head_failed", str(row["id"])[:8], type(exc).__name__)
                continue
            same = etag_ok == etag_alt and size_ok == size_alt
            print("scan", str(row["id"])[:8], "same" if same else "distinct", size_ok, size_alt)
            if same:
                targets.append(row["id"])
        unique_ids = list(dict.fromkeys(targets))
        print("repair_count", len(unique_ids))
        for task_id in unique_ids:
            print("repair", str(task_id))
            await service._run_web_music_b2_backfill(task_id, None, force=True)
        row = await pool.fetchrow(
            "SELECT b2_storage_key_ok, b2_storage_key_alt FROM suno_tasks WHERE id = $1::uuid",
            TASK,
        )
        if row is None:
            print("fire_task_missing")
            return 0
        size_ok, etag_ok = await asyncio.to_thread(
            _etag, client, config.bucket, str(row["b2_storage_key_ok"])
        )
        size_alt, etag_alt = await asyncio.to_thread(
            _etag, client, config.bucket, str(row["b2_storage_key_alt"])
        )
        print("fire_ok_bytes", size_ok, "etag", etag_ok[:16])
        print("fire_alt_bytes", size_alt, "etag", etag_alt[:16])
        print("fire_distinct", etag_ok != etag_alt)
        return 0 if etag_ok != etag_alt else 1
    finally:
        await pool.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
