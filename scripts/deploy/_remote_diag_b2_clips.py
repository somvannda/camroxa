#!/usr/bin/env python3
"""Compare web-music ok/alt B2 objects. Run on the API host only."""

from __future__ import annotations

import asyncio
import hashlib
import os
import sys

TASK = "a41873ce-3956-4377-9032-5ac0e5b88ca8"


async def main() -> int:
    sys.path.insert(0, "/opt/camxora/repo")
    import asyncpg
    from platform_api.services.storage_service import StorageService
    from platform_api.services.streaming_config_service import resolve_streaming_storage_config

    dsn = os.environ["PLATFORM_DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://", 1)
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=2)
    try:
        row = await pool.fetchrow(
            """
            SELECT b2_storage_key_ok, b2_storage_key_alt,
                   left(audio_url_ok, 40) AS ok_host,
                   left(audio_url_alt, 40) AS alt_host
            FROM suno_tasks WHERE id = $1::uuid
            """,
            TASK,
        )
        config = await resolve_streaming_storage_config(pool)
        print("cdn_base", bool(config.cdn_base_url), "bucket", config.bucket)
        storage = StorageService.from_config(config)
        client = storage._client()
        hashes: dict[str, str] = {}
        sizes: dict[str, int] = {}
        for label, key in (("ok", row["b2_storage_key_ok"]), ("alt", row["b2_storage_key_alt"])):
            short = str(key).rsplit("/", 1)[-1]
            head = client.head_object(Bucket=config.bucket, Key=str(key))
            got = client.get_object(Bucket=config.bucket, Key=str(key), Range="bytes=0-65535")
            data = got["Body"].read()
            digest = hashlib.md5(data).hexdigest()
            hashes[label] = digest
            sizes[label] = int(head["ContentLength"])
            print(
                label,
                "name",
                short,
                "bytes",
                sizes[label],
                "etag",
                str(head.get("ETag", "")).strip('"')[:20],
                "prefix_md5",
                digest,
            )
        print("size_equal", sizes.get("ok") == sizes.get("alt"))
        print("prefix_equal", hashes.get("ok") == hashes.get("alt"))
    finally:
        await pool.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
