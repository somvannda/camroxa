"""Repository for admin-curated image prompt styles."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class ImagePromptStyleRecord:
    id: str
    kind: str
    name: str
    prompt_text: str
    text_template: str | None = None
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
    id, kind, name, prompt_text, text_template, is_active, sort_order, notes,
    created_at, updated_at
"""


class ImagePromptStyleRepository:
    def __init__(self, db: DatabaseProtocol) -> None:
        self._db = db

    async def list_all(self, *, kind: str | None = None) -> list[ImagePromptStyleRecord]:
        if kind:
            rows = await self._db.fetch(
                f"""
                SELECT {_SELECT_COLUMNS}
                FROM image_prompt_styles
                WHERE lower(kind) = lower($1)
                ORDER BY kind ASC, sort_order ASC, lower(name) ASC, created_at ASC
                """,
                kind,
            )
        else:
            rows = await self._db.fetch(
                f"""
                SELECT {_SELECT_COLUMNS}
                FROM image_prompt_styles
                ORDER BY kind ASC, sort_order ASC, lower(name) ASC, created_at ASC
                """
            )
        return [self._row_to_record(row) for row in rows]

    async def list_active(self, *, kind: str) -> list[ImagePromptStyleRecord]:
        rows = await self._db.fetch(
            f"""
            SELECT {_SELECT_COLUMNS}
            FROM image_prompt_styles
            WHERE lower(kind) = lower($1)
              AND is_active = TRUE
            ORDER BY sort_order ASC, lower(name) ASC, created_at ASC
            """,
            kind,
        )
        return [self._row_to_record(row) for row in rows]

    async def get_by_id(self, style_id: str) -> ImagePromptStyleRecord | None:
        row = await self._db.fetchrow(
            f"""
            SELECT {_SELECT_COLUMNS}
            FROM image_prompt_styles
            WHERE id = $1::uuid
            """,
            style_id,
        )
        return self._row_to_record(row) if row else None

    async def create(
        self,
        *,
        kind: str,
        name: str,
        prompt_text: str,
        text_template: str | None = None,
        is_active: bool = True,
        sort_order: int = 0,
        notes: str | None = None,
        style_id: str | None = None,
    ) -> ImagePromptStyleRecord | None:
        row = await self._db.fetchrow(
            f"""
            INSERT INTO image_prompt_styles (
                id, kind, name, prompt_text, text_template, is_active, sort_order,
                notes, created_at, updated_at
            )
            VALUES (
                COALESCE($1::uuid, gen_random_uuid()), $2, $3, $4, $5, $6, $7,
                $8, NOW(), NOW()
            )
            RETURNING {_SELECT_COLUMNS}
            """,
            style_id,
            kind,
            name,
            prompt_text,
            text_template,
            is_active,
            sort_order,
            notes,
        )
        return self._row_to_record(row) if row else None

    async def update(
        self,
        style_id: str,
        *,
        kind: str | None = None,
        name: str | None = None,
        prompt_text: str | None = None,
        text_template: str | None = None,
        is_active: bool | None = None,
        sort_order: int | None = None,
        notes: str | None = None,
    ) -> ImagePromptStyleRecord | None:
        row = await self._db.fetchrow(
            f"""
            UPDATE image_prompt_styles
            SET kind = COALESCE($2, kind),
                name = COALESCE($3, name),
                prompt_text = COALESCE($4, prompt_text),
                text_template = COALESCE($5, text_template),
                is_active = COALESCE($6, is_active),
                sort_order = COALESCE($7, sort_order),
                notes = COALESCE($8, notes),
                updated_at = NOW()
            WHERE id = $1::uuid
            RETURNING {_SELECT_COLUMNS}
            """,
            style_id,
            kind,
            name,
            prompt_text,
            text_template,
            is_active,
            sort_order,
            notes,
        )
        return self._row_to_record(row) if row else None

    async def delete(self, style_id: str) -> bool:
        result = await self._db.execute(
            "DELETE FROM image_prompt_styles WHERE id = $1::uuid",
            style_id,
        )
        return result.upper().startswith("DELETE")

    async def count_active(self) -> dict[str, int]:
        rows = await self._db.fetch(
            """
            SELECT lower(kind) AS kind, COUNT(*)::int AS active
            FROM image_prompt_styles
            WHERE is_active = TRUE
            GROUP BY lower(kind)
            """
        )
        counts = {"background": 0, "thumbnail": 0}
        for row in rows:
            kind = str(row.get("kind") or "").lower()
            if kind in counts:
                counts[kind] = int(row.get("active") or 0)
        return counts

    @staticmethod
    def _row_to_record(row: dict[str, Any]) -> ImagePromptStyleRecord:
        return ImagePromptStyleRecord(
            id=str(row["id"]),
            kind=str(row["kind"]),
            name=str(row["name"]),
            prompt_text=str(row["prompt_text"]),
            text_template=row.get("text_template"),
            is_active=bool(row.get("is_active", True)),
            sort_order=int(row.get("sort_order") or 0),
            notes=row.get("notes"),
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
        )
