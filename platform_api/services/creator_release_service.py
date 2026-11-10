"""Creator release workflow: draft, submit, review, publish, unpublish."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from platform_api.exceptions import DuplicateError, NotFoundError, ValidationError
from platform_api.repositories.creator_repo import CreatorRepository
from platform_api.repositories.streaming_repo import StreamingRepository
from platform_api.services.streaming_slug import slugify

VARIANTS = {"ok", "alt"}
RELEASE_TYPES = {"single", "ep", "album"}


def _row(row: Any) -> dict[str, Any]:
    data = dict(row)
    metadata = data.get("metadata")
    if isinstance(metadata, str):
        try:
            data["metadata"] = json.loads(metadata)
        except json.JSONDecodeError:
            data["metadata"] = {}
    return data


async def _notify(
    pool: Any,
    user_id: Any,
    event_type: str,
    payload: dict[str, Any],
) -> None:
    await pool.execute(
        """
        INSERT INTO notification_queue (user_id, event_type, payload, expires_at)
        VALUES ($1, $2, $3::jsonb, NOW() + INTERVAL '30 days')
        """,
        user_id,
        event_type,
        json.dumps(payload),
    )


def _storage_key(task: dict[str, Any], variant: str) -> str | None:
    for column in (
        f"b2_storage_key_{variant}",
        f"packaged_storage_key_{variant}",
        f"b2_full_storage_key_{variant}",
    ):
        value = str(task.get(column) or "").strip()
        if value:
            return value
    return None


def _is_ready(task: dict[str, Any], variant: str) -> bool:
    if str(task.get(f"stream_ready_{variant}") or "").lower() in {"1", "true", "t"}:
        return True
    if str(task.get(f"package_status_{variant}") or "").lower() == "ready":
        return True
    return _storage_key(task, variant) is not None


def _validate_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    title = str(metadata.get("title") or "").strip()
    if not 1 <= len(title) <= 100:
        raise ValidationError(
            "title must be 1-100 characters.",
            details={"fields": {"title": "1-100 characters"}},
        )
    genre = str(metadata.get("genre") or "").strip()
    if not 1 <= len(genre) <= 120:
        raise ValidationError(
            "genre is required.",
            details={"fields": {"genre": "required"}},
        )
    language = str(metadata.get("language") or "km").strip().lower()
    if not 2 <= len(language) <= 8:
        raise ValidationError(
            "language is required.",
            details={"fields": {"language": "required"}},
        )
    release_type = str(metadata.get("release_type") or "single").strip().lower()
    if release_type not in RELEASE_TYPES:
        raise ValidationError(
            "release_type must be single, ep, or album.",
            details={"fields": {"release_type": "invalid"}},
        )
    if metadata.get("rights_attested") is not True:
        raise ValidationError(
            "You must attest that you own or have cleared the rights.",
            details={"fields": {"rights_attested": "required"}},
        )
    lyrics = metadata.get("lyrics")
    if lyrics is not None:
        lyrics = str(lyrics).strip() or None
    description = metadata.get("description")
    if description is not None:
        description = str(description).strip()[:500] or None
    cover_url = metadata.get("cover_url")
    if cover_url is not None:
        cover_url = str(cover_url).strip()[:1000] or None

    return {
        "title": title,
        "genre": genre,
        "genres": list(metadata.get("genres") or [genre])[:3],
        "language": language,
        "release_type": release_type,
        "rights_attested": True,
        "lyrics": lyrics,
        "description": description,
        "cover_url": cover_url,
        "release_date": metadata.get("release_date"),
    }


class CreatorReleaseService:
    def __init__(self, pool: Any) -> None:
        self._pool = pool
        self._profiles = CreatorRepository(pool)
        self._streaming = StreamingRepository(pool)

    async def _task_for_user(self, task_id: str, user_id: str) -> dict[str, Any]:
        try:
            UUID(str(task_id))
        except (TypeError, ValueError) as exc:
            raise ValidationError("Invalid source task id.") from exc
        row = await self._pool.fetchrow(
            "SELECT * FROM suno_tasks WHERE id = $1 AND user_id = $2",
            task_id,
            user_id,
        )
        if row is None:
            raise NotFoundError("Generation not found.")
        return _row(row)

    async def create_draft(
        self,
        user_id: str,
        *,
        source_task_id: str,
        variant: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if await self._profiles.get_by_user_id(user_id) is None:
            # Publishing must not require an application step: give the creator
            # a working profile on their first release and let them polish it
            # afterwards.
            from platform_api.services.creator_profile_service import (
                CreatorProfileService,
            )

            await CreatorProfileService(self._pool).ensure_profile(user_id)
        if variant not in VARIANTS:
            raise ValidationError(
                "variant must be ok or alt.",
                details={"fields": {"variant": "invalid"}},
            )
        task = await self._task_for_user(source_task_id, user_id)
        existing = await self._pool.fetchrow(
            """
            SELECT id FROM creator_releases
            WHERE creator_id = $1 AND source_task_id = $2 AND source_variant = $3
            """,
            user_id,
            task["id"],
            variant,
        )
        if existing:
            raise DuplicateError("A release already exists for this generation and variant.")

        incoming = metadata or {}
        ai_disclosure = str(incoming.get("ai_disclosure") or "none")
        if ai_disclosure == "ai_generated":
            ai_disclosure = "ai_artist"
        if ai_disclosure not in {"none", "ai_assisted", "ai_artist"}:
            ai_disclosure = "none"
        origin = str(incoming.get("origin") or "ai_generated")
        if origin not in {"original", "ai_assisted", "ai_generated"}:
            origin = "ai_generated"

        row = await self._pool.fetchrow(
            """
            INSERT INTO creator_releases (
                creator_id, source_type, source_task_id, source_variant,
                status, metadata, ai_disclosure, origin, updated_at
            ) VALUES ($1, 'web_music_generation', $2, $3, 'draft', $4::jsonb, $5, $6, NOW())
            RETURNING *
            """,
            user_id,
            task["id"],
            variant,
            json.dumps(incoming),
            ai_disclosure,
            origin,
        )
        return _row(row)

    async def list_for_creator(self, user_id: str) -> list[dict[str, Any]]:
        rows = await self._pool.fetch(
            """
            SELECT * FROM creator_releases
            WHERE creator_id = $1
            ORDER BY created_at DESC
            """,
            user_id,
        )
        return [_row(row) for row in rows]

    async def get_for_creator(self, user_id: str, release_id: str) -> dict[str, Any]:
        row = await self._pool.fetchrow(
            "SELECT * FROM creator_releases WHERE id = $1 AND creator_id = $2",
            release_id,
            user_id,
        )
        if row is None:
            raise NotFoundError("Release not found.")
        return _row(row)

    async def update_draft(
        self, user_id: str, release_id: str, metadata: dict[str, Any]
    ) -> dict[str, Any]:
        release = await self.get_for_creator(user_id, release_id)
        if release["status"] not in {"draft", "changes_requested"}:
            raise ValidationError(
                "Only drafts or releases with requested changes can be edited.",
                details={"fields": {"status": "locked"}},
            )
        merged = {**(release.get("metadata") or {}), **metadata}
        ai_disclosure = str(merged.get("ai_disclosure") or release["ai_disclosure"])
        if ai_disclosure == "ai_generated":
            ai_disclosure = "ai_artist"
        if ai_disclosure not in {"none", "ai_assisted", "ai_artist"}:
            ai_disclosure = "none"
        origin = str(merged.get("origin") or release["origin"])
        if origin not in {"original", "ai_assisted", "ai_generated"}:
            origin = "ai_generated"
        row = await self._pool.fetchrow(
            """
            UPDATE creator_releases
            SET metadata = $2::jsonb, ai_disclosure = $3, origin = $4, updated_at = NOW()
            WHERE id = $1
            RETURNING *
            """,
            release_id,
            json.dumps(merged),
            ai_disclosure,
            origin,
        )
        return _row(row)

    async def quick_publish(
        self,
        user_id: str,
        *,
        source_task_id: str,
        variant: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create and publish a release from a finished generation in one call.

        This is the creator's main path: generate, then publish. Missing details
        are filled from the generation so the creator never has to complete a
        form before their music goes live.
        """
        await self._profiles.get_by_user_id(user_id)
        from platform_api.services.creator_profile_service import (
            CreatorProfileService,
        )

        await CreatorProfileService(self._pool).ensure_profile(user_id)

        task = await self._task_for_user(source_task_id, user_id)
        incoming = dict(metadata or {})

        title = str(incoming.get("title") or "").strip()
        if not title:
            title = str(
                task.get(f"title_{variant}") or task.get("title") or ""
            ).strip()
        incoming["title"] = (title or "Untitled")[:100]

        genre = str(incoming.get("genre") or "").strip()
        if not genre:
            tags = task.get("tags")
            if isinstance(tags, list):
                tags = ", ".join(str(item) for item in tags)
            genre = str(tags or "").split(",")[0].strip()
        incoming["genre"] = (genre or "Khmer Pop")[:120]
        if not incoming.get("genres"):
            incoming["genres"] = [incoming["genre"]]

        incoming.setdefault("language", "km")
        incoming.setdefault("release_type", "single")
        incoming.setdefault("rights_attested", True)

        draft = await self.create_draft(
            user_id,
            source_task_id=source_task_id,
            variant=variant,
            metadata=incoming,
        )
        return await self.submit(user_id, draft["id"])

    async def submit(self, user_id: str, release_id: str) -> dict[str, Any]:
        release = await self.get_for_creator(user_id, release_id)
        if release["status"] not in {"draft", "changes_requested"}:
            raise ValidationError(
                "This release is already published or in a locked state.",
                details={"fields": {"status": "invalid"}},
            )
        task = await self._task_for_user(str(release["source_task_id"]), user_id)
        variant = release["source_variant"]
        if not _is_ready(task, variant):
            raise ValidationError(
                "The audio for this generation is not ready yet.",
                details={"fields": {"audio": "not ready"}},
            )
        cleaned = _validate_metadata(release.get("metadata") or {})
        await self._pool.execute(
            "UPDATE creator_releases SET metadata = $2::jsonb, updated_at = NOW() WHERE id = $1",
            release_id,
            json.dumps(cleaned),
        )
        # Publish-first: automated checks passed, so go live immediately.
        # Post-publication reports, spot checks, and takedowns replace pre-review.
        result = await self.decide(
            release_id, decision="approve", reviewer_id=user_id
        )
        return result["release"]

    async def withdraw(self, user_id: str, release_id: str) -> dict[str, Any]:
        release = await self.get_for_creator(user_id, release_id)
        if release["status"] not in {"submitted", "in_review", "changes_requested"}:
            raise ValidationError(
                "Only releases in review can be withdrawn.",
                details={"fields": {"status": "invalid"}},
            )
        row = await self._pool.fetchrow(
            """
            UPDATE creator_releases
            SET status = 'draft', submitted_at = NULL, sla_due_at = NULL, updated_at = NOW()
            WHERE id = $1
            RETURNING *
            """,
            release_id,
        )
        return _row(row)

    # ------------------------------------------------------------------
    # Admin
    # ------------------------------------------------------------------
    async def list_admin(
        self, *, status: str | None = None, limit: int = 50, offset: int = 0
    ) -> dict[str, Any]:
        rows = await self._pool.fetch(
            """
            SELECT r.*, u.email, u.display_name AS user_display_name, cp.handle
            FROM creator_releases r
            JOIN users u ON u.id = r.creator_id
            LEFT JOIN creator_profiles cp ON cp.user_id = r.creator_id
            WHERE ($1::text IS NULL OR r.status = $1)
            ORDER BY r.submitted_at DESC NULLS LAST, r.created_at DESC
            LIMIT $2 OFFSET $3
            """,
            status,
            max(1, min(limit, 100)),
            max(0, offset),
        )
        total = await self._pool.fetchval(
            "SELECT COUNT(*) FROM creator_releases WHERE ($1::text IS NULL OR status = $1)",
            status,
        )
        return {
            "items": [_row(row) for row in rows],
            "total": int(total or 0),
            "limit": limit,
            "offset": offset,
        }

    async def decide(
        self,
        release_id: str,
        *,
        decision: str,
        reviewer_id: str,
        reason: str | None = None,
    ) -> dict[str, Any]:
        release = await self._pool.fetchrow(
            "SELECT * FROM creator_releases WHERE id = $1", release_id
        )
        if release is None:
            raise NotFoundError("Release not found.")
        release = _row(release)

        if decision == "request_changes":
            if not reason:
                raise ValidationError(
                    "A reason is required when requesting changes.",
                    details={"fields": {"reason": "required"}},
                )
            row = await self._pool.fetchrow(
                """
                UPDATE creator_releases
                SET status = 'changes_requested', reviewed_by = $2, reviewed_at = NOW(),
                    takedown_reason = $3, updated_at = NOW()
                WHERE id = $1 RETURNING *
                """,
                release_id,
                reviewer_id,
                reason,
            )
            return {"release": _row(row)}

        if decision == "reject":
            if not reason:
                raise ValidationError(
                    "A reason is required when rejecting.",
                    details={"fields": {"reason": "required"}},
                )
            row = await self._pool.fetchrow(
                """
                UPDATE creator_releases
                SET status = 'rejected', reviewed_by = $2, reviewed_at = NOW(),
                    takedown_reason = $3, updated_at = NOW()
                WHERE id = $1 RETURNING *
                """,
                release_id,
                reviewer_id,
                reason,
            )
            return {"release": _row(row)}

        if decision != "approve":
            raise ValidationError(
                "decision must be approve, request_changes, or reject.",
                details={"fields": {"decision": "invalid"}},
            )

        task = await self._task_for_user(str(release["source_task_id"]), str(release["creator_id"]))
        variant = release["source_variant"]
        storage_key = _storage_key(task, variant)
        if storage_key is None:
            raise ValidationError(
                "Cannot publish: the generation has no stored audio.",
                details={"fields": {"audio": "missing"}},
            )
        metadata = release.get("metadata") or {}
        title = str(metadata.get("title") or task.get("title") or "Untitled").strip()
        genre = str(metadata.get("genre") or "Pop").strip()
        album_name = str(metadata.get("release_title") or title).strip()
        album_slug = f"{slugify(album_name)}-{str(release['source_task_id'])[:8]}"
        album_id = await self._streaming.get_or_create_album(
            user_id=release["creator_id"],
            batch_id=task.get("batch_id"),
            album_name=album_name,
            album_slug=album_slug,
            channel_role=variant,
        )
        track_id = await self._streaming.upsert_track(
            user_id=release["creator_id"],
            album_id=album_id,
            song_id=task.get("song_id"),
            suno_task_id=task["id"],
            title=title,
            lyrics=metadata.get("lyrics") or task.get("lyrics"),
            variant=variant,
            storage_key=storage_key,
            size_bytes=None,
            duration_seconds=task.get(f"duration_{variant}"),
            genre=genre,
            track_number=1,
            cover_storage_key=None,
            suno_image_url=task.get(f"image_url_{variant}"),
            tags=None,
            genres=list(metadata.get("genres") or [genre]),
            suno_audio_id=task.get(f"audio_id_{variant}"),
        )
        await self._pool.execute(
            "UPDATE stream_tracks SET origin = $2 WHERE id = $1",
            track_id,
            release["origin"],
        )
        await self._pool.execute(
            """
            UPDATE stream_albums
            SET genre = $2, genres = $3::jsonb, updated_at = NOW()
            WHERE id = $1
            """,
            album_id,
            genre,
            json.dumps(list(metadata.get("genres") or [genre])),
        )
        row = await self._pool.fetchrow(
            """
            UPDATE creator_releases
            SET status = 'published', album_id = $2, track_id = $3,
                reviewed_by = $4, reviewed_at = NOW(), published_at = NOW(),
                takedown_reason = NULL, updated_at = NOW()
            WHERE id = $1 RETURNING *
            """,
            release_id,
            album_id,
            track_id,
            reviewer_id,
        )
        return {"release": _row(row)}

    async def admin_takedown(
        self,
        release_id: str,
        *,
        reviewer_id: str,
        reason: str,
    ) -> dict[str, Any]:
        if not str(reason or "").strip():
            raise ValidationError(
                "A takedown reason is required.",
                details={"fields": {"reason": "required"}},
            )
        release = await self._pool.fetchrow(
            "SELECT * FROM creator_releases WHERE id = $1", release_id
        )
        if release is None:
            raise NotFoundError("Release not found.")
        release = _row(release)
        if release.get("track_id"):
            await self._streaming.set_track_publish_status(
                release["track_id"], "unpublished"
            )
        if release.get("album_id"):
            await self._streaming.set_album_publish_status(
                release["album_id"], "unpublished"
            )
        row = await self._pool.fetchrow(
            """
            UPDATE creator_releases
            SET status = 'taken_down',
                takedown_reason = $2,
                reviewed_by = $3,
                reviewed_at = NOW(),
                updated_at = NOW()
            WHERE id = $1
            RETURNING *
            """,
            release_id,
            reason.strip(),
            reviewer_id,
        )
        metadata = release.get("metadata") or {}
        await _notify(
            self._pool,
            release["creator_id"],
            "creator_release_taken_down",
            {
                "release_id": str(release["id"]),
                "title": metadata.get("title") or "Your release",
                "reason": reason.strip(),
            },
        )
        return _row(row)

    async def unpublish(self, user_id: str, release_id: str) -> dict[str, Any]:
        release = await self.get_for_creator(user_id, release_id)
        if release["status"] != "published":
            raise ValidationError(
                "Only published releases can be unpublished.",
                details={"fields": {"status": "invalid"}},
            )
        if release.get("track_id"):
            await self._streaming.set_track_publish_status(release["track_id"], "unpublished")
        if release.get("album_id"):
            await self._streaming.set_album_publish_status(release["album_id"], "unpublished")
        row = await self._pool.fetchrow(
            """
            UPDATE creator_releases
            SET status = 'taken_down', takedown_reason = 'Unpublished by creator.',
                updated_at = NOW()
            WHERE id = $1 RETURNING *
            """,
            release_id,
        )
        return _row(row)
