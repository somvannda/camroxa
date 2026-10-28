"""Encrypt ingested MP3s at rest and produce chunked A/B packages."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from platform_api.services.audio_packager import (
    GCM_MIME,
    ab_plaintext_variant,
    decrypt_original,
    encrypt_original,
    looks_like_camxora_audio,
    new_content_key,
    package_chunks,
    unwrap_content_key,
    wrap_content_key,
)
from platform_api.services.content_license_service import resolve_audio_kek
from platform_api.services.hls_packager import HlsPackagerError, package_hls_aes128

logger = logging.getLogger(__name__)


class AudioPackageService:
    def __init__(self, pool: Any) -> None:
        self._pool = pool

    async def package_plaintext(
        self,
        plaintext: bytes,
        *,
        subject_type: str,
        subject_id: UUID,
        variant: str,
        base_key: str,
        storage: Any,
        null_suno_urls: bool = True,
        source_key: str | None = None,
    ) -> dict[str, Any]:
        if not plaintext:
            raise ValueError("empty audio")
        if looks_like_camxora_audio(plaintext):
            logger.info("Skip packaging already-encrypted object subject=%s", subject_id)
            return {"status": "ready", "skipped": True}

        async with self._pool.acquire() as conn:
            # Session-scoped advisory lock, deliberately NOT transaction-scoped.
            # The packaging body performs several minutes of object-storage
            # uploads. Wrapping that in one transaction meant the rows stayed
            # locked until COMMIT, so a track never became visible as 'ready'
            # until every upload had finished, and the lock_timeout could cancel
            # the statement mid-upload and roll the whole thing back (seen on
            # production as "canceling statement due to lock timeout" followed
            # by a retry, leaving a track unplayable for ~4 minutes).
            #
            # With no enclosing transaction every statement autocommits, so the
            # ready columns written after lane A are visible immediately while
            # lane B and HLS continue. The lock is released in `finally` - a
            # leaked session lock previously blocked every packager.
            acquired = await conn.fetchval(
                "SELECT pg_try_advisory_lock(hashtext($1::text), hashtext($2::text))",
                str(subject_id),
                f"{subject_type}:{variant}",
            )
            if not acquired:
                # Another request/worker is already packaging this exact
                # subject. Do not queue on the lock: long storage uploads would
                # otherwise exhaust the API's DB pool with waiters.
                logger.info(
                    "Skip packaging (busy) subject=%s variant=%s",
                    subject_id,
                    variant,
                )
                return {"status": "busy", "skipped": True}
            try:
                if subject_type == "stream_track":
                    existing = await conn.fetchrow(
                        "SELECT package_status, packaged_storage_key FROM stream_tracks WHERE id = $1",
                        subject_id,
                    )
                else:
                    status_col = "package_status_ok" if variant == "ok" else "package_status_alt"
                    pkg_col = "packaged_storage_key_ok" if variant == "ok" else "packaged_storage_key_alt"
                    existing = await conn.fetchrow(
                        f"SELECT {status_col} AS package_status, {pkg_col} AS packaged_storage_key FROM suno_tasks WHERE id = $1",
                        subject_id,
                    )
                if (
                    existing is not None
                    and str(existing["package_status"] or "") == "ready"
                    and existing["packaged_storage_key"]
                ):
                    logger.info(
                        "Skip packaging already-ready subject=%s variant=%s",
                        subject_id,
                        variant,
                    )
                    return {"status": "ready", "skipped": True}

                return await self._package_plaintext_body(
                    conn,
                    plaintext,
                    subject_type=subject_type,
                    subject_id=subject_id,
                    variant=variant,
                    base_key=base_key,
                    storage=storage,
                    null_suno_urls=null_suno_urls,
                    source_key=source_key,
                )
            finally:
                await conn.execute(
                    "SELECT pg_advisory_unlock(hashtext($1::text), hashtext($2::text))",
                    str(subject_id),
                    f"{subject_type}:{variant}",
                )

    async def _mark_playable(
        self,
        conn: Any,
        *,
        subject_id: UUID,
        variant: str,
        orig_key: str,
        pkg_a_key: str,
        key_id: Any,
        null_suno_urls: bool,
    ) -> None:
        """Set just enough state for playback, before the heavy packaging work.

        ``content_license_service`` treats a track as playable when
        ``package_status = 'ready'`` and both ``packaged_storage_key`` and
        ``content_key_id`` are set. Lane B (``.b.cxa``) and the HLS segments are
        not required for that, so writing those columns here turns a
        multi-minute wait into two object uploads. The caller finishes lane B and
        HLS afterwards and re-asserts the same values.
        """
        if variant == "ok":
            await conn.execute(
                """
                UPDATE suno_tasks
                SET encrypted_original_key_ok = $2,
                    packaged_storage_key_ok = $3,
                    package_status_ok = 'ready',
                    content_key_id_ok = $4,
                    audio_url_ok = CASE WHEN $5 THEN NULL ELSE audio_url_ok END,
                    updated_at = NOW()
                WHERE id = $1
                """,
                subject_id,
                orig_key,
                pkg_a_key,
                key_id,
                null_suno_urls,
            )
        else:
            await conn.execute(
                """
                UPDATE suno_tasks
                SET encrypted_original_key_alt = $2,
                    packaged_storage_key_alt = $3,
                    package_status_alt = 'ready',
                    content_key_id_alt = $4,
                    audio_url_alt = CASE WHEN $5 THEN NULL ELSE audio_url_alt END,
                    updated_at = NOW()
                WHERE id = $1
                """,
                subject_id,
                orig_key,
                pkg_a_key,
                key_id,
                null_suno_urls,
            )

    async def _package_plaintext_body(
        self,
        conn: Any,
        plaintext: bytes,
        *,
        subject_type: str,
        subject_id: UUID,
        variant: str,
        base_key: str,
        storage: Any,
        null_suno_urls: bool,
        source_key: str | None,
    ) -> dict[str, Any]:
        await conn.execute(
            """
            INSERT INTO audio_package_jobs (subject_type, subject_id, variant, status, attempt_count)
            VALUES ($1, $2, $3, 'running', 1)
            """,
            subject_type,
            subject_id,
            variant,
        )
        kek = resolve_audio_kek()
        content_key = new_content_key()
        wrapped = wrap_content_key(kek, content_key)
        key_row = await conn.fetchrow(
            """
            INSERT INTO content_keys (
                subject_type, subject_id, variant, wrapped_key, key_version, status
            )
            VALUES ($1, $2, $3, $4,
                COALESCE((
                    SELECT MAX(key_version) + 1 FROM content_keys
                    WHERE subject_type = $1 AND subject_id = $2 AND variant = $3
                ), 1),
                'active'
            )
            RETURNING id
            """,
            subject_type,
            subject_id,
            variant,
            wrapped,
        )
        key_id = str(key_row["id"])
        original_blob = encrypt_original(plaintext, content_key)
        package_a = package_chunks(ab_plaintext_variant(plaintext, lane="a"), content_key, key_id=key_id)
        orig_key = f"{base_key}.cxo"
        pkg_a_key = f"{base_key}.cxa"
        pkg_b_key = f"{base_key}.b.cxa"
        await storage.upload_bytes(key=orig_key, data=original_blob, content_type=GCM_MIME)
        await storage.upload_bytes(key=pkg_a_key, data=package_a, content_type=GCM_MIME)

        # Web-music tracks are playable from this point. content_license_service
        # only requires package_status='ready' plus packaged_storage_key and
        # content_key_id, so lane B and the ~35 HLS segment uploads stay off the
        # critical path to first play. The UPDATEs below re-assert the same
        # values once the heavy work finishes.
        if subject_type != "stream_track":
            await self._mark_playable(
                conn,
                subject_id=subject_id,
                variant=variant,
                orig_key=orig_key,
                pkg_a_key=pkg_a_key,
                key_id=key_row["id"],
                null_suno_urls=null_suno_urls,
            )

        package_b = package_chunks(ab_plaintext_variant(plaintext, lane="b"), content_key, key_id=key_id)
        await storage.upload_bytes(key=pkg_b_key, data=package_b, content_type=GCM_MIME)
        hls_prefix = f"{base_key}.hls"
        hls_status = await self._package_and_upload_hls(
            ab_plaintext_variant(plaintext, lane="a"),
            content_key,
            storage=storage,
            prefix=hls_prefix,
        )

        if subject_type == "stream_track":
            await conn.execute(
                """
                UPDATE stream_tracks
                SET encrypted_original_storage_key = $2,
                    packaged_storage_key = $3,
                    packaged_storage_key_b = $4,
                    package_status = 'ready',
                    content_key_id = $5,
                    packaged_size_bytes = $6,
                    hls_storage_prefix = $7,
                    hls_status = $8,
                    updated_at = NOW()
                WHERE id = $1
                """,
                subject_id,
                orig_key,
                pkg_a_key,
                pkg_b_key,
                key_row["id"],
                len(package_a),
                hls_prefix if hls_status == "ready" else None,
                hls_status,
            )
        else:
            if variant == "ok":
                await conn.execute(
                    """
                    UPDATE suno_tasks
                    SET encrypted_original_key_ok = $2,
                        packaged_storage_key_ok = $3,
                        packaged_storage_key_ok_b = $4,
                        package_status_ok = 'ready',
                        content_key_id_ok = $5,
                        hls_storage_prefix_ok = $6,
                        hls_status_ok = $7,
                        audio_url_ok = CASE WHEN $8 THEN NULL ELSE audio_url_ok END,
                        updated_at = NOW()
                    WHERE id = $1
                    """,
                    subject_id,
                    orig_key,
                    pkg_a_key,
                    pkg_b_key,
                    key_row["id"],
                    hls_prefix if hls_status == "ready" else None,
                    hls_status,
                    null_suno_urls,
                )
            else:
                await conn.execute(
                    """
                    UPDATE suno_tasks
                    SET encrypted_original_key_alt = $2,
                        packaged_storage_key_alt = $3,
                        packaged_storage_key_alt_b = $4,
                        package_status_alt = 'ready',
                        content_key_id_alt = $5,
                        hls_storage_prefix_alt = $6,
                        hls_status_alt = $7,
                        audio_url_alt = CASE WHEN $8 THEN NULL ELSE audio_url_alt END,
                        updated_at = NOW()
                    WHERE id = $1
                    """,
                    subject_id,
                    orig_key,
                    pkg_a_key,
                    pkg_b_key,
                    key_row["id"],
                    hls_prefix if hls_status == "ready" else None,
                    hls_status,
                    null_suno_urls,
                )
        await conn.execute(
            """
            UPDATE audio_package_jobs
            SET status = 'ready', updated_at = NOW()
            WHERE id = (
                SELECT id FROM audio_package_jobs
                WHERE subject_type = $1 AND subject_id = $2 AND variant = $3
                ORDER BY created_at DESC LIMIT 1
            )
            """,
            subject_type,
            subject_id,
            variant,
        )
        logger.info(
            "Packaged audio subject_type=%s id=%s variant=%s key=%s",
            subject_type,
            subject_id,
            variant,
            orig_key,
        )
        if source_key and source_key not in {orig_key, pkg_a_key, pkg_b_key}:
            try:
                await storage.upload_bytes(key=source_key, data=original_blob, content_type=GCM_MIME)
                await conn.execute(
                    """
                    INSERT INTO audio_package_jobs (subject_type, subject_id, variant, status, attempt_count)
                    VALUES ($1, $2, $3, $4, 1)
                    """,
                    f"{subject_type}_source",
                    subject_id,
                    variant,
                    "ready",
                )
            except Exception as exc:
                logger.warning(
                    "source seal failed subject_type=%s id=%s key=%s: %s",
                    subject_type,
                    subject_id,
                    source_key,
                    exc,
                )
        return {
            "status": "ready",
            "content_key_id": key_id,
            "encrypted_original_storage_key": orig_key,
            "packaged_storage_key": pkg_a_key,
            "packaged_storage_key_b": pkg_b_key,
            "hls_status": hls_status,
            "hls_storage_prefix": hls_prefix if hls_status == "ready" else None,
        }

    async def _package_and_upload_hls(
        self,
        mp3_bytes: bytes,
        content_key: bytes,
        *,
        storage: Any,
        prefix: str,
    ) -> str:
        try:
            artifacts = package_hls_aes128(mp3_bytes, content_key)
        except HlsPackagerError as exc:
            logger.warning("HLS packaging skipped for %s: %s", prefix, exc)
            return "none"
        try:
            for name, data in artifacts.files.items():
                content_type = (
                    "application/vnd.apple.mpegurl"
                    if name.endswith(".m3u8")
                    else "video/mp2t"
                )
                await storage.upload_bytes(
                    key=f"{prefix}/{name}",
                    data=data,
                    content_type=content_type,
                )
        except Exception as exc:
            logger.warning("HLS upload failed for %s: %s", prefix, exc)
            return "failed"
        return "ready"

    async def backfill_hls(self, *, limit: int = 10, web_music_only: bool = True) -> dict[str, Any]:
        from platform_api.services.audio_packager import decrypt_package, unwrap_content_key
        from platform_api.services.storage_service import StorageService
        from platform_api.services.streaming_config_service import resolve_streaming_storage_config

        config = await resolve_streaming_storage_config(self._pool)
        if not config.configured:
            return {"ready": 0, "error": "storage not configured", "web_music_only": web_music_only}
        storage = StorageService.from_config(config)
        kek = resolve_audio_kek()
        ready = 0
        # Desktop studio / catalog stream_tracks stay untouched until we opt in.
        web_filter = "AND source = 'web_music'" if web_music_only else ""
        task_rows = await self._pool.fetch(
            f"""
            SELECT id, 'ok' AS variant, packaged_storage_key_ok AS packaged_storage_key,
                   content_key_id_ok AS content_key_id, hls_status_ok AS hls_status
            FROM suno_tasks
            WHERE package_status_ok = 'ready'
              AND hls_status_ok IS DISTINCT FROM 'ready'
              AND packaged_storage_key_ok IS NOT NULL
              AND content_key_id_ok IS NOT NULL
              {web_filter}
            UNION ALL
            SELECT id, 'alt' AS variant, packaged_storage_key_alt AS packaged_storage_key,
                   content_key_id_alt AS content_key_id, hls_status_alt AS hls_status
            FROM suno_tasks
            WHERE package_status_alt = 'ready'
              AND hls_status_alt IS DISTINCT FROM 'ready'
              AND packaged_storage_key_alt IS NOT NULL
              AND content_key_id_alt IS NOT NULL
              {web_filter}
            ORDER BY id ASC
            LIMIT $1
            """,
            limit,
        )
        skipped = 0
        for row in task_rows:
            wrapped = await self._wrapped_key(row["content_key_id"])
            pkg_key = str(row["packaged_storage_key"] or "")
            if not wrapped or not pkg_key:
                skipped += 1
                continue
            try:
                blob = await storage.download_bytes(key=pkg_key)
                if not blob:
                    skipped += 1
                    continue
                content_key = unwrap_content_key(kek, wrapped)
                mp3 = decrypt_package(blob, content_key)
                prefix = f"{pkg_key}.hls"
                status = await self._package_and_upload_hls(
                    mp3,
                    content_key,
                    storage=storage,
                    prefix=prefix,
                )
            except Exception as exc:
                skipped += 1
                logger.warning(
                    "hls backfill skipped web clip id=%s variant=%s: %s",
                    row["id"],
                    row["variant"],
                    exc,
                )
                continue
            variant = str(row["variant"] or "ok")
            if variant == "ok":
                await self._pool.execute(
                    """
                    UPDATE suno_tasks
                    SET hls_storage_prefix_ok = $2, hls_status_ok = $3, updated_at = NOW()
                    WHERE id = $1
                    """,
                    row["id"],
                    prefix if status == "ready" else None,
                    status,
                )
            else:
                await self._pool.execute(
                    """
                    UPDATE suno_tasks
                    SET hls_storage_prefix_alt = $2, hls_status_alt = $3, updated_at = NOW()
                    WHERE id = $1
                    """,
                    row["id"],
                    prefix if status == "ready" else None,
                    status,
                )
            if status == "ready":
                ready += 1
        return {"ready": ready, "attempted": len(task_rows), "skipped": skipped, "web_music_only": web_music_only}

    async def _record_job(
        self,
        subject_type: str,
        subject_id: UUID,
        variant: str,
        *,
        status: str,
    ) -> None:
        await self._pool.execute(
            """
            INSERT INTO audio_package_jobs (subject_type, subject_id, variant, status, attempt_count)
            VALUES ($1, $2, $3, $4, 1)
            """,
            subject_type,
            subject_id,
            variant,
            status,
        )

    async def _wrapped_key(self, key_id: Any) -> bytes | None:
        if not key_id:
            return None
        wrapped = await self._pool.fetchval(
            "SELECT wrapped_key FROM content_keys WHERE id = $1 AND status = 'active'",
            key_id,
        )
        return bytes(wrapped) if wrapped else None

    def _encrypt_with_wrapped(self, plaintext: bytes, wrapped_key: bytes) -> bytes:
        if looks_like_camxora_audio(plaintext):
            return plaintext
        content_key = unwrap_content_key(resolve_audio_kek(), bytes(wrapped_key))
        return encrypt_original(plaintext, content_key)

    def _decrypt_with_wrapped(self, blob: bytes, wrapped_key: bytes) -> bytes:
        if not looks_like_camxora_audio(blob):
            return blob
        content_key = unwrap_content_key(resolve_audio_kek(), bytes(wrapped_key))
        return decrypt_original(blob, content_key)

    async def decrypt_stored_original(self, storage: Any, storage_key: str, wrapped_key: bytes) -> bytes:
        blob = await storage.download_bytes(key=storage_key)
        if not blob:
            raise ValueError("encrypted original missing")
        return self._decrypt_with_wrapped(blob, wrapped_key)

    async def encrypt_suno_export(
        self,
        plaintext: bytes,
        *,
        subject_id: UUID,
        variant: str,
    ) -> bytes:
        if not plaintext or looks_like_camxora_audio(plaintext):
            return plaintext
        col = "content_key_id_ok" if variant == "ok" else "content_key_id_alt"
        key_id = await self._pool.fetchval(
            f"SELECT {col} FROM suno_tasks WHERE id = $1",
            subject_id,
        )
        wrapped = await self._wrapped_key(key_id)
        if not wrapped:
            return plaintext
        return self._encrypt_with_wrapped(plaintext, wrapped)

    async def decrypt_suno_export(
        self,
        blob: bytes,
        *,
        subject_id: UUID,
        variant: str,
    ) -> bytes:
        if not blob or not looks_like_camxora_audio(blob):
            return blob
        col = "content_key_id_ok" if variant == "ok" else "content_key_id_alt"
        key_id = await self._pool.fetchval(
            f"SELECT {col} FROM suno_tasks WHERE id = $1",
            subject_id,
        )
        wrapped = await self._wrapped_key(key_id)
        if not wrapped:
            raise ValueError("ciphertext without content key")
        return self._decrypt_with_wrapped(blob, wrapped)

    async def _seal_key(self, storage: Any, key: str, wrapped_key: bytes) -> str:
        data = await storage.download_bytes(key=key)
        if not data:
            return "missing"
        if looks_like_camxora_audio(data):
            return "already"
        blob = self._encrypt_with_wrapped(data, wrapped_key)
        await storage.upload_bytes(key=key, data=blob, content_type=GCM_MIME)
        return "sealed"

    async def backfill(self, *, limit: int = 10, web_music_only: bool = True) -> dict[str, Any]:
        from platform_api.services.storage_service import StorageService
        from platform_api.services.streaming_config_service import resolve_streaming_storage_config

        config = await resolve_streaming_storage_config(self._pool)
        if not config.configured:
            return {"packaged": 0, "sealed_sources": 0, "sealed_exports": 0, "error": "storage not configured"}
        storage = StorageService.from_config(config)
        packaged = await self._backfill_mp3(storage, limit=limit, web_music_only=web_music_only)
        sealed_sources = await self._backfill_seal_sources(
            storage, limit=limit, web_music_only=web_music_only
        )
        sealed_exports = await self._backfill_exports(storage, limit=limit)
        return {
            "packaged": packaged,
            "sealed_sources": sealed_sources,
            "sealed_exports": sealed_exports,
            "web_music_only": web_music_only,
        }

    async def _backfill_mp3(self, storage: Any, *, limit: int, web_music_only: bool) -> int:
        packaged = 0
        if web_music_only:
            tracks = await self._pool.fetch(
                """
                SELECT t.id, t.storage_key, t.variant
                FROM stream_tracks t
                INNER JOIN suno_tasks s ON s.id = t.suno_task_id AND s.source = 'web_music'
                WHERE COALESCE(t.package_status, 'none') = 'none'
                  AND t.storage_key IS NOT NULL AND t.storage_key <> ''
                ORDER BY t.created_at DESC
                LIMIT $1
                """,
                limit,
            )
        else:
            tracks = await self._pool.fetch(
                """
                SELECT id, storage_key, variant
                FROM stream_tracks
                WHERE COALESCE(package_status, 'none') = 'none'
                  AND storage_key IS NOT NULL AND storage_key <> ''
                ORDER BY created_at DESC
                LIMIT $1
                """,
                limit,
            )
        for row in tracks:
            try:
                storage_key = str(row["storage_key"])
                data = await storage.download_bytes(key=storage_key)
                if not data:
                    continue
                await self.package_plaintext(
                    data,
                    subject_type="stream_track",
                    subject_id=row["id"],
                    variant=str(row["variant"] or "ok"),
                    base_key=storage_key.rsplit(".mp3", 1)[0],
                    storage=storage,
                    source_key=storage_key,
                )
                packaged += 1
                print(f"packaged stream_track id={row['id']}", flush=True)
            except Exception as exc:
                logger.warning("stream_track package failed id=%s: %s", row["id"], exc)

        remaining = max(0, limit - packaged)
        if remaining:
            tasks = await self._pool.fetch(
                """
                SELECT id, b2_storage_key_ok, b2_storage_key_alt,
                       package_status_ok, package_status_alt
                FROM suno_tasks
                WHERE source = 'web_music'
                  AND (
                    (COALESCE(package_status_ok, 'none') = 'none' AND COALESCE(b2_storage_key_ok, '') <> '')
                    OR (COALESCE(package_status_alt, 'none') = 'none' AND COALESCE(b2_storage_key_alt, '') <> '')
                  )
                ORDER BY updated_at DESC
                LIMIT $1
                """,
                remaining,
            )
            for row in tasks:
                for variant, key_col, status_col in (
                    ("ok", "b2_storage_key_ok", "package_status_ok"),
                    ("alt", "b2_storage_key_alt", "package_status_alt"),
                ):
                    if str(row[status_col] or "none") != "none":
                        continue
                    storage_key = str(row[key_col] or "").strip()
                    if not storage_key:
                        continue
                    try:
                        data = await storage.download_bytes(key=storage_key)
                        if not data:
                            continue
                        await self.package_plaintext(
                            data,
                            subject_type="suno_task",
                            subject_id=row["id"],
                            variant=variant,
                            base_key=storage_key.rsplit(".mp3", 1)[0],
                            storage=storage,
                            null_suno_urls=True,
                            source_key=storage_key,
                        )
                        packaged += 1
                        print(f"packaged suno_task id={row['id']} variant={variant}", flush=True)
                    except Exception as exc:
                        logger.warning(
                            "suno_task package failed id=%s variant=%s: %s",
                            row["id"],
                            variant,
                            exc,
                        )
        return packaged

    async def _backfill_seal_sources(
        self, storage: Any, *, limit: int, web_music_only: bool
    ) -> int:
        sealed = 0
        if web_music_only:
            tracks = await self._pool.fetch(
                """
                SELECT t.id, t.storage_key, t.variant, t.content_key_id
                FROM stream_tracks t
                INNER JOIN suno_tasks s ON s.id = t.suno_task_id AND s.source = 'web_music'
                WHERE COALESCE(t.package_status, 'none') = 'ready'
                  AND t.storage_key IS NOT NULL AND t.storage_key <> ''
                  AND t.content_key_id IS NOT NULL
                  AND NOT EXISTS (
                    SELECT 1 FROM audio_package_jobs j
                    WHERE j.subject_type = 'stream_track_source'
                      AND j.subject_id = t.id
                      AND j.status = 'ready'
                  )
                ORDER BY t.updated_at DESC
                LIMIT $1
                """,
                limit,
            )
        else:
            tracks = await self._pool.fetch(
                """
                SELECT id, storage_key, variant, content_key_id
                FROM stream_tracks
                WHERE COALESCE(package_status, 'none') = 'ready'
                  AND storage_key IS NOT NULL AND storage_key <> ''
                  AND content_key_id IS NOT NULL
                  AND NOT EXISTS (
                    SELECT 1 FROM audio_package_jobs j
                    WHERE j.subject_type = 'stream_track_source'
                      AND j.subject_id = stream_tracks.id
                      AND j.status = 'ready'
                  )
                ORDER BY updated_at DESC
                LIMIT $1
                """,
                limit,
            )
        for row in tracks:
            try:
                wrapped = await self._wrapped_key(row["content_key_id"])
                if not wrapped:
                    continue
                result = await self._seal_key(storage, str(row["storage_key"]), wrapped)
                if result in {"sealed", "already"}:
                    await self._record_job(
                        "stream_track_source",
                        row["id"],
                        str(row["variant"] or "ok"),
                        status="ready",
                    )
                if result == "sealed":
                    sealed += 1
                    print(f"sealed stream_track source id={row['id']}", flush=True)
            except Exception as exc:
                logger.warning("stream_track source seal failed id=%s: %s", row["id"], exc)

        remaining = max(0, limit - sealed)
        if not remaining:
            return sealed
        tasks = await self._pool.fetch(
            """
            SELECT id, b2_storage_key_ok, b2_storage_key_alt,
                   content_key_id_ok, content_key_id_alt,
                   package_status_ok, package_status_alt
            FROM suno_tasks
            WHERE source = 'web_music'
              AND (
                (
                    COALESCE(package_status_ok, 'none') = 'ready'
                    AND content_key_id_ok IS NOT NULL
                    AND COALESCE(b2_storage_key_ok, '') <> ''
                    AND NOT EXISTS (
                        SELECT 1 FROM audio_package_jobs j
                        WHERE j.subject_type = 'suno_task_source'
                          AND j.subject_id = suno_tasks.id
                          AND j.variant = 'ok'
                          AND j.status = 'ready'
                    )
                )
                OR (
                    COALESCE(package_status_alt, 'none') = 'ready'
                    AND content_key_id_alt IS NOT NULL
                    AND COALESCE(b2_storage_key_alt, '') <> ''
                    AND NOT EXISTS (
                        SELECT 1 FROM audio_package_jobs j
                        WHERE j.subject_type = 'suno_task_source'
                          AND j.subject_id = suno_tasks.id
                          AND j.variant = 'alt'
                          AND j.status = 'ready'
                    )
                )
              )
            ORDER BY updated_at DESC
            LIMIT $1
            """,
            remaining,
        )
        for row in tasks:
            for variant, key_col, key_id_col, status_col in (
                ("ok", "b2_storage_key_ok", "content_key_id_ok", "package_status_ok"),
                ("alt", "b2_storage_key_alt", "content_key_id_alt", "package_status_alt"),
            ):
                if str(row[status_col] or "none") != "ready":
                    continue
                storage_key = str(row[key_col] or "").strip()
                if not storage_key:
                    continue
                try:
                    wrapped = await self._wrapped_key(row[key_id_col])
                    if not wrapped:
                        continue
                    result = await self._seal_key(storage, storage_key, wrapped)
                    if result in {"sealed", "already"}:
                        await self._record_job(
                            "suno_task_source",
                            row["id"],
                            variant,
                            status="ready",
                        )
                    if result == "sealed":
                        sealed += 1
                        print(
                            f"sealed suno_task source id={row['id']} variant={variant}",
                            flush=True,
                        )
                except Exception as exc:
                    logger.warning(
                        "suno_task source seal failed id=%s variant=%s: %s",
                        row["id"],
                        variant,
                        exc,
                    )
        return sealed

    async def _backfill_exports(self, storage: Any, *, limit: int) -> int:
        sealed = 0
        rows = await self._pool.fetch(
            """
            SELECT id,
                   b2_wav_storage_key_ok, b2_wav_storage_key_alt,
                   b2_lrc_storage_key_ok, b2_lrc_storage_key_alt,
                   content_key_id_ok, content_key_id_alt
            FROM suno_tasks
            WHERE source = 'web_music'
              AND (
                (
                    content_key_id_ok IS NOT NULL
                    AND (
                        (COALESCE(b2_wav_storage_key_ok, '') <> '' AND NOT EXISTS (
                            SELECT 1 FROM audio_package_jobs j
                            WHERE j.subject_type = 'suno_wav'
                              AND j.subject_id = suno_tasks.id
                              AND j.variant = 'ok' AND j.status = 'ready'
                        ))
                        OR (COALESCE(b2_lrc_storage_key_ok, '') <> '' AND NOT EXISTS (
                            SELECT 1 FROM audio_package_jobs j
                            WHERE j.subject_type = 'suno_lrc'
                              AND j.subject_id = suno_tasks.id
                              AND j.variant = 'ok' AND j.status = 'ready'
                        ))
                    )
                )
                OR (
                    content_key_id_alt IS NOT NULL
                    AND (
                        (COALESCE(b2_wav_storage_key_alt, '') <> '' AND NOT EXISTS (
                            SELECT 1 FROM audio_package_jobs j
                            WHERE j.subject_type = 'suno_wav'
                              AND j.subject_id = suno_tasks.id
                              AND j.variant = 'alt' AND j.status = 'ready'
                        ))
                        OR (COALESCE(b2_lrc_storage_key_alt, '') <> '' AND NOT EXISTS (
                            SELECT 1 FROM audio_package_jobs j
                            WHERE j.subject_type = 'suno_lrc'
                              AND j.subject_id = suno_tasks.id
                              AND j.variant = 'alt' AND j.status = 'ready'
                        ))
                    )
                )
              )
            ORDER BY updated_at DESC
            LIMIT $1
            """,
            limit,
        )
        for row in rows:
            for variant, wav_col, lrc_col, key_id_col in (
                ("ok", "b2_wav_storage_key_ok", "b2_lrc_storage_key_ok", "content_key_id_ok"),
                ("alt", "b2_wav_storage_key_alt", "b2_lrc_storage_key_alt", "content_key_id_alt"),
            ):
                wrapped = await self._wrapped_key(row[key_id_col])
                if not wrapped:
                    continue
                for kind, key_col in (("suno_wav", wav_col), ("suno_lrc", lrc_col)):
                    storage_key = str(row[key_col] or "").strip()
                    if not storage_key:
                        continue
                    already = await self._pool.fetchval(
                        """
                        SELECT 1 FROM audio_package_jobs
                        WHERE subject_type = $1 AND subject_id = $2 AND variant = $3 AND status = 'ready'
                        LIMIT 1
                        """,
                        kind,
                        row["id"],
                        variant,
                    )
                    if already:
                        continue
                    try:
                        result = await self._seal_key(storage, storage_key, wrapped)
                        if result in {"sealed", "already"}:
                            await self._record_job(kind, row["id"], variant, status="ready")
                        if result == "sealed":
                            sealed += 1
                            print(
                                f"sealed {kind} id={row['id']} variant={variant}",
                                flush=True,
                            )
                    except Exception as exc:
                        logger.warning(
                            "%s seal failed id=%s variant=%s: %s",
                            kind,
                            row["id"],
                            variant,
                            exc,
                        )
        return sealed
