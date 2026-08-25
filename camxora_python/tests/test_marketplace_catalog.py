"""Unit tests for marketplace catalog fetch, parsing, and preview cache."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from PySide6.QtWidgets import QApplication

from features.marketplace.coordinator import MarketplaceCoordinator
from features.marketplace.preview_loader import MarketplacePreviewLoader
from features.video.services.video_local_store import VideoLocalStore
from shared.services.platform_client import PlatformApiError


@pytest.fixture
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class _FakePlatformClient:
    def __init__(self, *, payload: Any = None, error: Exception | None = None) -> None:
        self.payload = payload
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def request(self, path: str, **kwargs: Any) -> Any:
        self.calls.append({"path": path, **kwargs})
        if self.error is not None:
            raise self.error
        return self.payload

    def request_bytes(self, path: str, **kwargs: Any) -> bytes:
        raise NotImplementedError


def _coordinator(client: _FakePlatformClient, store: VideoLocalStore | None = None) -> MarketplaceCoordinator:
    return MarketplaceCoordinator(
        platform_client=client,  # type: ignore[arg-type]
        template_store=store or VideoLocalStore(),
        user_id="user-1",
        on_install_complete=lambda _uid: None,
        on_error=lambda _msg: None,
    )


def test_fetch_catalog_success_parses_items() -> None:
    client = _FakePlatformClient(
        payload={
            "items": [
                {
                    "id": "a1",
                    "name": "Thunder Bass",
                    "description": "Bass drop",
                    "kind": "video",
                    "price": 0,
                    "preview_url": "/api/v3/marketplace/items/a1/preview",
                    "tags": ["bass"],
                }
            ],
            "total": 1,
            "page": 1,
            "page_size": 20,
        }
    )
    coord = _coordinator(client)
    resp = coord.fetch_catalog(page=1)

    assert resp.error is None
    assert coord.last_fetch_error is None
    assert resp.total == 1
    assert len(resp.items) == 1
    assert resp.items[0].name == "Thunder Bass"
    assert client.calls[0]["auth"] is True
    assert "kind" not in client.calls[0]["params"]
    assert "search" not in client.calls[0]["params"]


def test_fetch_catalog_omits_empty_filters() -> None:
    client = _FakePlatformClient(payload={"items": [], "total": 0, "page": 1, "page_size": 20})
    coord = _coordinator(client)
    coord.fetch_catalog(page=1, kind=None, search="")
    params = client.calls[0]["params"]
    assert "kind" not in params
    assert "search" not in params


def test_fetch_catalog_sends_kind_and_search() -> None:
    client = _FakePlatformClient(payload={"items": [], "total": 0, "page": 1, "page_size": 20})
    coord = _coordinator(client)
    coord.fetch_catalog(page=2, kind="reel", search="thunder")
    params = client.calls[0]["params"]
    assert params["kind"] == "reel"
    assert params["search"] == "thunder"
    assert params["page"] == 2


def test_fetch_catalog_auth_error_surfaces_not_empty_success() -> None:
    client = _FakePlatformClient(error=PlatformApiError(401, "Unauthenticated"))
    coord = _coordinator(client)
    resp = coord.fetch_catalog()

    assert resp.items == []
    assert resp.total == 0
    assert resp.error is not None
    assert "sign in" in resp.error.lower() or "session" in resp.error.lower()
    assert coord.last_fetch_error == resp.error


def test_fetch_catalog_skips_malformed_items() -> None:
    client = _FakePlatformClient(
        payload={
            "items": [
                {"id": "bad"},  # missing name
                None,
                {"id": "ok", "name": "Good", "price": None, "tags": None},
            ],
            "total": 3,
            "page": 1,
            "page_size": 20,
        }
    )
    coord = _coordinator(client)
    resp = coord.fetch_catalog()

    assert resp.error is None
    assert len(resp.items) == 1
    assert resp.items[0].id == "ok"
    assert resp.items[0].price == 0.0


def test_preview_loader_serves_memory_then_disk(tmp_path: Path, qapp) -> None:
    cache_dir = tmp_path / "previews"
    loader = MarketplacePreviewLoader(cache_dir=cache_dir, max_workers=2)

    url = "http://example.test/preview.png"
    data = b"\x89PNG\r\n\x1a\nfake"

    from features.marketplace.preview_loader import _cache_key

    path = cache_dir / f"{_cache_key(url)}.bin"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)

    received: list[tuple[str, bytes, int]] = []
    loader.loaded.connect(lambda iid, blob, gen: received.append((iid, blob, gen)))

    gen = loader.begin_generation()
    loader.request("item-1", url, gen)
    qapp.processEvents()

    assert len(received) == 1
    assert received[0][0] == "item-1"
    assert received[0][1] == data

    received.clear()
    loader.request("item-1", url, gen)
    qapp.processEvents()
    assert len(received) == 1
    assert received[0][1] == data

    loader.shutdown()


def test_preview_loader_drops_stale_generation(tmp_path: Path, qapp, monkeypatch) -> None:
    import time

    cache_dir = tmp_path / "previews"
    loader = MarketplacePreviewLoader(cache_dir=cache_dir, max_workers=1)

    def slow_fetch(_url: str) -> bytes | None:
        time.sleep(0.15)
        return b"late-bytes"

    monkeypatch.setattr(loader, "_fetch_url", slow_fetch)

    loaded: list[int] = []
    loader.loaded.connect(lambda _i, _b, gen: loaded.append(gen))

    gen1 = loader.begin_generation()
    loader.request("a", "http://example.test/a.png", gen1)
    gen2 = loader.begin_generation()
    assert gen2 != gen1

    deadline = time.time() + 1.0
    while time.time() < deadline:
        qapp.processEvents()
        time.sleep(0.05)

    assert loaded == []
    loader.shutdown()
