"""Repository for admin-managed thumbnail text presets."""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ThumbnailTextRecord:
    id: str
    title: str
    subtitle: str | None = None
    subline: str | None = None
    placement: str = "top_center"
    alignment: str = "center"
    style_hint: str | None = None
    is_active: bool = True
    sort_order: int = 0
    notes: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class DatabaseProtocol(Protocol):
    async def fetch(self, query: str, *args: Any) -> list[dict[str, Any]]: ...

    async def fetchrow(self, query: str, *args: Any) -> dict[str, Any] | None: ...

    async def execute(self, query: str, *args: Any) -> str: ...


_SELECT_COLUMNS = """
    id, title, subtitle, subline, placement, alignment, style_hint,
    is_active, sort_order, notes, created_at, updated_at
"""


class ImageThumbnailTextRepository:
    def __init__(self, db: DatabaseProtocol) -> None:
        self._db = db

    async def list_all(self) -> list[ThumbnailTextRecord]:
        rows = await self._db.fetch(
            f"""
            SELECT {_SELECT_COLUMNS}
            FROM image_thumbnail_texts
            ORDER BY sort_order ASC, lower(title) ASC, created_at ASC
            """
        )
        return [self._row_to_record(row) for row in rows]

    async def list_active(self) -> list[ThumbnailTextRecord]:
        rows = await self._db.fetch(
            f"""
            SELECT {_SELECT_COLUMNS}
            FROM image_thumbnail_texts
            WHERE is_active = TRUE
            ORDER BY sort_order ASC, lower(title) ASC, created_at ASC
            """
        )
        return [self._row_to_record(row) for row in rows]

    async def get_by_id(self, text_id: str) -> ThumbnailTextRecord | None:
        row = await self._db.fetchrow(
            f"SELECT {_SELECT_COLUMNS} FROM image_thumbnail_texts WHERE id = $1::uuid",
            text_id,
        )
        return self._row_to_record(row) if row else None

    async def create(
        self,
        *,
        title: str,
        subtitle: str | None = None,
        subline: str | None = None,
        placement: str = "top_center",
        alignment: str = "center",
        style_hint: str | None = None,
        is_active: bool = True,
        sort_order: int = 0,
        notes: str | None = None,
    ) -> ThumbnailTextRecord | None:
        row = await self._db.fetchrow(
            """
            INSERT INTO image_thumbnail_texts (
                title, subtitle, subline, placement, alignment, style_hint,
                is_active, sort_order, notes
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            RETURNING id, title, subtitle, subline, placement, alignment,
                      style_hint, is_active, sort_order, notes, created_at, updated_at
            """,
            title,
            subtitle,
            subline,
            placement,
            alignment,
            style_hint,
            is_active,
            sort_order,
            notes,
        )
        return self._row_to_record(row) if row else None

    async def update(
        self,
        text_id: str,
        *,
        title: str | None = None,
        subtitle: str | None = None,
        subline: str | None = None,
        placement: str | None = None,
        alignment: str | None = None,
        style_hint: str | None = None,
        is_active: bool | None = None,
        sort_order: int | None = None,
        notes: str | None = None,
    ) -> ThumbnailTextRecord | None:
        row = await self._db.fetchrow(
            """
            UPDATE image_thumbnail_texts
            SET title = COALESCE($2, title),
                subtitle = CASE WHEN $3::boolean THEN $4 ELSE subtitle END,
                subline = CASE WHEN $5::boolean THEN $6 ELSE subline END,
                placement = COALESCE($7, placement),
                alignment = COALESCE($8, alignment),
                style_hint = CASE WHEN $9::boolean THEN $10 ELSE style_hint END,
                is_active = COALESCE($11, is_active),
                sort_order = COALESCE($12, sort_order),
                notes = CASE WHEN $13::boolean THEN $14 ELSE notes END,
                updated_at = NOW()
            WHERE id = $1::uuid
            RETURNING id, title, subtitle, subline, placement, alignment,
                      style_hint, is_active, sort_order, notes, created_at, updated_at
            """,
            text_id,
            title,
            subtitle is not None,
            subtitle,
            subline is not None,
            subline,
            placement,
            alignment,
            style_hint is not None,
            style_hint,
            is_active,
            sort_order,
            notes is not None,
            notes,
        )
        return self._row_to_record(row) if row else None

    async def delete(self, text_id: str) -> bool:
        result = await self._db.execute(
            "DELETE FROM image_thumbnail_texts WHERE id = $1::uuid",
            text_id,
        )
        return result.upper().startswith("DELETE")

    async def delete_all(self) -> int:
        result = await self._db.execute("DELETE FROM image_thumbnail_texts")
        try:
            return int(str(result).split()[-1])
        except (IndexError, ValueError):
            return 0

    async def count_active(self) -> int:
        value = await self._db.fetchrow(
            "SELECT COUNT(*) AS count FROM image_thumbnail_texts WHERE is_active = TRUE"
        )
        return int((value or {}).get("count") or 0)

    async def pick_rotating_text(
        self,
        *,
        user_id: UUID,
        active_ids: list[str],
        exclude_ids: list[str] | None = None,
        batch_id: UUID | None = None,
    ) -> str | None:
        candidates_all = [str(value) for value in active_ids if str(value).strip()]
        if not candidates_all:
            return None
        exclude = {str(value) for value in (exclude_ids or []) if str(value).strip()}
        acquire = getattr(self._db, "acquire", None)
        if callable(acquire):
            async with acquire() as conn:
                async with conn.transaction():
                    await conn.execute(
                        "SELECT pg_advisory_xact_lock(hashtext($1))",
                        f"thumbnail_text_rotation:{user_id}",
                    )
                    return await self._pick_rotating_on(
                        conn,
                        user_id=user_id,
                        candidates_all=candidates_all,
                        exclude=exclude,
                        batch_id=batch_id,
                    )
        return await self._pick_rotating_on(
            self._db,
            user_id=user_id,
            candidates_all=candidates_all,
            exclude=exclude,
            batch_id=batch_id,
        )

    async def _pick_rotating_on(
        self,
        db: Any,
        *,
        user_id: UUID,
        candidates_all: list[str],
        exclude: set[str],
        batch_id: UUID | None,
    ) -> str | None:
        row = await db.fetchrow(
            """
            SELECT COALESCE(MAX(cycle_number), 0) AS cycle_number
            FROM image_thumbnail_text_rotation
            WHERE user_id = $1
            """,
            user_id,
        )
        cycle = max(1, int((row or {}).get("cycle_number") or 0))
        used_rows = await db.fetch(
            """
            SELECT text_id
            FROM image_thumbnail_text_rotation
            WHERE user_id = $1 AND cycle_number = $2
            """,
            user_id,
            cycle,
        )
        used = {str(item["text_id"]) for item in used_rows}
        unused = [text_id for text_id in candidates_all if text_id not in used]
        candidates = [text_id for text_id in unused if text_id not in exclude]
        if not candidates:
            cycle += 1
            candidates = [
                text_id for text_id in candidates_all if text_id not in exclude
            ] or candidates_all
        chosen = random.choice(candidates)
        await db.execute(
            """
            INSERT INTO image_thumbnail_text_rotation (
                user_id, text_id, cycle_number, batch_id, used_at
            )
            VALUES ($1, $2::uuid, $3, $4, NOW())
            ON CONFLICT (user_id, text_id, cycle_number) DO NOTHING
            """,
            user_id,
            chosen,
            cycle,
            batch_id,
        )
        return chosen

    @staticmethod
    def _row_to_record(row: dict[str, Any]) -> ThumbnailTextRecord:
        return ThumbnailTextRecord(
            id=str(row["id"]),
            title=str(row.get("title") or ""),
            subtitle=row.get("subtitle"),
            subline=row.get("subline"),
            placement=str(row.get("placement") or "top_center"),
            alignment=str(row.get("alignment") or "center"),
            style_hint=row.get("style_hint"),
            is_active=bool(row.get("is_active", True)),
            sort_order=int(row.get("sort_order") or 0),
            notes=row.get("notes"),
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
        )
