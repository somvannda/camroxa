from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import pytest
from fastapi import HTTPException

from platform_api.middleware.auth import AuthContext
from platform_api.routers import admin_content_pools


class FakeAdminContentPoolDb:
    def __init__(self) -> None:
        self.deleted: list[tuple[str, int]] = []
        self.truncated: list[str] = []
        self.deleted_preset_packs: list[tuple[str, UUID]] = []
        self.preset_pack_id = UUID("00000000-0000-0000-0000-000000000111")
        self.preset_packs = [
            {
                "id": self.preset_pack_id,
                "kind": "titles",
                "name": "Synthwave Nights",
                "description": "Title pack for neon synth releases",
                "config": {"include_defaults": True, "adjectives": ["synthwave"], "nouns": ["boulevard"]},
                "is_active": True,
                "created_at": datetime(2026, 6, 27, 11, 0, tzinfo=timezone.utc),
                "updated_at": datetime(2026, 6, 27, 11, 30, tzinfo=timezone.utc),
            }
        ]

    async def fetchrow(self, query: str, *args):
        if "COUNT(*)::int AS total" in query and "title_pool" in query:
            return {"total": 120, "unused": 75, "reserved": 6, "stale_reserved": 2, "available": 114}
        if "COUNT(*)::int AS total" in query and "album_pool" in query:
            return {"total": 80, "unused": 33, "reserved": 3, "stale_reserved": 1, "available": 77}
        if "COUNT(*)::int AS total" in query and "opening_pairs" in query:
            return {"total": 64, "unused": 28, "reserved": 5, "stale_reserved": 1, "available": 59}
        if "SELECT id, kind, name, description, config, is_active, created_at, updated_at" in query:
            for pack in self.preset_packs:
                if pack["kind"] == args[0] and pack["id"] == args[1]:
                    return pack
            return None
        if "INSERT INTO content_pool_preset_packs" in query:
            if args[2] == "duplicate":
                raise Exception("duplicate key value violates unique constraint")
            row = {
                "id": UUID("00000000-0000-0000-0000-000000000222"),
                "kind": args[0],
                "name": args[1],
                "description": args[3],
                "config": args[4],
                "is_active": args[5],
                "created_at": datetime(2026, 6, 27, 12, 0, tzinfo=timezone.utc),
                "updated_at": datetime(2026, 6, 27, 12, 0, tzinfo=timezone.utc),
            }
            self.preset_packs.append(row)
            return row
        if "UPDATE content_pool_preset_packs" in query:
            if args[3] == "duplicate":
                raise Exception("duplicate key value violates unique constraint")
            for index, pack in enumerate(self.preset_packs):
                if pack["kind"] == args[0] and pack["id"] == args[1]:
                    updated = {
                        **pack,
                        "name": args[2],
                        "description": args[4],
                        "config": args[5],
                        "is_active": args[6],
                        "updated_at": datetime(2026, 6, 27, 13, 0, tzinfo=timezone.utc),
                    }
                    self.preset_packs[index] = updated
                    return updated
            return None
        if "UPDATE title_pool" in query:
            if args[1] == "Duplicate":
                raise Exception("duplicate key value violates unique constraint")
            return {
                "id": args[0],
                "text": args[1],
                "used_count": 5,
                "created_at": datetime(2026, 6, 27, 10, 0, tzinfo=timezone.utc),
            }
        return None

    async def fetchval(self, query: str, *args):
        if "title_pool" in query:
            return 120
        if "album_pool" in query:
            return 80
        if "opening_pairs" in query:
            return 64
        return 0

    async def fetch(self, query: str, *args):
        if "FROM content_pool_preset_packs" in query:
            return [pack for pack in self.preset_packs if pack["kind"] == args[0]]
        if "FROM title_pool" in query:
            return [
                {
                    "id": 8,
                    "text": "Midnight Echo",
                    "used_count": 5,
                    "reservation_token": "claim-xyz",
                    "reserved_by": "batch-12:item-4",
                    "reserved_at": datetime(2026, 6, 28, 11, 0, tzinfo=timezone.utc),
                    "is_stale_reservation": False,
                    "created_at": datetime(2026, 6, 27, 10, 0, tzinfo=timezone.utc),
                }
            ]
        return []

    async def execute(self, query: str, *args):
        if query.startswith("DELETE FROM content_pool_preset_packs"):
            self.deleted_preset_packs.append((args[0], args[1]))
            for index, pack in enumerate(self.preset_packs):
                if pack["kind"] == args[0] and pack["id"] == args[1]:
                    self.preset_packs.pop(index)
                    return "DELETE 1"
            return "DELETE 0"
        if query.startswith("DELETE FROM"):
            self.deleted.append((query, args[0]))
            return "DELETE 1" if args[0] == 8 else "DELETE 0"
        if query.startswith("TRUNCATE TABLE"):
            self.truncated.append(query)
            return "TRUNCATE TABLE"
        return "OK"


