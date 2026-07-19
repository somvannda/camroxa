from __future__ import annotations

import io
import zipfile

import pytest

from platform_api.exceptions import ValidationError
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


@pytest.mark.asyncio
async def test_import_pack_from_url_downloads_and_extracts(tmp_path, monkeypatch) -> None:
    repo = _FakeRepo()
    service = ImageSamplePackService(storage_root=str(tmp_path), repo=repo)
    zip_bytes = _zip_with_images()

    async def _fake_download(source_type: str, source_value: str) -> bytes:
        assert source_type == "url"
        assert source_value == "https://example.com/pack.zip"
        return zip_bytes

    monkeypatch.setattr(
        "platform_api.services.image_sample_pack_service.download_zip_from_url",
        _fake_download,
    )

    record = await service.import_pack_from_url(
        category="thumbnail",
        name="Remote Pack",
        source_type="url",
        source_value="https://example.com/pack.zip",
    )
    assert record.asset_count == 2
    assert record.source_type == "url"
    assert record.source_value == "https://example.com/pack.zip"
    assert len(repo.assets) == 2


@pytest.mark.asyncio
async def test_import_pack_from_google_drive_folder_rejected(tmp_path) -> None:
    repo = _FakeRepo()
    service = ImageSamplePackService(storage_root=str(tmp_path), repo=repo)

    with pytest.raises(ValidationError, match="folder links are not supported"):
        await service.import_pack_from_url(
            category="background",
            name="Folder Pack",
            source_type="google_drive",
            source_value="https://drive.google.com/drive/folders/abc123XYZ",
        )


def test_get_url_import_max_bytes_uses_settings(monkeypatch) -> None:
    from platform_api.config import Settings
    from platform_api.services import sample_pack_downloader

    monkeypatch.setattr(
        sample_pack_downloader,
        "get_settings",
        lambda: Settings(sample_pack_url_import_max_mb=512),
    )
    assert sample_pack_downloader.get_url_import_max_bytes() == 512 * 1024 * 1024

