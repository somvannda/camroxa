from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class ImageSamplePackRecord:
    id: str
    category: str
    name: str
    source_type: str
    source_value: str
    is_active: bool
    sort_order: int
    version_label: str | None = None
    notes: str | None = None
    storage_path: str | None = None
    asset_count: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None


class DatabaseProtocol(Protocol):
    async def fetch(self, query: str, *args: Any) -> list[dict[str, Any]]: ...

    async def fetchrow(self, query: str, *args: Any) -> dict[str, Any] | None: ...

    async def execute(self, query: str, *args: Any) -> str: ...


class ImageSamplePackRepository:
    def __init__(self, db: DatabaseProtocol) -> None:
        self._db = db

    async def list_for_user(self) -> list[ImageSamplePackRecord]:
        rows = await self._db.fetch(
            """
            SELECT id, category, name, source_type, source_value, is_active, sort_order,
                   version_label, notes, storage_path, asset_count, created_at, updated_at
            FROM image_sample_packs
            WHERE is_active = TRUE
            ORDER BY category ASC, sort_order ASC, lower(name) ASC, created_at ASC
            """
        )
        return [self._row_to_record(row) for row in rows]

    async def get_by_id(self, pack_id: str) -> ImageSamplePackRecord | None:
        row = await self._db.fetchrow(
            """
            SELECT id, category, name, source_type, source_value, is_active, sort_order,
                   version_label, notes, storage_path, asset_count, created_at, updated_at
            FROM image_sample_packs
            WHERE id = $1::uuid
            """,
            pack_id,
        )
        return self._row_to_record(row) if row else None

    async def list_all(self) -> list[ImageSamplePackRecord]:
        rows = await self._db.fetch(
            """
            SELECT id, category, name, source_type, source_value, is_active, sort_order,
                   version_label, notes, storage_path, asset_count, created_at, updated_at
            FROM image_sample_packs
            ORDER BY category ASC, sort_order ASC, lower(name) ASC, created_at ASC
            """
        )
        return [self._row_to_record(row) for row in rows]

    async def create(
        self,
        *,
        category: str,
        name: str,
        source_type: str,
        source_value: str,
        is_active: bool = True,
        sort_order: int = 0,
        version_label: str | None = None,
        notes: str | None = None,
        pack_id: str | None = None,
        storage_path: str | None = None,
        asset_count: int = 0,
    ) -> ImageSamplePackRecord | None:
        row = await self._db.fetchrow(
            """
            INSERT INTO image_sample_packs (
                id,
                category,
                name,
                source_type,
                source_value,
                is_active,
                sort_order,
                version_label,
                notes,
                storage_path,
                asset_count,
                created_at,
                updated_at
            )
            VALUES (
                COALESCE($1::uuid, gen_random_uuid()),
                $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, NOW(), NOW()
            )
            RETURNING id, category, name, source_type, source_value, is_active, sort_order,
                      version_label, notes, storage_path, asset_count, created_at, updated_at
            """,
            pack_id,
            category,
            name,
            source_type,
            source_value,
            is_active,
            sort_order,
            version_label,
            notes,
            storage_path,
            asset_count,
        )
        return self._row_to_record(row) if row else None

    async def update(
        self,
        pack_id: str,
        *,
        category: str | None = None,
        name: str | None = None,
        source_type: str | None = None,
        source_value: str | None = None,
        is_active: bool | None = None,
        sort_order: int | None = None,
        version_label: str | None = None,
        notes: str | None = None,
        storage_path: str | None = None,
        asset_count: int | None = None,
    ) -> ImageSamplePackRecord | None:
        row = await self._db.fetchrow(
            """
            UPDATE image_sample_packs
            SET category = COALESCE($2, category),
                name = COALESCE($3, name),
                source_type = COALESCE($4, source_type),
                source_value = COALESCE($5, source_value),
                is_active = COALESCE($6, is_active),
                sort_order = COALESCE($7, sort_order),
                version_label = COALESCE($8, version_label),
                notes = COALESCE($9, notes),
                storage_path = COALESCE($10, storage_path),
                asset_count = COALESCE($11, asset_count),
                updated_at = NOW()
            WHERE id = $1::uuid
            RETURNING id, category, name, source_type, source_value, is_active, sort_order,
                      version_label, notes, storage_path, asset_count, created_at, updated_at
            """,
            pack_id,
            category,
            name,
            source_type,
            source_value,
            is_active,
            sort_order,
            version_label,
            notes,
            storage_path,
            asset_count,
        )
        return self._row_to_record(row) if row else None

    async def delete_assets_for_pack(self, pack_id: str) -> None:
        await self._db.execute(
            "DELETE FROM image_sample_pack_assets WHERE pack_id = $1::uuid",
            pack_id,
        )

    async def insert_assets(self, pack_id: str, assets: list[dict[str, Any]]) -> None:
        for asset in assets:
            await self._db.execute(
                """
                INSERT INTO image_sample_pack_assets (
                    pack_id, relative_path, file_name, absolute_path, sort_order, created_at
                )
                VALUES ($1::uuid, $2, $3, $4, $5, NOW())
                """,
                pack_id,
                asset["relative_path"],
                asset["file_name"],
                asset["absolute_path"],
                int(asset.get("sort_order") or 0),
            )

    async def list_vps_asset_paths(self, *, category: str) -> list[str]:
        rows = await self._db.fetch(
            """
            SELECT a.absolute_path
            FROM image_sample_pack_assets a
            JOIN image_sample_packs p ON p.id = a.pack_id
            WHERE p.is_active = TRUE
              AND lower(p.category) = lower($1)
              AND p.asset_count > 0
            ORDER BY p.sort_order ASC, lower(p.name) ASC, a.sort_order ASC, a.file_name ASC
            """,
            category,
        )
        return [str(row["absolute_path"]) for row in rows if row.get("absolute_path")]

    async def delete(self, pack_id: str) -> bool:
        result = await self._db.execute(
            "DELETE FROM image_sample_packs WHERE id = $1::uuid",
            pack_id,
        )
        return result.upper().startswith("DELETE")

    @staticmethod
    def _row_to_record(row: dict[str, Any]) -> ImageSamplePackRecord:
        return ImageSamplePackRecord(
            id=str(row["id"]),
            category=str(row["category"]),
            name=str(row["name"]),
            source_type=str(row["source_type"]),
            source_value=str(row["source_value"]),
            is_active=bool(row["is_active"]),
            sort_order=int(row["sort_order"] or 0),
            version_label=row.get("version_label"),
            notes=row.get("notes"),
            storage_path=row.get("storage_path"),
            asset_count=int(row.get("asset_count") or 0),
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
        )
