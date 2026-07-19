"""Tests for additive model cost seeding behavior."""

from __future__ import annotations

from typing import Any

import pytest

from platform_api.services.model_cost_service import ModelCostService


class _FakeModelCostRepo:
    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.rows = list(rows or [])
        self.deleted: list[tuple[str, str, str]] = []

    async def get_all(self) -> list[dict[str, Any]]:
        return list(self.rows)

    async def create(self, **kwargs: Any) -> dict[str, Any]:
        row = {"id": "new", **kwargs}
        self.rows.append(row)
        return row

    async def update(self, **kwargs: Any) -> dict[str, Any]:
        return {"id": "updated", **kwargs}

    async def delete(
        self, *, ai_service: str, sub_model: str, operation_type: str
    ) -> bool:
        self.deleted.append((ai_service, sub_model, operation_type))
        return True

    async def upsert(self, **kwargs: Any) -> dict[str, Any]:
        key = (kwargs["ai_service"], kwargs["sub_model"], kwargs["operation_type"])
        self.rows = [
            row
            for row in self.rows
            if (
                row["ai_service"],
                row.get("sub_model") or "",
                row["operation_type"],
            )
            != key
        ]
        row = {"id": "upserted", **kwargs}
        self.rows.append(row)
        return row


@pytest.mark.asyncio
async def test_seed_from_registry_prunes_stale_registry_rows_without_overwrite() -> None:
    repo = _FakeModelCostRepo(
        [
            {
                "ai_service": "slai",
                "sub_model": "removed-model",
                "operation_type": "lyric",
                "source": "registry",
            }
        ]
    )
    service = ModelCostService(repo=repo)

    await service.seed_from_registry(overwrite=False)

    assert repo.deleted == [("slai", "removed-model", "lyric")]


@pytest.mark.asyncio
async def test_seed_from_registry_prunes_stale_rows_with_overwrite() -> None:
    repo = _FakeModelCostRepo(
        [
            {
                "ai_service": "slai",
                "sub_model": "removed-model",
                "operation_type": "lyric",
                "source": "registry",
            }
        ]
    )
    service = ModelCostService(repo=repo)

    await service.seed_from_registry(overwrite=True)

    assert repo.deleted == [("slai", "removed-model", "lyric")]
