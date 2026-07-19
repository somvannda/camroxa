"""Repository for admin-managed Suno lyrics blocklist terms."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg

from platform_api.exceptions import DuplicateError, NotFoundError


class SunoBlocklistRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    @staticmethod
    def _row_to_dict(row: asyncpg.Record) -> dict[str, Any]:
        return dict(row)

    async def list_all(self) -> list[dict[str, Any]]:
        rows = await self._pool.fetch(
            """
            SELECT id, term, replacement, severity, source, enabled, notes,
                   created_at, updated_at
            FROM suno_blocklist_terms
            ORDER BY LOWER(term) ASC
            """
        )
        return [self._row_to_dict(row) for row in rows]

    async def get_by_id(self, term_id: UUID) -> dict[str, Any] | None:
        row = await self._pool.fetchrow(
            """
            SELECT id, term, replacement, severity, source, enabled, notes,
                   created_at, updated_at
            FROM suno_blocklist_terms
            WHERE id = $1
            """,
            term_id,
        )
        return self._row_to_dict(row) if row else None

    async def get_enabled_terms(
        self,
        *,
        channel_profile_id: UUID | None = None,
    ) -> list[dict[str, Any]]:
        if channel_profile_id is None:
            rows = await self._pool.fetch(
                """
                SELECT id, term, replacement, severity, source, enabled, notes,
                       channel_profile_id, created_at, updated_at
                FROM suno_blocklist_terms
                WHERE enabled = TRUE
                  AND channel_profile_id IS NULL
                ORDER BY LOWER(term) ASC
                """
            )
        else:
            rows = await self._pool.fetch(
                """
                SELECT id, term, replacement, severity, source, enabled, notes,
                       channel_profile_id, created_at, updated_at
                FROM suno_blocklist_terms
                WHERE enabled = TRUE
                  AND (
                    channel_profile_id IS NULL
                    OR channel_profile_id = $1
                  )
                ORDER BY LOWER(term) ASC
                """,
                channel_profile_id,
            )
        return [self._row_to_dict(row) for row in rows]

    async def create(
        self,
        *,
        term: str,
        replacement: str | None,
        severity: str,
        source: str = "manual",
        enabled: bool = True,
        notes: str | None = None,
    ) -> dict[str, Any]:
        try:
            row = await self._pool.fetchrow(
                """
                INSERT INTO suno_blocklist_terms (
                    id, term, replacement, severity, source, enabled, notes,
                    created_at, updated_at
                )
                VALUES (
                    gen_random_uuid(), $1, $2, $3, $4, $5, $6, NOW(), NOW()
                )
                RETURNING id, term, replacement, severity, source, enabled, notes,
                          created_at, updated_at
                """,
                term,
                replacement,
                severity,
                source,
                enabled,
                notes,
            )
        except asyncpg.UniqueViolationError:
            raise DuplicateError(
                "A blocklist term with this value already exists.",
                details={"term": term},
            )
        return self._row_to_dict(row)

    async def update(
        self,
        term_id: UUID,
        *,
        term: str | None = None,
        replacement: str | None = None,
        severity: str | None = None,
        enabled: bool | None = None,
        notes: str | None = None,
        clear_replacement: bool = False,
    ) -> dict[str, Any]:
        existing = await self.get_by_id(term_id)
        if existing is None:
            raise NotFoundError("Blocklist term not found.", details={"id": str(term_id)})

        next_term = term if term is not None else str(existing["term"])
        next_replacement = None if clear_replacement else (
            replacement if replacement is not None else existing.get("replacement")
        )
        next_severity = severity if severity is not None else str(existing["severity"])
        next_enabled = enabled if enabled is not None else bool(existing["enabled"])
        next_notes = notes if notes is not None else existing.get("notes")

        try:
            row = await self._pool.fetchrow(
                """
                UPDATE suno_blocklist_terms
                SET term = $2,
                    replacement = $3,
                    severity = $4,
                    enabled = $5,
                    notes = $6,
                    updated_at = NOW()
                WHERE id = $1
                RETURNING id, term, replacement, severity, source, enabled, notes,
                          created_at, updated_at
                """,
                term_id,
                next_term,
                next_replacement,
                next_severity,
                next_enabled,
                next_notes,
            )
        except asyncpg.UniqueViolationError:
            raise DuplicateError(
                "A blocklist term with this value already exists.",
                details={"term": next_term},
            )
        if row is None:
            raise NotFoundError("Blocklist term not found.", details={"id": str(term_id)})
        return self._row_to_dict(row)

    async def delete(self, term_id: UUID) -> bool:
        result = await self._pool.execute(
            "DELETE FROM suno_blocklist_terms WHERE id = $1",
            term_id,
        )
        return "DELETE 1" in result

    async def upsert_learned(
        self,
        *,
        term: str,
        replacement: str | None,
        severity: str = "block",
        enabled: bool = True,
        notes: str | None = None,
    ) -> dict[str, Any]:
        row = await self._pool.fetchrow(
            """
            INSERT INTO suno_blocklist_terms (
                id, term, replacement, severity, source, enabled, notes,
                created_at, updated_at
            )
            VALUES (gen_random_uuid(), $1, $2, $3, 'learned', $4, $5, NOW(), NOW())
            ON CONFLICT ((LOWER(term)))
            DO UPDATE SET
                replacement = COALESCE(EXCLUDED.replacement, suno_blocklist_terms.replacement),
                severity = EXCLUDED.severity,
                source = 'learned',
                enabled = EXCLUDED.enabled,
                notes = COALESCE(EXCLUDED.notes, suno_blocklist_terms.notes),
                updated_at = NOW()
            RETURNING id, term, replacement, severity, source, enabled, notes,
                      created_at, updated_at
            """,
            term,
            replacement,
            severity,
            enabled,
            notes,
        )
        return self._row_to_dict(row)
