from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from platform_api.exceptions import ValidationError
from platform_api.middleware.auth import AuthContext, require_admin
from platform_api.main import create_app
from platform_api.services.desktop_release_upload_service import (
    DesktopReleaseUploadService,
    extract_version_from_installer_filename,
)


def test_store_installer_uses_versioned_filename(tmp_path: Path) -> None:
    service = DesktopReleaseUploadService(
        storage_root=str(tmp_path),
        public_base_url="https://downloads.example.com/desktop",
    )
    result = service.store_installer(
        b"fake-zip-bytes",
        original_filename="Camxora.zip",
        version="2.5.0",
    )
    assert result.filename == "Camxora-2.5.0.zip"
    assert result.download_url == "https://downloads.example.com/desktop/Camxora-2.5.0.zip"
    assert (tmp_path / "Camxora-2.5.0.zip").read_bytes() == b"fake-zip-bytes"


def test_store_installer_rejects_invalid_extension(tmp_path: Path) -> None:
    service = DesktopReleaseUploadService(storage_root=str(tmp_path))
    with pytest.raises(ValidationError, match=r"\.zip, \.exe, or \.msi"):
        service.store_installer(b"data", original_filename="installer.txt", version="1.0.0")


def test_store_installer_rejects_empty_file(tmp_path: Path) -> None:
    service = DesktopReleaseUploadService(storage_root=str(tmp_path))
    with pytest.raises(ValidationError, match="empty"):
        service.store_installer(b"", original_filename="Camxora.zip", version="1.0.0")


def test_store_installer_falls_back_to_api_download_url(tmp_path: Path) -> None:
    service = DesktopReleaseUploadService(
        storage_root=str(tmp_path),
        api_download_base_url="https://api.example.com/api/v1/public/desktop-release/files",
    )
    result = service.store_installer(
        b"payload",
        original_filename="Camxora.zip",
        version="0.3.0",
    )
    assert (
        result.download_url
        == "https://api.example.com/api/v1/public/desktop-release/files/Camxora-0.3.0.zip"
    )


def test_extract_version_from_installer_filename() -> None:
    assert extract_version_from_installer_filename("Camxora-2.5.0.zip") == "2.5.0"
    assert extract_version_from_installer_filename("Camxora-0.3.0.exe") == "0.3.0"
    assert extract_version_from_installer_filename("custom-name.zip") is None


def test_list_installers_returns_newest_first(tmp_path: Path) -> None:
    service = DesktopReleaseUploadService(
        storage_root=str(tmp_path),
        api_download_base_url="https://api.example.com/api/v1/public/desktop-release/files",
    )
    service.store_installer(b"one", original_filename="Camxora.zip", version="1.0.0")
    service.store_installer(b"two", original_filename="Camxora.zip", version="2.0.0")
    records = service.list_installers()
    assert len(records) == 2
    assert records[0].filename == "Camxora-2.0.0.zip"
    assert records[0].download_url.endswith("/Camxora-2.0.0.zip")
    assert records[1].filename == "Camxora-1.0.0.zip"


def test_delete_installer_removes_file(tmp_path: Path) -> None:
    service = DesktopReleaseUploadService(storage_root=str(tmp_path))
    result = service.store_installer(b"payload", original_filename="Camxora.zip", version="1.2.3")
    service.delete_installer(result.filename)
    assert service.resolve_existing_file(result.filename) is None


def test_delete_installer_missing_file_raises(tmp_path: Path) -> None:
    service = DesktopReleaseUploadService(storage_root=str(tmp_path))
    with pytest.raises(ValidationError, match="not found"):
        service.delete_installer("Camxora-9.9.9.zip")


def test_public_download_route_serves_uploaded_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = DesktopReleaseUploadService(storage_root=str(tmp_path))
    service.store_installer(b"zip-content", original_filename="Camxora.zip", version="1.2.3")

    monkeypatch.setenv("PLATFORM_DESKTOP_RELEASE_STORAGE_PATH", str(tmp_path))

    from platform_api.config import get_settings

    get_settings.cache_clear()

    app = create_app()
    client = TestClient(app)
    response = client.get("/api/v1/public/desktop-release/files/Camxora-1.2.3.zip")
    assert response.status_code == 200
    assert response.content == b"zip-content"
    assert response.headers["content-type"].startswith("application/zip")


