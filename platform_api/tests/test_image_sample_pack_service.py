from __future__ import annotations

import io
import zipfile

import pytest

from platform_api.services.image_sample_pack_service import ImageSamplePackService


class _FakeRepo:
    def __init__(self) -> None:
        self.assets: list[dict] = []
        self.record = None

    async def create(self, **kwargs):
        from platform_api.repositories.image_sample_pack_repo import ImageSamplePackRecord

        self.record = ImageSamplePackRecord(
            id=kwargs.get("pack_id") or "pack-1",
            category=kwargs["category"],
            name=kwargs["name"],
            source_type=kwargs["source_type"],
            source_value=kwargs["source_value"],
            is_active=kwargs.get("is_active", True),
            sort_order=kwargs.get("sort_order", 0),
            storage_path=kwargs.get("storage_path"),
            asset_count=kwargs.get("asset_count", 0),
        )
        return self.record

    async def insert_assets(self, pack_id: str, assets: list[dict]) -> None:
        self.assets.extend(assets)

    async def delete_assets_for_pack(self, pack_id: str) -> None:
        self.assets.clear()

    async def get_by_id(self, pack_id: str):
        return self.record

    async def update(self, pack_id: str, **kwargs):
        return self.record


def _zip_with_images() -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as zf:
        zf.writestr("one.png", b"png")
        zf.writestr("folder/two.jpg", b"jpg")
    return out.getvalue()


@pytest.mark.asyncio
async def test_upload_pack_zip_extracts_supported_images(tmp_path) -> None:
    repo = _FakeRepo()
    service = ImageSamplePackService(storage_root=str(tmp_path), repo=repo)
    record = await service.upload_pack_zip(
        category="background",
        name="Gym Pack",
        file_content=_zip_with_images(),
    )
    assert record.asset_count == 2
    assert len(repo.assets) == 2
    assert all(str(tmp_path) in asset["absolute_path"] for asset in repo.assets)
