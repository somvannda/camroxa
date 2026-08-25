"""Unit tests for marketplace template install/reinstall via VideoLocalStore."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from typing import Any

import pytest

from features.marketplace.coordinator import MarketplaceCoordinator
from features.video.services import video_local_store
from features.video.services.video_local_store import VideoLocalStore
from shared.lib import app_paths
from shared.services.platform_client import PlatformApiError


class _FakePlatformClient:
    def __init__(
        self,
        *,
        zip_bytes: bytes | None = None,
        error: Exception | None = None,
    ) -> None:
        self.zip_bytes = zip_bytes
        self.error = error
        self.byte_calls: list[dict[str, Any]] = []

    def request(self, path: str, **kwargs: Any) -> Any:
        raise NotImplementedError

    def request_bytes(self, path: str, **kwargs: Any) -> bytes:
        self.byte_calls.append({"path": path, **kwargs})
        if self.error is not None:
            raise self.error
        if self.zip_bytes is None:
            raise PlatformApiError(500, "No zip configured")
        return self.zip_bytes


def _make_zip(*, name: str = "Thunder Bass", kind: str = "video") -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "manifest.json",
            json.dumps(
                {
                    "name": name,
                    "description": "Bass drop",
                    "version": "1.0.0",
                    "author": "Admin",
                    "kind": kind,
                    "tags": ["bass"],
                }
            ),
        )
        zf.writestr(
            "template.json",
            json.dumps(
                {
                    "templateName": name,
                    "style": "straight-bars",
                    "layers": [{"id": "layer-1"}],
                }
            ),
        )
        zf.writestr("preview.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 8)
    return buf.getvalue()


@pytest.fixture()
def isolated_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> VideoLocalStore:
    user_templates_path = tmp_path / "user-templates.json"
    prefs_path = tmp_path / "prefs.json"
    monkeypatch.setattr(app_paths, "get_user_video_templates_path", lambda: user_templates_path)
    monkeypatch.setattr(app_paths, "get_video_workspace_prefs_path", lambda: prefs_path)
    monkeypatch.setattr(app_paths, "get_video_draft_store_dir", lambda: tmp_path / "drafts")
    monkeypatch.setattr(video_local_store, "get_user_video_templates_path", lambda: user_templates_path)
    monkeypatch.setattr(video_local_store, "get_video_workspace_prefs_path", lambda: prefs_path)
    monkeypatch.setattr(video_local_store, "get_video_draft_store_dir", lambda: tmp_path / "drafts")
    return VideoLocalStore()


def _coordinator(
    client: _FakePlatformClient,
    store: VideoLocalStore,
    *,
    errors: list[str] | None = None,
) -> MarketplaceCoordinator:
    err_list = errors if errors is not None else []
    return MarketplaceCoordinator(
        platform_client=client,  # type: ignore[arg-type]
        template_store=store,
        user_id="user-1",
        on_install_complete=lambda _uid: None,
        on_error=lambda msg: err_list.append(msg),
    )


def test_install_template_writes_marketplace_record(isolated_store: VideoLocalStore) -> None:
    client = _FakePlatformClient(zip_bytes=_make_zip())
    errors: list[str] = []
    coord = _coordinator(client, isolated_store, errors=errors)

    result = coord.install_template("item-thunder")

    assert result.ok
    assert result.uid
    assert errors == []
    assert client.byte_calls[0]["path"] == "/marketplace/items/item-thunder/download"
    assert client.byte_calls[0]["auth"] is True

    record = isolated_store.get_by_marketplace_item_id("item-thunder")
    assert record is not None
    assert record["id"] == result.uid
    assert record["name"] == "Thunder Bass"
    assert record["source"] == "marketplace"
    assert record["marketplace_item_id"] == "item-thunder"
    assert record["template"]["style"] == "straight-bars"
    assert coord.is_installed("item-thunder") is True


def test_install_appears_in_read_templates_and_workspace_dropdown(
    isolated_store: VideoLocalStore,
) -> None:
    """Installed marketplace templates must show in the same list as local ones."""
    client = _FakePlatformClient(zip_bytes=_make_zip(name="Market Drop"))
    coord = _coordinator(client, isolated_store)
    result = coord.install_template("item-market")
    assert result.ok

    listed = isolated_store.read_templates()
    assert any(
        item.get("id") == result.uid and item.get("source") == "marketplace" for item in listed
    )

    workspace = isolated_store.read_workspace_state({"outputResolution": "1920x1080"})
    dropdown_ids = {summary.id for summary in workspace.templates}
    assert result.uid in dropdown_ids
    assert any(summary.name == "Market Drop" for summary in workspace.templates)


def test_install_template_rejects_duplicate(isolated_store: VideoLocalStore) -> None:
    client = _FakePlatformClient(zip_bytes=_make_zip())
    coord = _coordinator(client, isolated_store)
    first = coord.install_template("item-thunder")
    assert first.ok

    second = coord.install_template("item-thunder")
    assert not second.ok
    assert second.error == "Template is already installed"
    assert len([t for t in isolated_store.read_templates() if t.get("source") == "marketplace"]) == 1


def test_reinstall_template_preserves_id(isolated_store: VideoLocalStore) -> None:
    client = _FakePlatformClient(zip_bytes=_make_zip(name="Thunder Bass"))
    coord = _coordinator(client, isolated_store)
    first = coord.install_template("item-thunder")
    assert first.ok

    client.zip_bytes = _make_zip(name="Thunder Bass v2")
    second = coord.reinstall_template("item-thunder")
    assert second.ok
    assert second.uid == first.uid

    record = isolated_store.get_by_marketplace_item_id("item-thunder")
    assert record is not None
    assert record["id"] == first.uid
    assert record["name"] == "Thunder Bass v2"


def test_install_surfaces_auth_error(isolated_store: VideoLocalStore) -> None:
    client = _FakePlatformClient(error=PlatformApiError(401, "Unauthenticated"))
    errors: list[str] = []
    coord = _coordinator(client, isolated_store, errors=errors)

    result = coord.install_template("item-thunder")

    assert not result.ok
    assert result.error is not None
    assert "sign in" in result.error.lower() or "session" in result.error.lower()
    assert result.error in errors
    assert isolated_store.get_by_marketplace_item_id("item-thunder") is None


def test_install_surfaces_network_error(isolated_store: VideoLocalStore) -> None:
    client = _FakePlatformClient(
        error=PlatformApiError(0, "Cannot connect to http://localhost:8000/api/v3. Start platform_api.")
    )
    coord = _coordinator(client, isolated_store)

    result = coord.install_template("item-thunder")

    assert not result.ok
    assert result.error is not None
    assert "Cannot connect" in result.error