def _admin_ctx() -> AuthContext:
    return AuthContext(
        user_id="00000000-0000-0000-0000-000000000001",
        email="boss@example.com",
        role="admin",
    )


@pytest.mark.asyncio
async def test_admin_content_pool_stats_and_list(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(admin_content_pools, "get_db_pool", lambda: FakeAdminContentPoolDb())

    stats = await admin_content_pools.get_admin_content_pool_stats(_admin_ctx())
    listing = await admin_content_pools.list_admin_content_pool_items("titles", _admin_ctx(), limit=100, offset=0)

    assert stats.titles.total == 120
    assert stats.titles.reserved == 6
    assert stats.titles.stale_reserved == 2
    assert stats.openings.unused == 28
    assert listing.items[0].text == "Midnight Echo"
    assert listing.items[0].used_count == 5
    assert listing.items[0].reservation_state == "reserved"
    assert listing.items[0].reserved_by == "batch-12:item-4"


@pytest.mark.asyncio
async def test_admin_content_pool_generate_and_import_delegate_helpers(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    async def fake_generate(kind, count, preset_pack_id=None):
        captured["kind"] = kind
        captured["count"] = count
        captured["preset_pack_id"] = preset_pack_id
        return admin_content_pools.GenerateContentPoolResponse(
            requested=count,
            attempted=58,
            inserted=42,
            duplicates_skipped=16,
        )

    async def fake_import(kind, text):
        return 12

    monkeypatch.setattr(admin_content_pools, "_generate_kind", fake_generate)
    monkeypatch.setattr(admin_content_pools, "_import_kind", fake_import)

    generated = await admin_content_pools.generate_content_pool_items(
        "titles",
        admin_content_pools.GenerateContentPoolRequest(
            count=1000,
            preset_pack_id="00000000-0000-0000-0000-000000000111",
        ),
        _admin_ctx(),
    )
    imported = await admin_content_pools.import_content_pool_items(
        "albums",
        admin_content_pools.ImportContentPoolRequest(text="One\nTwo"),
        _admin_ctx(),
    )

    assert generated.requested == 1000
    assert generated.attempted == 58
    assert generated.inserted == 42
    assert generated.duplicates_skipped == 16
    assert imported.inserted == 12
    assert captured == {
        "kind": "titles",
        "count": 1000,
        "preset_pack_id": "00000000-0000-0000-0000-000000000111",
    }


@pytest.mark.asyncio
async def test_generate_kind_reports_attempts_and_skipped_duplicates(monkeypatch: pytest.MonkeyPatch) -> None:
    generated_batches = iter(
        [
            ["Neon Echo", "Neon Echo", "Midnight Signal"],
            ["Midnight Signal", "Golden Dream", "Silver Horizon"],
        ]
    )
    inserted_per_round = iter([2, 1])
    seen_rows: list[list[tuple[str, ...]]] = []

    def fake_generate_title_candidates(count: int, config=None) -> list[str]:
        return next(generated_batches)

    async def fake_bulk_insert_rows(kind: str, rows: list[tuple[str, ...]]) -> int:
        seen_rows.append(rows)
        return next(inserted_per_round)

    monkeypatch.setattr(admin_content_pools, "_generate_title_candidates", fake_generate_title_candidates)
    monkeypatch.setattr(admin_content_pools, "_bulk_insert_rows", fake_bulk_insert_rows)

    result = await admin_content_pools._generate_kind("titles", 3)

    assert result.requested == 3
    assert result.attempted == 4
    assert result.inserted == 3
    assert result.duplicates_skipped == 1
    assert [row[0] for row in seen_rows[0]] == ["Neon Echo", "Midnight Signal"]
    assert [row[0] for row in seen_rows[1]] == ["Golden Dream", "Silver Horizon"]


@pytest.mark.asyncio
async def test_admin_content_pool_generate_preset_banks_returns_requested_sizes() -> None:
    titles = await admin_content_pools.generate_content_pool_preset_pack_banks(
        "titles",
        admin_content_pools.GeneratePresetPackBanksRequest(target_count=120),
        _admin_ctx(),
    )
    openings = await admin_content_pools.generate_content_pool_preset_pack_banks(
        "openings",
        admin_content_pools.GeneratePresetPackBanksRequest(target_count=120),
        _admin_ctx(),
    )

    assert titles.target_count == 120
    assert len(titles.banks.adjectives) == 120
    assert len(titles.banks.nouns) == 120
    assert len(titles.banks.verbs) == 120
    assert len(titles.banks.places) == 120
    assert len(titles.banks.feelings) == 120
    assert len(set(titles.banks.adjectives)) == 120
    assert len(openings.banks.whos) == 120
    assert len(openings.banks.moods) == 120
    assert len(openings.banks.times) == 120


@pytest.mark.asyncio
async def test_admin_content_pool_preset_pack_storage_missing_table_returns_actionable_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class MissingPresetPackTableDb:
        async def fetch(self, query: str, *args):
            raise RuntimeError('relation "content_pool_preset_packs" does not exist')

    monkeypatch.setattr(admin_content_pools, "get_db_pool", lambda: MissingPresetPackTableDb())

    with pytest.raises(HTTPException) as exc_info:
        await admin_content_pools.list_content_pool_preset_packs("titles", _admin_ctx())

    assert exc_info.value.status_code == 503
    assert "migration has not been applied" in str(exc_info.value.detail).lower()


@pytest.mark.asyncio
async def test_admin_content_pool_preset_pack_crud(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_db = FakeAdminContentPoolDb()
    monkeypatch.setattr(admin_content_pools, "get_db_pool", lambda: fake_db)

    listing = await admin_content_pools.list_content_pool_preset_packs("titles", _admin_ctx())
    created = await admin_content_pools.create_content_pool_preset_pack(
        "titles",
        admin_content_pools.CreateContentPoolPresetPackRequest(
            name="After Hours",
            description="Late-night title pack",
            is_active=True,
            config=admin_content_pools.ContentPoolPresetConfig(
                include_defaults=False,
                adjectives=["after-hours"],
                nouns=["skyline"],
            ),
        ),
        _admin_ctx(),
    )
    updated = await admin_content_pools.update_content_pool_preset_pack(
        "titles",
        str(fake_db.preset_pack_id),
        admin_content_pools.UpdateContentPoolPresetPackRequest(
            name="Synthwave Nights 2",
            description="Updated theme",
            is_active=False,
            config=admin_content_pools.ContentPoolPresetConfig(
                include_defaults=True,
                adjectives=["synthwave", "chrome"],
                nouns=["boulevard"],
            ),
        ),
        _admin_ctx(),
    )
    await admin_content_pools.delete_content_pool_preset_pack(
        "titles",
        str(fake_db.preset_pack_id),
        _admin_ctx(),
    )

    assert listing.items[0].name == "Synthwave Nights"
    assert created.name == "After Hours"
    assert created.config.include_defaults is False
    assert updated.name == "Synthwave Nights 2"
    assert updated.is_active is False
    assert fake_db.deleted_preset_packs


@pytest.mark.asyncio
async def test_admin_content_pool_update_delete_and_clear(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_db = FakeAdminContentPoolDb()
    monkeypatch.setattr(admin_content_pools, "get_db_pool", lambda: fake_db)

    updated = await admin_content_pools.update_content_pool_item(
        "titles",
        8,
        admin_content_pools.UpdateContentPoolItemRequest(text="New Title"),
        _admin_ctx(),
    )
    await admin_content_pools.delete_content_pool_item("titles", 8, _admin_ctx())
    cleared = await admin_content_pools.clear_content_pool("albums", _admin_ctx())

    assert updated.text == "New Title"
    assert fake_db.deleted
    assert fake_db.truncated
    assert cleared["ok"] is True

    with pytest.raises(HTTPException):
        await admin_content_pools.update_content_pool_item(
            "titles",
            8,
            admin_content_pools.UpdateContentPoolItemRequest(text="Duplicate"),
            _admin_ctx(),
        )
