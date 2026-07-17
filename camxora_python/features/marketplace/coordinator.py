"""MarketplaceCoordinator — orchestrates marketplace browsing and template installation.

Handles catalog fetching, template downloading/installing, reinstalling, and
duplicate detection. Uses constructor-injected dependencies following the
coordinator pattern (no Qt imports). Persists installed templates via
VideoLocalStore (local JSON), not PostgreSQL.
"""

from __future__ import annotations

import io
import json
import uuid
import zipfile
from dataclasses import dataclass
from typing import Any, Callable, Protocol

from features.video.services.video_local_store import VideoLocalStore
from shared.services.platform_client import PlatformApiError, PlatformClient


class LoggerPort(Protocol):
    """Logging interface to decouple from app-level logging."""

    def info(self, msg: str) -> None: ...
    def error(self, msg: str) -> None: ...
    def warning(self, msg: str) -> None: ...


@dataclass(frozen=True)
class CatalogItem:
    """A single marketplace catalog item."""

    id: str
    name: str
    description: str
    version: str
    author: str
    kind: str
    tags: list[str]
    status: str
    price: float
    preview_url: str
    created_at: str


@dataclass(frozen=True)
class CatalogResponse:
    """Paginated catalog response from the Platform API."""

    items: list[CatalogItem]
    total: int
    page: int
    page_size: int
    error: str | None = None


@dataclass(frozen=True)
class InstallResult:
    """Outcome of install/reinstall."""

    uid: str = ""
    error: str | None = None

    @property
    def ok(self) -> bool:
        return bool(self.uid) and self.error is None


