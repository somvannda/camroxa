"""Tests for music-web KH-only geo middleware."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from platform_api.middleware.geo_access import (
    MusicWebGeoMiddleware,
    geo_is_allowed,
    music_web_geo_in_scope,
)


def _app() -> FastAPI:
    application = FastAPI()
    application.add_middleware(MusicWebGeoMiddleware)

    @application.get("/api/v1/web-music/quota")
    async def quota() -> dict[str, bool]:
        return {"ok": True}

    @application.post("/api/v1/generation/suno")
    async def suno() -> dict[str, bool]:
        return {"ok": True}

    @application.get("/health")
    async def health() -> dict[str, bool]:
        return {"ok": True}

    @application.get("/api/v1/public/streaming/tracks/{track_id}/stream")
    async def stream_track(track_id: str):
        async def chunks():
            yield b"ID3"
            yield b"fake"

        from starlette.responses import StreamingResponse

        return StreamingResponse(chunks(), media_type="audio/mpeg")

    return application


@pytest.fixture
def enforce_geo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "platform_api.middleware.geo_access.is_music_web_geo_enforced",
        lambda: True,
    )


@pytest.fixture
async def client(enforce_geo: None):
    transport = ASGITransport(app=_app())
    async with AsyncClient(transport=transport, base_url="http://test") as session:
        yield session


def test_geo_allows_kh_only() -> None:
    assert geo_is_allowed("KH", allowed="KH")
    assert not geo_is_allowed("US", allowed="KH")
    assert not geo_is_allowed("T1", allowed="KH")
    assert not geo_is_allowed("XX", allowed="KH")
    assert not geo_is_allowed("", allowed="KH")


def test_web_music_path_in_scope_on_api_host() -> None:
    from starlette.requests import Request

    async def receive() -> dict:
        return {"type": "http.request"}

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "https",
        "path": "/api/v1/web-music/generate",
        "raw_path": b"/api/v1/web-music/generate",
        "query_string": b"",
        "headers": [(b"host", b"api.camxora.com")],
        "client": ("1.2.3.4", 1234),
        "server": ("api.camxora.com", 443),
    }
    request = Request(scope, receive)
    assert music_web_geo_in_scope(request) is True


@pytest.mark.asyncio
async def test_kh_header_allows_web_music(client: AsyncClient) -> None:
    resp = await client.get(
        "/api/v1/web-music/quota",
        headers={"Host": "music.camxora.com", "CF-IPCountry": "KH"},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_us_header_blocks_web_music(client: AsyncClient) -> None:
    resp = await client.get(
        "/api/v1/web-music/quota",
        headers={"Host": "music.camxora.com", "CF-IPCountry": "US"},
    )
    assert resp.status_code == 403
    body = resp.json()
    assert body["error"]["code"] == "GEO_BLOCKED"


@pytest.mark.asyncio
async def test_tor_and_missing_country_blocked_behind_cloudflare(client: AsyncClient) -> None:
    missing = await client.get(
        "/api/v1/web-music/quota",
        headers={"Host": "music.sandbox.camxora.com", "CF-Connecting-IP": "1.2.3.4"},
    )
    assert missing.status_code == 403
    tor = await client.get(
        "/api/v1/web-music/quota",
        headers={"Host": "music.camxora.com", "CF-IPCountry": "T1"},
    )
    assert tor.status_code == 403


@pytest.mark.asyncio
async def test_no_cloudflare_headers_allowed_on_origin(client: AsyncClient) -> None:
    resp = await client.get(
        "/api/v1/web-music/quota",
        headers={"Host": "music.sandbox.camxora.com"},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_api_host_web_music_still_geo_checked(client: AsyncClient) -> None:
    resp = await client.get(
        "/api/v1/web-music/quota",
        headers={"Host": "api.camxora.com", "CF-IPCountry": "US"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_desktop_suno_not_geo_checked(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/generation/suno",
        headers={"Host": "api.camxora.com", "CF-IPCountry": "US"},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_health_exempt(client: AsyncClient) -> None:
    resp = await client.get("/health", headers={"Host": "music.camxora.com"})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_geo_off_allows_foreign(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "platform_api.middleware.geo_access.is_music_web_geo_enforced",
        lambda: False,
    )
    transport = ASGITransport(app=_app())
    async with AsyncClient(transport=transport, base_url="http://test") as session:
        resp = await session.get(
            "/api/v1/web-music/quota",
            headers={"Host": "music.camxora.com", "CF-IPCountry": "US"},
        )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_geo_pass_through_does_not_buffer_audio(client: AsyncClient) -> None:
    resp = await client.get(
        "/api/v1/public/streaming/tracks/441cb4bf-f013-4c88-8ea1-9d17499b1762/stream",
        headers={"Host": "music.sandbox.camxora.com"},
    )
    assert resp.status_code == 200
    assert resp.content == b"ID3fake"
