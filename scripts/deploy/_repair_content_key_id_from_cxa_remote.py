#!/usr/bin/env python3
"""Point suno_tasks content_key_id at the key embedded in the CXA1 header."""

from __future__ import annotations

import asyncio
import os
import sys
from uuid import UUID

sys.path.insert(0, "/opt/camxora/repo")

import asyncpg

from platform_api.services.audio_packager import parse_package_header
from platform_api.services.storage_service import StorageService
from platform_api.services.streaming_config_service import resolve_streaming_storage_config


async def main() -> None:
    email = (sys.argv[1] if len(sys.argv) > 1 else "").strip().lower()
    dsn = os.environ["PLATFORM_DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://", 1)
    pool = await asyncpg.create_pool(dsn)
    try:
        config = await resolve_streaming_storage_config(pool)
        storage = StorageService.from_config(config)
        if email:
            rows = await pool.fetch(
                """
                SELECT t.id, lower(u.email) AS email, left(coalesce(t.title,''),32) AS title,
                       t.content_key_id_ok, t.content_key_id_alt,
                       t.packaged_storage_key_ok, t.packaged_storage_key_alt
                FROM suno_tasks t
                JOIN users u ON u.id = t.user_id
                WHERE t.source = 'web_music'
                  AND lower(u.email) = $1
                  AND (t.packaged_storage_key_ok IS NOT NULL OR t.packaged_storage_key_alt IS NOT NULL)
                """,
                email,
            )
        else:
            rows = await pool.fetch(
                """
                SELECT t.id, lower(u.email) AS email, left(coalesce(t.title,''),32) AS title,
                       t.content_key_id_ok, t.content_key_id_alt,
                       t.packaged_storage_key_ok, t.packaged_storage_key_alt
                FROM suno_tasks t
                JOIN users u ON u.id = t.user_id
                WHERE t.source = 'web_music'
                  AND t.status = 'success'
                  AND (t.packaged_storage_key_ok IS NOT NULL OR t.packaged_storage_key_alt IS NOT NULL)
                  AND (
                    (SELECT count(*) FROM content_keys ck
                     WHERE ck.subject_type='suno_task' AND ck.subject_id=t.id) > 2
                  )
                """
            )
        print("candidates", len(rows), flush=True)
        fixed = 0
        for row in rows:
            for variant, pkg_col, key_col in (
                ("ok", "packaged_storage_key_ok", "content_key_id_ok"),
                ("alt", "packaged_storage_key_alt", "content_key_id_alt"),
            ):
                pkg_key = row[pkg_col]
                db_key = row[key_col]
                if not pkg_key:
                    continue
                try:
                    blob = bytes(await storage.download_bytes(key=pkg_key) or b"")
                    header, _ = parse_package_header(blob)
                    header_id = UUID(header.key_id)
                except Exception as exc:
                    print("skip", row["email"], row["id"], variant, type(exc).__name__, exc, flush=True)
                    continue
                if db_key == header_id:
                    continue
                exists = await pool.fetchval(
                    "SELECT 1 FROM content_keys WHERE id = $1 AND status = 'active'",
                    header_id,
                )
                if not exists:
                    print("missing_header_key", row["email"], row["id"], variant, header_id, flush=True)
                    continue
                await pool.execute(
                    f"UPDATE suno_tasks SET {key_col} = $2, updated_at = NOW() WHERE id = $1",
                    row["id"],
                    header_id,
                )
                fixed += 1
                print(
                    "fixed",
                    row["email"],
                    row["title"],
                    variant,
                    str(db_key),
                    "->",
                    str(header_id),
                    flush=True,
                )
        print("KEY_REPAIR_SUMMARY", {"fixed": fixed, "candidates": len(rows)}, flush=True)
        print("KEY_REPAIR_DONE", flush=True)
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
