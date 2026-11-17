"""Repository for admin-curated image prompt styles."""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID


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

    async def delete_all(self, *, kind: str) -> int:
        """Delete every style of one kind and return how many rows were removed."""
        result = await self._db.execute(
            "DELETE FROM image_prompt_styles WHERE lower(kind) = lower($1)",
            kind,
        )
        try:
            return int(str(result).split()[-1])
        except (IndexError, ValueError):
            return 0

    async def pick_rotating_style(
        self,
        *,
        user_id: UUID,
        kind: str,
        active_ids: list[str],
        exclude_ids: list[str] | None = None,
        batch_id: UUID | None = None,
    ) -> str | None:
        """Pick one active style for a user's current cycle, then advance it.

        Every active style is used once per cycle in random order. When the
        cycle is exhausted (or the batch exclusion leaves nothing), a new cycle
        starts and the excluded styles are avoided while alternatives exist.
        """
        candidates_all = [str(value) for value in active_ids if str(value).strip()]
        if not candidates_all:
            return None
        exclude = {str(value) for value in (exclude_ids or []) if str(value).strip()}
        kind_key = str(kind or "").strip().lower() or "background"

        acquire = getattr(self._db, "acquire", None)
        if callable(acquire):
            async with acquire() as conn:
                async with conn.transaction():
                    await conn.execute(
                        "SELECT pg_advisory_xact_lock(hashtext($1))",
                        f"image_prompt_rotation:{user_id}:{kind_key}",
                    )
                    return await self._pick_rotating_on(
                        conn,
                        user_id=user_id,
                        kind_key=kind_key,
                        candidates_all=candidates_all,
                        exclude=exclude,
                        batch_id=batch_id,
                    )
        return await self._pick_rotating_on(
            self._db,
            user_id=user_id,
            kind_key=kind_key,
            candidates_all=candidates_all,
            exclude=exclude,
            batch_id=batch_id,
        )

    async def _pick_rotating_on(
        self,
        db: Any,
        *,
        user_id: UUID,
        kind_key: str,
        candidates_all: list[str],
        exclude: set[str],
        batch_id: UUID | None,
    ) -> str | None:
        row = await db.fetchrow(
            """
            SELECT COALESCE(MAX(cycle_number), 0) AS cycle_number
            FROM image_prompt_rotation
            WHERE user_id = $1 AND kind = $2
            """,
            user_id,
            kind_key,
        )
        cycle = max(1, int((row or {}).get("cycle_number") or 0))
        used_rows = await db.fetch(
            """
            SELECT style_id
            FROM image_prompt_rotation
            WHERE user_id = $1 AND kind = $2 AND cycle_number = $3
            """,
            user_id,
            kind_key,
            cycle,
        )
        used = {str(item["style_id"]) for item in used_rows}
        unused = [style_id for style_id in candidates_all if style_id not in used]
        candidates = [style_id for style_id in unused if style_id not in exclude]
        if not candidates:
            # Either the cycle is exhausted or the remaining styles are all
            # already used by this batch. Start the next cycle and keep the
            # batch's channels distinct while alternatives exist.
            cycle += 1
            candidates = [
                style_id for style_id in candidates_all if style_id not in exclude
            ] or candidates_all
        chosen = random.choice(candidates)
        await db.execute(
            """
            INSERT INTO image_prompt_rotation (
                user_id, kind, style_id, cycle_number, batch_id, used_at
            )
            VALUES ($1, $2, $3::uuid, $4, $5, NOW())
            ON CONFLICT (user_id, kind, style_id, cycle_number) DO NOTHING
            """,
            user_id,
            kind_key,
            chosen,
            cycle,
            batch_id,
        )
        return chosen

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
