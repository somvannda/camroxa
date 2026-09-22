"""Tests for curated music genre catalog."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from platform_api.services.music_genre_catalog_service import MusicGenreCatalogService


@pytest.mark.asyncio
async def test_resolve_genre_names_maps_aliases() -> None:
    repo = AsyncMock()
    repo.fetch_all_active = AsyncMock(
        return_value=[
            {"name": "Eurodance", "aliases": []},
            {"name": "Hip Hop", "aliases": ["Hip-Hop"]},
        ]
    )
    service = MusicGenreCatalogService(AsyncMock())
    service._repo = repo
    resolved = await service.resolve_genre_names(["hip-hop", "Eurodance"])
    assert resolved == ["Hip Hop", "Eurodance"]


@pytest.mark.asyncio
async def test_resolve_genre_names_rejects_unknown() -> None:
    repo = AsyncMock()
    repo.fetch_all_active = AsyncMock(return_value=[{"name": "Pop", "aliases": []}])
    service = MusicGenreCatalogService(AsyncMock())
    service._repo = repo
    with pytest.raises(ValueError, match="Unknown genre"):
        await service.resolve_genre_names(["Not A Real Genre"])
