from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from platform_api.models.domain import ImageJob
from platform_api.models.enums import ChannelRole, ImageKind, TaskStatus
from platform_api.repositories.image_sample_repo import ImageSampleRepository
from platform_api.services.image_sample_rotation import ImageSampleRotationService


@pytest.mark.asyncio
async def test_pick_least_used_value_rotates_samples() -> None:
    pool = AsyncMock()
    pool.fetch = AsyncMock(
        side_effect=[
            [{"value": "a.png", "used_count": 2, "used_at": None}],
            [],
        ]
    )
    pool.execute = AsyncMock()
    repo = ImageSampleRepository(pool=pool)

    first = await repo.pick_least_used_value(kind="bg_sample", values=["a.png", "b.png"])
    second = await repo.pick_least_used_value(kind="bg_sample", values=["a.png", "b.png"])

    assert first == "b.png"
    assert second == "b.png"
    assert pool.execute.await_count == 2


def test_build_candidates_prefers_selected_when_not_random(tmp_path) -> None:
    selected = tmp_path / "selected.png"
    selected.write_bytes(b"x")
    settings = {
        "imageBgSamples": [str(selected)],
        "imageBackgroundSamplesDir": str(tmp_path / "folder"),
        "imageBgRandom": False,
    }
    candidates = ImageSampleRotationService.build_candidates(settings, ImageKind.BACKGROUND)
    assert candidates == [str(selected)]


def test_build_candidates_uses_selected_subset_when_random(tmp_path) -> None:
    selected = tmp_path / "selected.png"
    selected.write_bytes(b"x")
    other = tmp_path / "other.png"
    other.write_bytes(b"y")
    settings = {
        "imageBgSamples": [str(selected)],
        "imageBackgroundSamplesDir": str(tmp_path),
        "imageBgRandom": True,
    }
    candidates = ImageSampleRotationService.build_candidates(settings, ImageKind.BACKGROUND)
    assert candidates == [str(selected)]


@pytest.mark.asyncio
async def test_pick_sample_path_prefers_vps_assets(tmp_path) -> None:
    vps_file = tmp_path / "vps.png"
    vps_file.write_bytes(b"x")
    pack_repo = AsyncMock()
    pack_repo.list_vps_asset_paths = AsyncMock(return_value=[str(vps_file)])
    sample_repo = AsyncMock()
    sample_repo.pick_least_used_value = AsyncMock(return_value=str(vps_file))
    service = ImageSampleRotationService(repo=sample_repo, pack_repo=pack_repo)
    chosen = await service.pick_sample_path(
        settings={"imageBgSamples": ["/missing/local.png"]},
        kind=ImageKind.BACKGROUND,
    )
    assert chosen == str(vps_file)


@pytest.mark.asyncio
async def test_pick_sample_path_does_not_fall_back_to_local_settings(tmp_path) -> None:
    local = tmp_path / "local.png"
    local.write_bytes(b"x")
    pack_repo = AsyncMock()
    pack_repo.list_vps_asset_paths = AsyncMock(return_value=[])
    sample_repo = AsyncMock()
    service = ImageSampleRotationService(repo=sample_repo, pack_repo=pack_repo)
    chosen = await service.pick_sample_path(
        settings={
            "imageBgSamples": [str(local)],
            "imageBackgroundSamplesDir": str(tmp_path),
        },
        kind=ImageKind.BACKGROUND,
    )
    assert chosen is None
    sample_repo.pick_least_used_value.assert_not_awaited()


def test_build_candidates_uses_folder_when_random_and_nothing_selected() -> None:
    settings = {
        "imageBgSamples": ["/tmp/selected.png"],
        "imageBackgroundSamplesDir": "/tmp/folder",
        "imageBgRandom": True,
    }
    candidates = ImageSampleRotationService.build_candidates(settings, ImageKind.BACKGROUND)
    assert candidates == []
