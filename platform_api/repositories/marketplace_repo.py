"""Marketplace repository for template marketplace item CRUD operations.

Provides paginated listing, search (case-insensitive partial match on name,
description, and tags), filtering by kind, and standard CRUD operations.

Requirements: 1.1, 1.8, 2.1, 2.2, 2.3, 2.4, 3.1, 3.2, 3.3, 3.5
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Domain record
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class MarketplaceItemRecord:
    """A marketplace template item record."""

    id: UUID
    name: str
    description: str
    version: str
    author: str
    kind: str
    tags: list[str]
    status: str
    zip_path: str
    preview_path: str
    created_at: datetime
    updated_at: datetime
    price: float = 0.0


# ---------------------------------------------------------------------------
# Database Protocol
# ---------------------------------------------------------------------------


class AsyncPGPool(Protocol):
    """Minimal async database interface for marketplace operations."""

    async def fetchrow(self, query: str, *args: Any) -> Any: ...
    async def fetch(self, query: str, *args: Any) -> list[Any]: ...
    async def execute(self, query: str, *args: Any) -> str: ...
    async def fetchval(self, query: str, *args: Any) -> Any: ...


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------

_SELECT_COLS = (
    "id, name, description, version, author, kind, tags, status, "
    "zip_path, preview_path, price, created_at, updated_at"
)


class MarketplaceRepository:
    """Repository for marketplace_items table CRUD operations.

    Implements the MarketplaceRepositoryPort protocol defined in the design:
      - create
      - get_by_id
      - find_by_name_version
      - list_all (paginated, for admin)
      - list_enabled (paginated, filterable by kind and search, for public catalog)
      - update
      - delete
    """

    def __init__(self, pool: AsyncPGPool) -> None:
        self._pool = pool

    async def create(self, item: MarketplaceItemRecord) -> MarketplaceItemRecord:
        """Insert a new marketplace item and return the created record."""
        row = await self._pool.fetchrow(
            f"""
            INSERT INTO marketplace_items (
                id, name, description, version, author, kind, tags, status,
                zip_path, preview_path, price, created_at, updated_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, NOW(), NOW())
            RETURNING {_SELECT_COLS}
            """,
            item.id,
            item.name,
            item.description,
            item.version,
            item.author,
            item.kind,
            item.tags,
            item.status,
            item.zip_path,
            item.preview_path,
            item.price,
        )
        return _row_to_record(row)

    async def get_by_id(self, item_id: UUID) -> MarketplaceItemRecord | None:
        """Retrieve a marketplace item by its UUID."""
        row = await self._pool.fetchrow(
            f"SELECT {_SELECT_COLS} FROM marketplace_items WHERE id = $1",
            item_id,
        )
        return _row_to_record(row) if row else None

    async def find_by_name_version(
        self, name: str, version: str
    ) -> MarketplaceItemRecord | None:
        """Find a marketplace item by its unique (name, version) pair."""
        row = await self._pool.fetchrow(
            f"SELECT {_SELECT_COLS} FROM marketplace_items WHERE name = $1 AND version = $2",
            name,
            version,
        )
        return _row_to_record(row) if row else None

    async def list_all(
        self, *, offset: int, limit: int
    ) -> tuple[list[MarketplaceItemRecord], int]:
        """List all marketplace items (admin view) with pagination.

        Returns a tuple of (items, total_count).
        Ordered by created_at DESC.
        """
        total: int = await self._pool.fetchval(
            "SELECT COUNT(*) FROM marketplace_items"
        ) or 0

        rows = await self._pool.fetch(
            f"""
            SELECT {_SELECT_COLS}
            FROM marketplace_items
            ORDER BY created_at DESC
            LIMIT $1 OFFSET $2
            """,
            limit,
            offset,
        )
        items = [_row_to_record(row) for row in rows]
        return items, total

    async def list_enabled(
        self,
        *,
        offset: int,
        limit: int,
        kind: str | None = None,
        search: str | None = None,
    ) -> tuple[list[MarketplaceItemRecord], int]:
        """List enabled marketplace items (public catalog) with pagination.

        Supports optional filtering by kind and case-insensitive search
        across name, description, and tags array elements.

        Returns a tuple of (items, total_count).
        Ordered by created_at DESC.
        """
        conditions: list[str] = ["status = 'enabled'"]
        params: list[Any] = []
        param_idx = 0

        if kind is not None:
            param_idx += 1
            conditions.append(f"kind = ${param_idx}")
            params.append(kind)

        if search is not None:
            param_idx += 1
            search_param = f"${param_idx}"
            search_condition = (
                f"("
                f"name ILIKE '%' || {search_param} || '%' OR "
                f"description ILIKE '%' || {search_param} || '%' OR "
                f"EXISTS (SELECT 1 FROM unnest(tags) AS tag WHERE tag ILIKE '%' || {search_param} || '%')"
                f")"
            )
            conditions.append(search_condition)
            params.append(search)

        where_clause = "WHERE " + " AND ".join(conditions)

        # Count total matching entries
        count_query = f"SELECT COUNT(*) FROM marketplace_items {where_clause}"
        total: int = await self._pool.fetchval(count_query, *params) or 0

        # Fetch page
        param_idx += 1
        limit_param = f"${param_idx}"
        param_idx += 1
        offset_param = f"${param_idx}"

        select_query = f"""
            SELECT {_SELECT_COLS}
            FROM marketplace_items
            {where_clause}
            ORDER BY created_at DESC
            LIMIT {limit_param} OFFSET {offset_param}
        """
        rows = await self._pool.fetch(select_query, *params, limit, offset)
        items = [_row_to_record(row) for row in rows]
        return items, total

    async def update(
        self, item_id: UUID, fields: dict[str, Any]
    ) -> MarketplaceItemRecord | None:
        """Update specific fields of a marketplace item.

        Only non-None fields in the dict are applied. The updated_at
        timestamp is always set to NOW().

        Returns the updated record or None if the item was not found.
        """
        if not fields:
            return await self.get_by_id(item_id)

        set_parts: list[str] = []
        values: list[Any] = []
        idx = 0

        for key, val in fields.items():
            idx += 1
            set_parts.append(f"{key} = ${idx}")
            values.append(val)

        # Always update updated_at
        set_parts.append("updated_at = NOW()")

        # Add item_id as last parameter
        idx += 1
        id_param = f"${idx}"

        query = f"""
            UPDATE marketplace_items
            SET {', '.join(set_parts)}
            WHERE id = {id_param}
            RETURNING {_SELECT_COLS}
        """
        values.append(item_id)

        row = await self._pool.fetchrow(query, *values)
        return _row_to_record(row) if row else None

    async def delete(self, item_id: UUID) -> bool:
        """Delete a marketplace item by its UUID.

        Returns True if a row was deleted, False otherwise.
        """
        result = await self._pool.execute(
            "DELETE FROM marketplace_items WHERE id = $1",
            item_id,
        )
        # asyncpg returns "DELETE N" where N is the number of deleted rows
        return result.endswith("1")


# ---------------------------------------------------------------------------
# Row mapping helper
# ---------------------------------------------------------------------------


def _row_to_record(row: Any) -> MarketplaceItemRecord:
    """Convert a database row to a MarketplaceItemRecord dataclass."""
    return MarketplaceItemRecord(
        id=row["id"] if isinstance(row["id"], UUID) else UUID(str(row["id"])),
        name=row["name"],
        description=row["description"],
        version=row["version"],
        author=row["author"],
        kind=row["kind"],
        tags=list(row["tags"]) if row["tags"] else [],
        status=row["status"],
        zip_path=row["zip_path"],
        preview_path=row["preview_path"],
        price=float(row["price"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
