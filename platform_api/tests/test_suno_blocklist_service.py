"""Tests for Suno blocklist service."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from platform_api.exceptions import DuplicateError, ValidationError
from platform_api.services.suno_blocklist_service import SunoBlocklistService


class FakeSunoBlocklistRepo:
    def __init__(self) -> None:
        now = datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc)
        self.rows: dict[UUID, dict] = {
            UUID("00000000-0000-0000-0000-000000000101"): {
                "id": UUID("00000000-0000-0000-0000-000000000101"),
                "term": "lowlight",
                "replacement": "afterglow",
                "severity": "block",
                "source": "manual",
                "enabled": True,
                "notes": None,
                "created_at": now,
                "updated_at": now,
            }
        }

    async def list_all(self) -> list[dict]:
        return list(self.rows.values())

    async def get_by_id(self, term_id: UUID) -> dict | None:
        return self.rows.get(term_id)

    async def get_enabled_terms(self, *, channel_profile_id: UUID | None = None) -> list[dict]:
        del channel_profile_id
        return [row for row in self.rows.values() if row["enabled"]]

    async def create(
        self,
        *,
        term: str,
        replacement: str | None,
        severity: str,
        source: str = "manual",
        enabled: bool = True,
        notes: str | None = None,
    ) -> dict:
        normalized = term.strip().lower()
        if any(str(row["term"]).lower() == normalized for row in self.rows.values()):
            raise DuplicateError("duplicate", details={"term": term})
        row_id = uuid4()
        now = datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc)
        row = {
            "id": row_id,
            "term": normalized,
            "replacement": replacement,
            "severity": severity,
            "source": source,
            "enabled": enabled,
            "notes": notes,
            "created_at": now,
            "updated_at": now,
        }
        self.rows[row_id] = row
        return row

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
    ) -> dict:
        existing = self.rows.get(term_id)
        if existing is None:
            from platform_api.exceptions import NotFoundError

            raise NotFoundError("missing", details={"id": str(term_id)})
        if term is not None:
            existing["term"] = term
        if clear_replacement:
            existing["replacement"] = None
        elif replacement is not None:
            existing["replacement"] = replacement
        if severity is not None:
            existing["severity"] = severity
        if enabled is not None:
            existing["enabled"] = enabled
        if notes is not None:
            existing["notes"] = notes
        return existing

    async def delete(self, term_id: UUID) -> bool:
        return self.rows.pop(term_id, None) is not None

    async def upsert_learned(
        self,
        *,
        term: str,
        replacement: str | None,
        severity: str = "block",
        enabled: bool = True,
        notes: str | None = None,
    ) -> dict:
        normalized = term.strip().lower()
        for row in self.rows.values():
            if str(row["term"]).lower() == normalized:
                row["replacement"] = replacement or row.get("replacement")
                row["severity"] = severity
                row["source"] = "learned"
                row["enabled"] = enabled
                if notes is not None:
                    row["notes"] = notes
                return row
        return await self.create(
            term=normalized,
            replacement=replacement,
            severity=severity,
            source="learned",
            enabled=enabled,
            notes=notes,
        )


@pytest.mark.asyncio
async def test_create_term_normalizes_lowercase() -> None:
    service = SunoBlocklistService(FakeSunoBlocklistRepo())
    row = await service.create_term(term=" SkyLine ", replacement="horizon")
    assert row["term"] == "skyline"
    assert row["replacement"] == "horizon"


@pytest.mark.asyncio
async def test_create_term_rejects_empty_term() -> None:
    service = SunoBlocklistService(FakeSunoBlocklistRepo())
    with pytest.raises(ValidationError):
        await service.create_term(term="   ")


@pytest.mark.asyncio
async def test_get_runtime_config_merges_enabled_terms() -> None:
    repo = FakeSunoBlocklistRepo()
    service = SunoBlocklistService(repo)
    await service.create_term(term="skyline", replacement="horizon", severity="block")
    await service.create_term(term="echo", replacement=None, severity="warn", enabled=True)

    config = await service.get_runtime_config(force_refresh=True)
    assert config.replacements["lowlight"] == "afterglow"
    assert config.replacements["skyline"] == "horizon"
    assert "skyline" in config.block_terms
    assert "echo" in config.warn_terms


@pytest.mark.asyncio
async def test_runtime_config_cache_is_reused() -> None:
    repo = FakeSunoBlocklistRepo()
    service = SunoBlocklistService(repo)
    first = await service.get_runtime_config()
    second = await service.get_runtime_config()
    assert first is second


@pytest.mark.asyncio
async def test_promote_learned_term_upserts() -> None:
    repo = FakeSunoBlocklistRepo()
    service = SunoBlocklistService(repo)
    row = await service.promote_learned_term(term="vendor", replacement="maker")
    assert row["source"] == "learned"
    assert row["term"] == "vendor"

    updated = await service.promote_learned_term(term="vendor", replacement="creator")
    assert updated["replacement"] == "creator"