class MarketplaceCoordinator:
    """Orchestrates marketplace browsing and template installation.

    Dependencies (constructor-injected):
        platform_client: PlatformClient (auth + token refresh)
        template_store: VideoLocalStore for local template catalog
        user_id: str — authenticated user identifier
        on_install_complete: Callable[[str], None] — called with template uid on success
        on_error: Callable[[str], None] — called with error message on install/download failure
        logger: LoggerPort | None — optional structured logger
    """

    _CATALOG_TIMEOUT: float = 15.0
    _DOWNLOAD_TIMEOUT: float = 60.0
    _CATALOG_PAGE_SIZE: int = 20

    def __init__(
        self,
        *,
        platform_client: PlatformClient,
        template_store: VideoLocalStore,
        user_id: str,
        on_install_complete: Callable[[str], None],
        on_error: Callable[[str], None],
        logger: LoggerPort | None = None,
    ) -> None:
        self._client = platform_client
        self._store = template_store
        self._user_id = user_id
        self._on_install_complete = on_install_complete
        self._on_error = on_error
        self._logger = logger or _NullLogger()
        self._last_fetch_error: str | None = None

    @property
    def last_fetch_error(self) -> str | None:
        """Most recent catalog fetch error, or None after a successful fetch."""
        return self._last_fetch_error

    # ─── Public API ───────────────────────────────────────────────────────

    def fetch_catalog(
        self,
        *,
        page: int = 1,
        kind: str | None = None,
        search: str | None = None,
    ) -> CatalogResponse:
        """Fetch the marketplace catalog from the Platform API.

        Uses PlatformClient with auth so access tokens stay fresh. Failures are
        surfaced via ``CatalogResponse.error`` / ``last_fetch_error`` (not the
        install ``on_error`` callback) so the UI can distinguish empty vs error.

        Args:
            page: Page number (1-indexed).
            kind: Optional filter — 'video' or 'reel'.
            search: Optional search query string.
        """
        self._last_fetch_error = None
        params: dict[str, Any] = {
            "page": page,
            "page_size": self._CATALOG_PAGE_SIZE,
        }
        # Only send filters when meaningful — empty kind/"All" must omit the param
        # so the API does not reject or filter incorrectly.
        if kind:
            params["kind"] = kind
        if search:
            params["search"] = search

        try:
            data = self._client.request(
                "/marketplace/catalog",
                auth=True,
                params=params,
                timeout=self._CATALOG_TIMEOUT,
            )
            if not isinstance(data, dict):
                raise ValueError("Catalog response is not a JSON object")

            raw_items = data.get("items")
            if raw_items is None:
                raw_items = []
            if not isinstance(raw_items, list):
                raise ValueError("Catalog 'items' is not a list")

            items: list[CatalogItem] = []
            for item in raw_items:
                parsed = self._parse_catalog_item(item)
                if parsed is not None:
                    items.append(parsed)

            total = int(data.get("total") or 0)
            resp_page = int(data.get("page") or page)
            page_size = int(data.get("page_size") or self._CATALOG_PAGE_SIZE)

            return CatalogResponse(
                items=items,
                total=total,
                page=resp_page,
                page_size=page_size,
            )

        except PlatformApiError as exc:
            msg = self._format_platform_error(exc)
            self._logger.error(msg)
            self._last_fetch_error = msg
            return CatalogResponse(
                items=[],
                total=0,
                page=page,
                page_size=self._CATALOG_PAGE_SIZE,
                error=msg,
            )

        except Exception as exc:
            msg = f"Catalog fetch failed: {exc}"
            self._logger.error(msg)
            self._last_fetch_error = msg
            return CatalogResponse(
                items=[],
                total=0,
                page=page,
                page_size=self._CATALOG_PAGE_SIZE,
                error=msg,
            )

    def install_template(self, item_id: str) -> InstallResult:
        """Download and install a marketplace template locally.

        Downloads the template zip, extracts template.json and manifest.json,
        checks for duplicates, and inserts a new record into the local
        video template catalog (VideoLocalStore).

        Args:
            item_id: The marketplace item UUID to install.

        Returns:
            InstallResult with uid on success, or error message on failure.
        """
        try:
            existing = self._store.get_by_marketplace_item_id(item_id)
            if existing is not None:
                self._logger.warning(
                    f"Template from marketplace item {item_id} is already installed"
                )
                return self._fail("Template is already installed")

            zip_bytes, download_error = self._download_zip(item_id)
            if zip_bytes is None:
                return self._fail(download_error or "Download failed")

            template_json, manifest, extract_error = self._extract_zip_contents(zip_bytes)
            if template_json is None or manifest is None:
                return self._fail(extract_error or "Template file is corrupted")

            uid = str(uuid.uuid4())
            name = str(manifest.get("name") or "Untitled")
            kind = str(manifest.get("kind") or "video")

            self._store.insert_marketplace_template(
                template_id=uid,
                name=name,
                template_json=template_json,
                kind=kind,
                marketplace_item_id=item_id,
                user_id=self._user_id,
            )

            self._logger.info(f"Installed marketplace template '{name}' as {uid}")
            self._on_install_complete(uid)
            return InstallResult(uid=uid)

        except PlatformApiError as exc:
            msg = self._format_platform_error(exc, action="Download")
            self._logger.error(msg)
            return self._fail(msg)

        except zipfile.BadZipFile:
            self._logger.error(f"Corrupt zip file for item {item_id}")
            return self._fail("Template file is corrupted")

        except json.JSONDecodeError:
            self._logger.error(f"Invalid JSON in template for item {item_id}")
            return self._fail("Invalid template data")

        except OSError as exc:
            msg = self._classify_os_error(exc)
            self._logger.error(f"OS error installing item {item_id}: {exc}")
            return self._fail(msg)

        except Exception as exc:
            self._logger.error(f"Unexpected error installing item {item_id}: {exc}")
            return self._fail(f"Installation failed: {exc}")

    def reinstall_template(self, item_id: str) -> InstallResult:
        """Reinstall a marketplace template, updating content while preserving identity.

        Downloads a fresh copy and updates the existing local record, preserving
        the original uid and created_at timestamp.

        Args:
            item_id: The marketplace item UUID to reinstall.

        Returns:
            InstallResult with uid on success, or error message on failure.
        """
        try:
            existing = self._store.get_by_marketplace_item_id(item_id)
            if existing is None:
                self._logger.error(
                    f"Cannot reinstall: no existing record for marketplace item {item_id}"
                )
                return self._fail("Template is not installed")

            zip_bytes, download_error = self._download_zip(item_id)
            if zip_bytes is None:
                return self._fail(download_error or "Download failed")

            template_json, manifest, extract_error = self._extract_zip_contents(zip_bytes)
            if template_json is None or manifest is None:
                return self._fail(extract_error or "Template file is corrupted")

            uid = str(existing.get("id") or "").strip()
            if not uid:
                return self._fail("Installed template is missing an id")
            name = str(manifest.get("name") or "Untitled")
            kind = str(manifest.get("kind") or "video")

            updated = self._store.update_marketplace_template(
                template_id=uid,
                name=name,
                template_json=template_json,
                kind=kind,
            )
            if updated is None:
                return self._fail("Failed to save template")

            self._logger.info(f"Reinstalled marketplace template '{name}' ({uid})")
            self._on_install_complete(uid)
            return InstallResult(uid=uid)

        except PlatformApiError as exc:
            msg = self._format_platform_error(exc, action="Download")
            self._logger.error(msg)
            return self._fail(msg)

        except zipfile.BadZipFile:
            self._logger.error(f"Corrupt zip file for reinstall of item {item_id}")
            return self._fail("Template file is corrupted")

        except json.JSONDecodeError:
            self._logger.error(f"Invalid JSON in template for reinstall of item {item_id}")
            return self._fail("Invalid template data")

        except OSError as exc:
            msg = self._classify_os_error(exc)
            self._logger.error(f"OS error reinstalling item {item_id}: {exc}")
            return self._fail(msg)

        except Exception as exc:
            self._logger.error(f"Unexpected error reinstalling item {item_id}: {exc}")
            return self._fail(f"Reinstallation failed: {exc}")

    def is_installed(self, marketplace_item_id: str) -> bool:
        """Check whether a marketplace item is already installed locally."""
        try:
            return self._store.get_by_marketplace_item_id(marketplace_item_id) is not None
        except Exception as exc:
            self._logger.error(f"Error checking installation status: {exc}")
            return False

    # ─── Private Helpers ──────────────────────────────────────────────────

    def _fail(self, message: str) -> InstallResult:
        self._on_error(message)
        return InstallResult(error=message)

    def _download_zip(self, item_id: str) -> tuple[bytes | None, str | None]:
        """Download the template zip from the Platform API."""
        try:
            data = self._client.request_bytes(
                f"/marketplace/items/{item_id}/download",
                auth=True,
                timeout=self._DOWNLOAD_TIMEOUT,
            )
            return data, None
        except PlatformApiError as exc:
            msg = self._format_platform_error(exc, action="Download")
            self._logger.error(msg)
            return None, msg
        except Exception as exc:
            msg = f"Download failed: {exc}"
            self._logger.error(msg)
            return None, msg

    def _extract_zip_contents(
        self, zip_bytes: bytes
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None, str | None]:
        """Extract template.json and manifest.json from zip bytes."""
        try:
            with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
                entries: dict[str, str] = {}
                for raw_name in zf.namelist():
                    if raw_name.endswith(("/", "\\")):
                        continue
                    normalized = raw_name.replace("\\", "/").strip("/")
                    if not normalized:
                        continue
                    basename = normalized.rsplit("/", 1)[-1]
                    if basename not in {"template.json", "manifest.json"}:
                        continue
                    depth = normalized.count("/")
                    current = entries.get(basename)
                    if current is None or depth < current[0]:
                        entries[basename] = (depth, raw_name)

                template_path = entries.get("template.json", (None, None))[1]
                manifest_path = entries.get("manifest.json", (None, None))[1]

                if template_path is None:
                    self._logger.error("Zip missing template.json")
                    return None, None, "Template file is corrupted"

                if manifest_path is None:
                    self._logger.error("Zip missing manifest.json")
                    return None, None, "Template file is corrupted"

                template_raw = zf.read(template_path)
                manifest_raw = zf.read(manifest_path)

            template_json: dict[str, Any] = json.loads(template_raw)
            manifest: dict[str, Any] = json.loads(manifest_raw)

            return template_json, manifest, None

        except zipfile.BadZipFile:
            self._logger.error("Invalid zip archive")
            return None, None, "Template file is corrupted"

        except json.JSONDecodeError as exc:
            self._logger.error(f"Invalid JSON in zip contents: {exc}")
            return None, None, "Invalid template data"

        except OSError as exc:
            msg = self._classify_os_error(exc)
            self._logger.error(f"OS error extracting zip: {exc}")
            return None, None, msg

    @staticmethod
    def _parse_catalog_item(item: Any) -> CatalogItem | None:
        """Parse one catalog item; skip malformed rows instead of emptying the page."""
        if not isinstance(item, dict):
            return None
        item_id = item.get("id")
        name = item.get("name")
        if not item_id or not name:
            return None
        tags = item.get("tags") or []
        if not isinstance(tags, list):
            tags = []
        raw_price = item.get("price", 0.0)
        try:
            price = float(raw_price) if raw_price is not None else 0.0
        except (TypeError, ValueError):
            price = 0.0
        return CatalogItem(
            id=str(item_id),
            name=str(name),
            description=str(item.get("description") or ""),
            version=str(item.get("version") or ""),
            author=str(item.get("author") or ""),
            kind=str(item.get("kind") or ""),
            tags=[str(t) for t in tags],
            status=str(item.get("status") or "enabled"),
            price=price,
            preview_url=str(item.get("preview_url") or ""),
            created_at=str(item.get("created_at") or ""),
        )

    @staticmethod
    def _format_platform_error(exc: PlatformApiError, *, action: str = "Catalog fetch") -> str:
        if exc.status == 0:
            return str(exc) or f"{action} failed (network)"
        if exc.status == 401:
            return "Session expired — please sign in again"
        if exc.status == 403:
            return f"{action} forbidden — you may not have permission for this item"
        if exc.status == 404:
            return f"{action} not found — the template may have been removed"
        if exc.status >= 500:
            return f"{action} failed on the server (status {exc.status}). Try again later."
        detail = str(exc).strip()
        if detail and detail.lower() not in {"", "none"}:
            return f"{action} failed: {detail}"
        return f"{action} failed with status {exc.status}"

    @staticmethod
    def _classify_os_error(exc: OSError) -> str:
        """Classify an OSError into a user-friendly message."""
        import errno

        if exc.errno == errno.ENOSPC:
            return "Not enough disk space"
        if exc.errno == errno.EACCES:
            return "Permission denied — cannot write template files"
        return f"File system error: {exc.strerror or exc}"


class _NullLogger:
    """No-op logger used when no logger is provided."""

    def info(self, msg: str) -> None:
        pass

    def error(self, msg: str) -> None:
        pass

    def warning(self, msg: str) -> None:
        pass
