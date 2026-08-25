"""Marketplace service for template bundle upload, catalog, and management.

Provides upload validation, catalog browsing (public, enabled-only),
admin item listing, metadata updates, enable/disable, deletion with
filesystem cleanup, and file path resolution for preview/download.

Requirements: 1.1–1.9, 2.1–2.7, 3.1–3.5, 4.1–4.5
"""

from __future__ import annotations

import io
import json
import logging
import os
import posixpath
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Generic, Protocol, TypeVar
from uuid import UUID, uuid4

from platform_api.exceptions import (
    DuplicateError,
    ForbiddenError,
    NotFoundError,
    PlatformAPIError,
    ValidationError,
)
from platform_api.repositories.marketplace_repo import (
    MarketplaceItemRecord,
    MarketplaceRepository,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_REQUIRED_ZIP_FILES = {"template.json", "preview.png", "manifest.json"}

_MAX_NAME_LENGTH = 200
_MAX_DESCRIPTION_LENGTH = 2000
_MAX_VERSION_LENGTH = 50
_MAX_AUTHOR_LENGTH = 200
_MAX_TAGS_COUNT = 20
_MAX_TAG_LENGTH = 50
_VALID_KINDS = {"video", "reel"}

DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PaginatedResult(Generic[T]):
    """A paginated result set."""

    items: list[T]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Custom exceptions for marketplace
# ---------------------------------------------------------------------------


class FileSizeExceededError(PlatformAPIError):
    """Uploaded file exceeds size limit (413)."""

    status_code = 413
    error_code = "FILE_SIZE_EXCEEDED"

    def __init__(self, max_bytes: int, actual_bytes: int) -> None:
        super().__init__(
            f"File size {actual_bytes} bytes exceeds maximum of {max_bytes} bytes.",
            details={"max_bytes": max_bytes, "actual_bytes": actual_bytes},
        )


class InvalidBundleError(PlatformAPIError):
    """Zip bundle is missing required files (422)."""

    status_code = 422
    error_code = "INVALID_BUNDLE"

    def __init__(self, missing_files: list[str]) -> None:
        super().__init__(
            "Template bundle is missing required files.",
            details={"missing_files": missing_files},
        )


class InvalidZipArchiveError(PlatformAPIError):
    """Zip archive could not be opened or parsed (422)."""

    status_code = 422
    error_code = "INVALID_ZIP_ARCHIVE"

    def __init__(self) -> None:
        super().__init__(
            "Invalid or unreadable zip archive.",
            details={"reason": "bad_zip_file"},
        )


class InvalidManifestError(PlatformAPIError):
    """Manifest has invalid or missing fields (422)."""

    status_code = 422
    error_code = "INVALID_MANIFEST"

    def __init__(self, invalid_fields: dict[str, str]) -> None:
        super().__init__(
            "Manifest contains invalid fields.",
            details={"invalid_fields": invalid_fields},
        )


class InvalidKindError(PlatformAPIError):
    """Kind value is not valid (422)."""

    status_code = 422
    error_code = "INVALID_KIND"

    def __init__(self) -> None:
        super().__init__(
            "Invalid kind value.",
            details={"valid_values": sorted(_VALID_KINDS)},
        )


class InvalidTemplateJsonError(PlatformAPIError):
    """template.json is not valid JSON (422)."""

    status_code = 422
    error_code = "INVALID_TEMPLATE_JSON"

    def __init__(self, reason: str = "not valid JSON") -> None:
        super().__init__(
            "template.json is invalid.",
            details={"reason": reason},
        )


class InvalidPreviewImageError(PlatformAPIError):
    """Preview image is not a valid PNG (422)."""

    status_code = 422
    error_code = "INVALID_PREVIEW_IMAGE"

    def __init__(self) -> None:
        super().__init__(
            "preview.png is not a valid PNG file.",
            details={"reason": "not a valid PNG file"},
        )


class ItemNotFoundError(NotFoundError):
    """Marketplace item not found (404)."""

    error_code = "ITEM_NOT_FOUND"

    def __init__(self, item_id: UUID) -> None:
        super().__init__(
            f"Marketplace item {item_id} not found.",
            details={"item_id": str(item_id)},
        )


class ItemNotAvailableError(ForbiddenError):
    """Item is disabled and not available for download (403)."""

    error_code = "ITEM_NOT_AVAILABLE"

    def __init__(self) -> None:
        super().__init__(
            "Item is not available.",
            details={"reason": "item is disabled"},
        )


class InvalidMetadataError(PlatformAPIError):
    """Metadata update contains invalid fields (422)."""

    status_code = 422
    error_code = "INVALID_METADATA"

    def __init__(self, invalid_fields: dict[str, str]) -> None:
        super().__init__(
            "Metadata update contains invalid fields.",
            details={"invalid_fields": invalid_fields},
        )


class DuplicateItemError(DuplicateError):
    """Duplicate (name, version) pair already exists (409)."""

    error_code = "DUPLICATE_ITEM"

    def __init__(self, name: str, version: str) -> None:
        super().__init__(
            f"Template '{name}' version '{version}' already exists.",
            details={"name": name, "version": version},
        )


class FileUnavailableError(PlatformAPIError):
    """File missing on disk (404)."""

    status_code = 404
    error_code = "FILE_UNAVAILABLE"

    def __init__(self, item_id: UUID) -> None:
        super().__init__(
            f"File unavailable for item {item_id}.",
            details={"item_id": str(item_id)},
        )


# ---------------------------------------------------------------------------
# Update DTO
# ---------------------------------------------------------------------------


@dataclass
class MarketplaceItemUpdate:
    """Data transfer object for item metadata updates."""

    name: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    price: float | None = None


def _normalize_zip_member_path(name: str) -> str:
    return name.replace("\\", "/").strip("/")


def _resolve_required_zip_entries(zf: zipfile.ZipFile) -> dict[str, str]:
    """Map canonical bundle filenames to their path inside the archive."""
    resolved: dict[str, tuple[int, str]] = {}
    for raw_name in zf.namelist():
        if raw_name.endswith(("/", "\\")):
            continue
        normalized = _normalize_zip_member_path(raw_name)
        if not normalized:
            continue
        basename = posixpath.basename(normalized)
        if basename not in _REQUIRED_ZIP_FILES:
            continue
        depth = normalized.count("/")
        current = resolved.get(basename)
        if current is None or depth < current[0]:
            resolved[basename] = (depth, raw_name)
    return {name: path for name, (_, path) in resolved.items()}


def _build_flat_bundle_zip(zf: zipfile.ZipFile, entries: dict[str, str]) -> bytes:
    """Repack required bundle files at the zip root for downstream consumers."""
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as out_zf:
        for canonical in sorted(_REQUIRED_ZIP_FILES):
            out_zf.writestr(canonical, zf.read(entries[canonical]))
    return out.getvalue()


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class MarketplaceService:
    """Service for marketplace template upload, catalog, and management.

    Constructor-injected dependencies:
        repo: MarketplaceRepository — database access
        storage_path: str — root filesystem path for zip/preview storage
    """

    def __init__(self, repo: MarketplaceRepository, storage_path: str) -> None:
        self._repo = repo
        self._storage_path = Path(storage_path)
        # Ensure storage directories exist
        (self._storage_path / "zips").mkdir(parents=True, exist_ok=True)
        (self._storage_path / "previews").mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Upload (Task 3.1)
    # ------------------------------------------------------------------

    async def upload_template(
        self, file_content: bytes, filename: str
    ) -> MarketplaceItemRecord:
        """Upload and validate a template bundle zip.

        Steps:
        1. Validate file size <= 10MB
        2. Open zip in memory, validate root-level required files
        3. Validate manifest.json schema
        4. Validate template.json is parseable JSON
        5. Validate preview.png PNG signature
        6. Check duplicate (name, version)
        7. Store zip and preview to filesystem
        8. Create DB record with status='enabled'

        On failure after partial file write, cleans up stored files.
        """
        # 1. Size check
        if len(file_content) > _MAX_FILE_SIZE_BYTES:
            raise FileSizeExceededError(
                max_bytes=_MAX_FILE_SIZE_BYTES, actual_bytes=len(file_content)
            )

        # 2. Open and validate zip structure
        try:
            zf = zipfile.ZipFile(io.BytesIO(file_content))
        except zipfile.BadZipFile as exc:
            raise InvalidZipArchiveError() from exc

        entries = _resolve_required_zip_entries(zf)
        missing = sorted(_REQUIRED_ZIP_FILES - set(entries))
        if missing:
            raise InvalidBundleError(missing_files=missing)

        # 3. Validate manifest
        try:
            manifest_raw = zf.read(entries["manifest.json"])
            manifest = json.loads(manifest_raw)
        except (json.JSONDecodeError, KeyError) as exc:
            raise InvalidManifestError(
                invalid_fields={"manifest.json": "not valid JSON"}
            ) from exc

        manifest_errors = self._validate_manifest(manifest)
        if manifest_errors:
            raise InvalidManifestError(invalid_fields=manifest_errors)

        # 4. Validate template.json
        try:
            template_raw = zf.read(entries["template.json"])
            json.loads(template_raw)
        except (json.JSONDecodeError, KeyError) as exc:
            raise InvalidTemplateJsonError() from exc

        # 5. Validate preview.png signature
        try:
            preview_bytes = zf.read(entries["preview.png"])
        except KeyError as exc:
            raise InvalidBundleError(missing_files=["preview.png"]) from exc

        if not preview_bytes[:8] == _PNG_SIGNATURE:
            raise InvalidPreviewImageError()

        normalized_zip = _build_flat_bundle_zip(zf, entries)

        # 6. Duplicate check
        name = manifest["name"]
        version = manifest["version"]
        existing = await self._repo.find_by_name_version(name, version)
        if existing is not None:
            raise DuplicateItemError(name=name, version=version)

        # 7. Store files
        item_id = uuid4()
        zip_path = self._storage_path / "zips" / f"{item_id}.zip"
        preview_path = self._storage_path / "previews" / f"{item_id}.png"

        try:
            zip_path.write_bytes(normalized_zip)
            preview_path.write_bytes(preview_bytes)
        except OSError:
            # Cleanup partial writes
            self._safe_delete(zip_path)
            self._safe_delete(preview_path)
            raise

        # 8. Create DB record
        item = MarketplaceItemRecord(
            id=item_id,
            name=name,
            description=manifest["description"],
            version=version,
            author=manifest["author"],
            kind=manifest["kind"],
            tags=manifest.get("tags", []),
            status="enabled",
            zip_path=str(zip_path),
            preview_path=str(preview_path),
            price=float(manifest.get("price", 0.0)),
            created_at=datetime.min,  # Will be set by DB
            updated_at=datetime.min,  # Will be set by DB
        )

        try:
            created = await self._repo.create(item)
        except Exception:
            # Cleanup files if DB insert fails
            self._safe_delete(zip_path)
            self._safe_delete(preview_path)
            raise

        return created

    # ------------------------------------------------------------------
    # Catalog & Listing (Task 3.2)
    # ------------------------------------------------------------------

    async def list_items(
        self, *, page: int = 1, page_size: int = DEFAULT_PAGE_SIZE
    ) -> PaginatedResult[MarketplaceItemRecord]:
        """List all marketplace items for admin view (all statuses).

        Args:
            page: 1-based page number.
            page_size: Items per page (default 25, max 100).

        Raises:
            ValidationError: If page < 1 or page_size invalid.
        """
        page, page_size = self._validate_pagination(page, page_size)
        offset = (page - 1) * page_size

        items, total = await self._repo.list_all(offset=offset, limit=page_size)
        return PaginatedResult(
            items=items, total=total, page=page, page_size=page_size
        )

    async def get_catalog(
        self,
        *,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
        kind: str | None = None,
        search: str | None = None,
    ) -> PaginatedResult[MarketplaceItemRecord]:
        """Get public catalog of enabled items with optional filters.

        Only returns items with status='enabled'. Supports filtering by
        kind (video/reel) and case-insensitive search across name,
        description, and tags.

        Args:
            page: 1-based page number.
            page_size: Items per page (default 25, max 100).
            kind: Optional filter by template kind.
            search: Optional search term (1-100 chars).

        Raises:
            ValidationError: If page/page_size invalid or kind not in valid set.
        """
        page, page_size = self._validate_pagination(page, page_size)

        if kind is not None and kind not in _VALID_KINDS:
            raise ValidationError(
                "Invalid kind filter value.",
                details={"field": "kind", "valid_values": sorted(_VALID_KINDS)},
            )

        offset = (page - 1) * page_size
        items, total = await self._repo.list_enabled(
            offset=offset, limit=page_size, kind=kind, search=search
        )
        return PaginatedResult(
            items=items, total=total, page=page, page_size=page_size
        )

    # ------------------------------------------------------------------
    # Item Management (Task 3.2)
    # ------------------------------------------------------------------

    async def update_item(
        self, item_id: UUID, update: MarketplaceItemUpdate
    ) -> MarketplaceItemRecord:
        """Update marketplace item metadata with validation.

        Validates:
        - name: 1-200 chars (if provided)
        - description: 1-2000 chars (if provided)
        - tags: ≤20 items, each ≤50 chars (if provided)

        Raises:
            ItemNotFoundError: If item does not exist.
            InvalidMetadataError: If any field violates constraints.
        """
        # Validate metadata fields
        invalid_fields: dict[str, str] = {}

        if update.name is not None:
            if len(update.name) < 1:
                invalid_fields["name"] = "must not be empty"
            elif len(update.name) > _MAX_NAME_LENGTH:
                invalid_fields["name"] = f"max {_MAX_NAME_LENGTH} chars"

        if update.description is not None:
            if len(update.description) < 1:
                invalid_fields["description"] = "must not be empty"
            elif len(update.description) > _MAX_DESCRIPTION_LENGTH:
                invalid_fields["description"] = f"max {_MAX_DESCRIPTION_LENGTH} chars"

        if update.tags is not None:
            if len(update.tags) > _MAX_TAGS_COUNT:
                invalid_fields["tags"] = f"max {_MAX_TAGS_COUNT} items"
            else:
                for tag in update.tags:
                    if len(tag) > _MAX_TAG_LENGTH:
                        invalid_fields["tags"] = f"each tag max {_MAX_TAG_LENGTH} chars"
                        break

        if update.price is not None:
            if update.price < 0:
                invalid_fields["price"] = "must be >= 0"

        if invalid_fields:
            raise InvalidMetadataError(invalid_fields=invalid_fields)

        # Check item exists
        existing = await self._repo.get_by_id(item_id)
        if existing is None:
            raise ItemNotFoundError(item_id)

        # Build fields dict for update
        fields: dict[str, Any] = {}
        if update.name is not None:
            fields["name"] = update.name
        if update.description is not None:
            fields["description"] = update.description
        if update.tags is not None:
            fields["tags"] = update.tags
        if update.price is not None:
            fields["price"] = update.price

        if not fields:
            return existing

        updated = await self._repo.update(item_id, fields)
        if updated is None:
            raise ItemNotFoundError(item_id)

        return updated

    async def enable_item(self, item_id: UUID) -> MarketplaceItemRecord:
        """Enable a marketplace item (makes it visible in public catalog).

        Raises:
            ItemNotFoundError: If item does not exist.
        """
        existing = await self._repo.get_by_id(item_id)
        if existing is None:
            raise ItemNotFoundError(item_id)

        updated = await self._repo.update(item_id, {"status": "enabled"})
        if updated is None:
            raise ItemNotFoundError(item_id)

        return updated

    async def disable_item(self, item_id: UUID) -> MarketplaceItemRecord:
        """Disable a marketplace item (hides it from public catalog).

        Raises:
            ItemNotFoundError: If item does not exist.
        """
        existing = await self._repo.get_by_id(item_id)
        if existing is None:
            raise ItemNotFoundError(item_id)

        updated = await self._repo.update(item_id, {"status": "disabled"})
        if updated is None:
            raise ItemNotFoundError(item_id)

        return updated

    async def delete_item(self, item_id: UUID) -> None:
        """Delete a marketplace item: remove DB record then delete files.

        Removes the database record first, then attempts to delete the
        stored zip and preview files. If file deletion fails, logs the
        orphaned paths but still returns success.

        Raises:
            ItemNotFoundError: If item does not exist.
        """
        existing = await self._repo.get_by_id(item_id)
        if existing is None:
            raise ItemNotFoundError(item_id)

        # Remove DB record first
        deleted = await self._repo.delete(item_id)
        if not deleted:
            raise ItemNotFoundError(item_id)

        # Then attempt file cleanup (log but don't fail on errors)
        self._cleanup_files(existing.zip_path, existing.preview_path, item_id)

    # ------------------------------------------------------------------
    # File path resolution (Task 3.2)
    # ------------------------------------------------------------------

    async def get_preview_path(self, item_id: UUID) -> str:
        """Get filesystem path for preview image.

        Raises:
            ItemNotFoundError: If item does not exist.
            FileUnavailableError: If preview file is missing on disk.
        """
        item = await self._repo.get_by_id(item_id)
        if item is None:
            raise ItemNotFoundError(item_id)

        if not Path(item.preview_path).is_file():
            raise FileUnavailableError(item_id)

        return item.preview_path

    async def update_preview(self, item_id: UUID, content: bytes) -> "MarketplaceItemRecord":
        """Upload or replace the preview image for a marketplace item.

        Validates PNG signature, writes to disk, updates the DB record.

        Raises:
            ItemNotFoundError: If item does not exist.
            ValidationError: If content is not a valid PNG.
        """
        item = await self._repo.get_by_id(item_id)
        if item is None:
            raise ItemNotFoundError(item_id)

        # Validate PNG signature
        if not content.startswith(_PNG_SIGNATURE):
            raise ValidationError(
                error_code="INVALID_PREVIEW_IMAGE",
                message="File is not a valid PNG image.",
                details={"reason": "not a valid PNG file"},
            )

        # Write preview to disk
        previews_dir = Path(self._storage_path) / "previews"
        previews_dir.mkdir(parents=True, exist_ok=True)
        preview_path = previews_dir / f"{item_id}.png"
        preview_path.write_bytes(content)

        # Update DB record with new preview path
        updated = await self._repo.update(item_id, {"preview_path": str(preview_path)})
        if updated is None:
            raise ItemNotFoundError(item_id)

        return updated

    async def get_download_path(self, item_id: UUID) -> str:
        """Get filesystem path for zip download.

        Checks item exists, checks status (disabled = 403), and
        verifies file exists on disk.

        Raises:
            ItemNotFoundError: If item does not exist.
            ItemNotAvailableError: If item is disabled.
            FileUnavailableError: If zip file is missing on disk.
        """
        item = await self._repo.get_by_id(item_id)
        if item is None:
            raise ItemNotFoundError(item_id)

        if item.status == "disabled":
            raise ItemNotAvailableError()

        if not Path(item.zip_path).is_file():
            raise FileUnavailableError(item_id)

        return item.zip_path

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _validate_manifest(self, manifest: dict[str, Any]) -> dict[str, str]:
        """Validate manifest fields and return dict of invalid fields."""
        errors: dict[str, str] = {}

        # Required string fields
        for field, max_len in [
            ("name", _MAX_NAME_LENGTH),
            ("description", _MAX_DESCRIPTION_LENGTH),
            ("version", _MAX_VERSION_LENGTH),
            ("author", _MAX_AUTHOR_LENGTH),
        ]:
            value = manifest.get(field)
            if not value or not isinstance(value, str) or value.strip() == "":
                errors[field] = "required"
            elif len(value) > max_len:
                errors[field] = f"max {max_len} chars"

        # Kind validation
        kind = manifest.get("kind")
        if not kind or kind not in _VALID_KINDS:
            errors["kind"] = f"must be one of: {', '.join(sorted(_VALID_KINDS))}"

        # Tags validation (optional but constrained)
        tags = manifest.get("tags", [])
        if not isinstance(tags, list):
            errors["tags"] = "must be an array"
        elif len(tags) > _MAX_TAGS_COUNT:
            errors["tags"] = f"max {_MAX_TAGS_COUNT} items"
        else:
            for tag in tags:
                if not isinstance(tag, str) or len(tag) > _MAX_TAG_LENGTH:
                    errors["tags"] = f"each tag max {_MAX_TAG_LENGTH} chars"
                    break

        # Price validation (optional, default 0.00)
        price = manifest.get("price", 0.0)
        if not isinstance(price, (int, float)):
            errors["price"] = "must be a number"
        elif price < 0:
            errors["price"] = "must be >= 0"

        return errors

    def _validate_pagination(self, page: int, page_size: int) -> tuple[int, int]:
        """Validate and clamp pagination parameters."""
        if page < 1:
            raise ValidationError(
                "page must be at least 1.",
                details={"page": page},
            )
        if page_size < 1:
            raise ValidationError(
                "page_size must be at least 1.",
                details={"page_size": page_size},
            )
        if page_size > MAX_PAGE_SIZE:
            page_size = MAX_PAGE_SIZE
        return page, page_size

    def _cleanup_files(
        self, zip_path: str, preview_path: str, item_id: UUID
    ) -> None:
        """Attempt to delete stored files; log failures as orphans."""
        for path in (zip_path, preview_path):
            try:
                p = Path(path)
                if p.exists():
                    p.unlink()
            except OSError as exc:
                logger.warning(
                    "Orphaned file after delete of item %s: %s (error: %s)",
                    item_id,
                    path,
                    exc,
                )

    @staticmethod
    def _safe_delete(path: Path) -> None:
        """Silently delete a file if it exists."""
        try:
            if path.exists():
                path.unlink()
        except OSError:
            pass