class _FakeSettingsPool:
    settings: dict[str, str] = {}

    async def fetchrow(self, query: str, key: str):
        value = self.settings.get(key)
        if value is None:
            return None
        return {"value": value}

    async def execute(self, query: str, *args):
        if "INSERT INTO system_settings" in query and len(args) >= 2:
            self.settings[str(args[0])] = str(args[1])


def test_admin_upload_endpoint_returns_download_url(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PLATFORM_DESKTOP_RELEASE_STORAGE_PATH", str(tmp_path))
    monkeypatch.setenv("PLATFORM_PUBLIC_API_BASE_URL", "https://api.example.com")

    from platform_api.config import get_settings

    get_settings.cache_clear()

    app = create_app()
    app.dependency_overrides[require_admin] = lambda: AuthContext(
        user_id="admin-1",
        email="admin@test.com",
        role="admin",
    )

    class _FakePool(_FakeSettingsPool):
        pass

    fake_pool = _FakePool()
    monkeypatch.setattr("platform_api.dependencies.get_db_pool", lambda: fake_pool)

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zf:
        zf.writestr("Camxora.exe", b"binary")
    zip_buffer.seek(0)

    client = TestClient(app)
    response = client.post(
        "/api/v1/admin/desktop/software-update/upload",
        data={"version": "2.6.0"},
        files={"file": ("Camxora.zip", zip_buffer.getvalue(), "application/zip")},
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["filename"] == "Camxora-2.6.0.zip"
    assert (
        payload["download_url"]
        == "https://api.example.com/api/v1/public/desktop-release/files/Camxora-2.6.0.zip"
    )
    assert payload["size_bytes"] > 0
    assert payload["draft_saved"] is True
    assert fake_pool.settings["desktop.software_update.download_url"] == payload["download_url"]
    assert fake_pool.settings["desktop.software_update.version"] == "2.6.0"


def test_admin_list_installers_endpoint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PLATFORM_DESKTOP_RELEASE_STORAGE_PATH", str(tmp_path))
    monkeypatch.setenv("PLATFORM_PUBLIC_API_BASE_URL", "https://api.example.com")

    from platform_api.config import get_settings

    get_settings.cache_clear()

    service = DesktopReleaseUploadService(storage_root=str(tmp_path))
    service.store_installer(b"payload", original_filename="Camxora.zip", version="3.1.0")

    app = create_app()
    app.dependency_overrides[require_admin] = lambda: AuthContext(
        user_id="admin-1",
        email="admin@test.com",
        role="admin",
    )
    monkeypatch.setattr("platform_api.dependencies.get_db_pool", lambda: _FakeSettingsPool())

    client = TestClient(app)
    response = client.get("/api/v1/admin/desktop/software-update/installers")
    app.dependency_overrides.clear()

    assert response.status_code == 200, response.text
    payload = response.json()
    assert len(payload["items"]) == 1
    assert payload["items"][0]["filename"] == "Camxora-3.1.0.zip"
    assert payload["items"][0]["download_url"].startswith("https://api.example.com/")


def test_admin_delete_installer_endpoint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PLATFORM_DESKTOP_RELEASE_STORAGE_PATH", str(tmp_path))

    from platform_api.config import get_settings

    get_settings.cache_clear()

    service = DesktopReleaseUploadService(storage_root=str(tmp_path))
    result = service.store_installer(b"payload", original_filename="Camxora.zip", version="4.0.0")

    app = create_app()
    app.dependency_overrides[require_admin] = lambda: AuthContext(
        user_id="admin-1",
        email="admin@test.com",
        role="admin",
    )
    monkeypatch.setattr("platform_api.dependencies.get_db_pool", lambda: _FakeSettingsPool())

    client = TestClient(app)
    response = client.delete(
        f"/api/v1/admin/desktop/software-update/installers/{result.filename}",
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "deleted"
    assert service.resolve_existing_file(result.filename) is None
