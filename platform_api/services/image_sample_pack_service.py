"""Admin ZIP upload and VPS extraction for image sample packs."""

from __future__ import annotations

import io
import re
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from platform_api.exceptions import ValidationError
from platform_api.services.sample_pack_downloader import (
    download_zip_from_url,
    get_url_import_max_bytes,
)

_SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
_MAX_ZIP_BYTES = 10 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class ExtractedSampleAsset:
    relative_path: str
    file_name: str
    absolute_path: str
    sort_order: int


def _normalize_zip_member(name: str) -> str:
    cleaned = str(name or "").replace("\\", "/").strip().lstrip("/")
    parts = [part for part in cleaned.split("/") if part and part not in {".", ".."}]
    return "/".join(parts)


class ImageSamplePackService:
    """Extract sample-pack ZIP archives onto VPS disk and persist asset rows."""

    def __init__(self, *, storage_root: str, repo: Any) -> None:
        self._storage_root = Path(str(storage_root or "./sample_pack_storage")).expanduser()
        self._repo = repo
        self._storage_root.mkdir(parents=True, exist_ok=True)

    def validate_zip_bytes(self, file_content: bytes, *, max_bytes: int = _MAX_ZIP_BYTES) -> None:
        if not file_content:
            raise ValidationError("ZIP file is empty.", details={"field": "file"})
        if len(file_content) > max_bytes:
            limit_mb = max_bytes // (1024 * 1024)
            raise ValidationError(
                f"ZIP file exceeds {limit_mb} MB limit.",
                details={"field": "file", "max_bytes": max_bytes},
            )
        try:
            with zipfile.ZipFile(io.BytesIO(file_content)) as zf:
                if zf.testzip() is not None:
                    raise ValidationError("ZIP archive is corrupt.", details={"field": "file"})
        except zipfile.BadZipFile as exc:
            raise ValidationError(
                "Invalid ZIP archive.",
                details={"field": "file", "reason": "bad_zip_file"},
            ) from exc

    def extract_assets_from_zip(
        self,
        file_content: bytes,
        *,
        destination: Path,
        max_bytes: int = _MAX_ZIP_BYTES,
    ) -> list[ExtractedSampleAsset]:
        self.validate_zip_bytes(file_content, max_bytes=max_bytes)
        if destination.exists():
            shutil.rmtree(destination)
        destination.mkdir(parents=True, exist_ok=True)

        assets: list[ExtractedSampleAsset] = []
        with zipfile.ZipFile(io.BytesIO(file_content)) as zf:
            for index, info in enumerate(zf.infolist()):
                if info.is_dir():
                    continue
                member = _normalize_zip_member(info.filename)
                if not member:
                    continue
                suffix = Path(member).suffix.lower()
                if suffix not in _SUPPORTED_EXTENSIONS:
                    continue
                target = destination / member
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(zf.read(info))
                assets.append(
                    ExtractedSampleAsset(
                        relative_path=member,
                        file_name=Path(member).name,
                        absolute_path=str(target.resolve()),
                        sort_order=index,
                    )
                )

        if not assets:
            shutil.rmtree(destination, ignore_errors=True)
            raise ValidationError(
                "ZIP contains no supported images (.png, .jpg, .jpeg, .webp).",
                details={"field": "file"},
            )
        return assets

    async def download_zip_from_url(self, source_type: str, source_value: str) -> bytes:
        return await download_zip_from_url(source_type, source_value)

    async def _persist_pack_zip(
        self,
        *,
        category: str,
        name: str,
        file_content: bytes,
        source_type: str,
        source_value: str,
        is_active: bool = True,
        sort_order: int = 0,
        version_label: str | None = None,
        notes: str | None = None,
        pack_id: str | None = None,
        max_zip_bytes: int = _MAX_ZIP_BYTES,
    ) -> Any:
        normalized_category = str(category or "").strip().lower()
        if normalized_category not in {"background", "thumbnail"}:
            raise ValidationError(
                "category must be background or thumbnail.",
                details={"field": "category"},
            )
        normalized_name = re.sub(r"\s+", " ", str(name or "").strip())
        if not normalized_name:
            raise ValidationError("name is required.", details={"field": "name"})

        pack_uuid = UUID(str(pack_id)) if pack_id else uuid4()
        destination = self._storage_root / normalized_category / str(pack_uuid)
        self.validate_zip_bytes(file_content, max_bytes=max_zip_bytes)
        assets = self.extract_assets_from_zip(
            file_content,
            destination=destination,
            max_bytes=max_zip_bytes,
        )

        if pack_id:
            existing = await self._repo.get_by_id(str(pack_uuid))
            if existing is None:
                shutil.rmtree(destination, ignore_errors=True)
                raise ValidationError("Sample pack not found.", details={"pack_id": pack_id})
            await self._repo.delete_assets_for_pack(str(pack_uuid))
            record = await self._repo.update(
                str(pack_uuid),
                category=normalized_category,
                name=normalized_name,
                source_type=source_type,
                source_value=source_value,
                is_active=is_active,
                sort_order=sort_order,
                version_label=version_label,
                notes=notes,
                storage_path=str(destination),
                asset_count=len(assets),
            )
        else:
            record = await self._repo.create(
                pack_id=str(pack_uuid),
                category=normalized_category,
                name=normalized_name,
                source_type=source_type,
                source_value=source_value,
                is_active=is_active,
                sort_order=sort_order,
                version_label=version_label,
                notes=notes,
                storage_path=str(destination),
                asset_count=len(assets),
            )

        if record is None:
            shutil.rmtree(destination, ignore_errors=True)
            raise ValidationError("Unable to persist sample pack record.")

        await self._repo.insert_assets(
            str(pack_uuid),
            [
                {
                    "relative_path": asset.relative_path,
                    "file_name": asset.file_name,
                    "absolute_path": asset.absolute_path,
                    "sort_order": asset.sort_order,
                }
                for asset in assets
            ],
        )
        return record

    async def upload_pack_zip(
        self,
        *,
        category: str,
        name: str,
        file_content: bytes,
        is_active: bool = True,
        sort_order: int = 0,
        version_label: str | None = None,
        notes: str | None = None,
        pack_id: str | None = None,
    ) -> Any:
        pack_uuid = UUID(str(pack_id)) if pack_id else uuid4()
        destination = self._storage_root / str(category or "").strip().lower() / str(pack_uuid)
        return await self._persist_pack_zip(
            category=category,
            name=name,
            file_content=file_content,
            source_type="vps_upload",
            source_value=str(destination),
            is_active=is_active,
            sort_order=sort_order,
            version_label=version_label,
            notes=notes,
            pack_id=pack_id,
            max_zip_bytes=_MAX_ZIP_BYTES,
        )

    async def import_pack_from_url(
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
    ) -> Any:
        file_content = await self.download_zip_from_url(source_type, source_value)
        normalized_source = str(source_type or "").strip().lower()
        return await self._persist_pack_zip(
            category=category,
            name=name,
            file_content=file_content,
            source_type=normalized_source,
            source_value=str(source_value or "").strip(),
            is_active=is_active,
            sort_order=sort_order,
            version_label=version_label,
            notes=notes,
            pack_id=pack_id,
            max_zip_bytes=get_url_import_max_bytes(),
        )
