from __future__ import annotations

from uuid import uuid4

import httpx
import pytest

from platform_api.services.batch_service import BatchService


class _FakeRepo:
    def __init__(self, rows):
        self._rows = rows
        self.marked: list[tuple[str, str]] = []

    async def list_suno_download_health_candidates(self, *, user_id, limit):
        return list(self._rows)

    async def mark_suno_download_unavailable(self, *, task_id, variant, unavailable=True):
        self.marked.append((str(task_id), variant))


class _FakeResponse:
    def __init__(self, status: int) -> None:
        self.status_code = status

    async def aiter_bytes(self):
        yield b"ID3\x04\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"


class _FakeStream:
    def __init__(self, status: int) -> None:
        self._status = status

    async def __aenter__(self) -> _FakeResponse:
        return _FakeResponse(self._status)

    async def __aexit__(self, *exc) -> bool:
        return False


class _FakeClient:
    def __init__(self, statuses: list[int]) -> None:
        self._statuses = list(statuses)

    async def __aenter__(self) -> "_FakeClient":
        return self

    async def __aexit__(self, *exc) -> bool:
        return False

    def stream(self, method: str, url: str) -> _FakeStream:
        status = self._statuses.pop(0) if self._statuses else 200
        return _FakeStream(status)


def _service(repo: _FakeRepo) -> BatchService:
    return BatchService(
        batch_repo=repo,
        credit_service=None,  # type: ignore[arg-type]
        pricing_service=None,  # type: ignore[arg-type]
        generation_service=None,  # type: ignore[arg-type]
        profile_repo=None,  # type: ignore[arg-type]
        ai_routing_service=None,
    )


@pytest.mark.asyncio
async def test_probe_marks_dead_url_and_backs_up_live_url(monkeypatch) -> None:
    task_id = uuid4()
    repo = _FakeRepo(
        [
            {
                "id": task_id,
                "audio_url_ok": "https://cdn.example.com/ok.mp3",
                "audio_url_alt": "https://cdn.example.com/alt.mp3",
                "downloaded_ok": False,
                "downloaded_alt": False,
                "download_unavailable_ok": False,
                "download_unavailable_alt": False,
            }
        ]
    )
    service = _service(repo)
    backups: list[str] = []
    monkeypatch.setattr(service, "_load_b2_download_coverage", lambda ids: _empty())
    monkeypatch.setattr(service, "_schedule_download_backup", lambda tid: backups.append(str(tid)))
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: _FakeClient([404, 200]))

    marked = await service.probe_dead_suno_downloads(user_id=str(uuid4()))

    assert marked == 1
    assert repo.marked == [(str(task_id), "primary")]
    assert backups == [str(task_id)]


@pytest.mark.asyncio
async def test_probe_keeps_channel_with_b2_copy(monkeypatch) -> None:
    task_id = uuid4()
    repo = _FakeRepo(
        [
            {
                "id": task_id,
                "audio_url_ok": "https://cdn.example.com/ok.mp3",
                "audio_url_alt": None,
                "downloaded_ok": False,
                "downloaded_alt": False,
                "download_unavailable_ok": False,
                "download_unavailable_alt": False,
            }
        ]
    )
    service = _service(repo)
    monkeypatch.setattr(
        service,
        "_load_b2_download_coverage",
        lambda ids: _coverage((str(task_id), "primary")),
    )
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: _FakeClient([404]))

    marked = await service.probe_dead_suno_downloads(user_id=str(uuid4()))

    assert marked == 0
    assert repo.marked == []


@pytest.mark.asyncio
async def test_probe_is_inconclusive_on_network_error(monkeypatch) -> None:
    task_id = uuid4()
    repo = _FakeRepo(
        [
            {
                "id": task_id,
                "audio_url_ok": "https://cdn.example.com/ok.mp3",
                "audio_url_alt": None,
                "downloaded_ok": False,
                "downloaded_alt": False,
                "download_unavailable_ok": False,
                "download_unavailable_alt": False,
            }
        ]
    )
    service = _service(repo)
    monkeypatch.setattr(service, "_load_b2_download_coverage", lambda ids: _empty())
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: _FakeClient([503]))

    marked = await service.probe_dead_suno_downloads(user_id=str(uuid4()))

    assert marked == 0
    assert repo.marked == []


class _FakeStorage:
    @staticmethod
    def from_config(config):
        return _FakeStorage()

    async def get_signed_get_url(self, key: str, *, cache_bust: bool = False) -> str:
        return f"https://cdn.test/{key.lstrip('/')}"


@pytest.mark.asyncio
async def test_resolve_pending_b2_urls_skips_packaged_and_encrypted(monkeypatch) -> None:
    from types import SimpleNamespace

    from platform_api import dependencies as deps
    from platform_api.repositories import streaming_repo as sr
    from platform_api.services import storage_service as ss
    from platform_api.services import streaming_config_service as scs

    task_id = uuid4()
    monkeypatch.setattr(deps, "get_db_pool", lambda: object())
    monkeypatch.setattr(
        scs,
        "resolve_streaming_storage_config",
        lambda pool: _aresolve(SimpleNamespace(configured=True, cdn_base_url="https://cdn.test")),
    )

    class _Repo:
        def __init__(self, pool):
            pass

        async def get_track_storage_keys_for_suno_tasks(self, ids):
            return {
                (str(task_id), "ok"): "catalog/plain-ok.mp3",
                (str(task_id), "alt"): "catalog/secret-alt.cxa",
            }

    monkeypatch.setattr(sr, "StreamingRepository", _Repo)
    monkeypatch.setattr(ss, "StorageService", _FakeStorage)

    service = _service(_FakeRepo([]))

    async def _packaged(pool, ids):
        return set()

    monkeypatch.setattr(service, "_load_packaged_variants", _packaged)

    urls = await service._resolve_pending_b2_urls([{"id": task_id}])

    assert urls == {(str(task_id), "ok"): "https://cdn.test/catalog/plain-ok.mp3"}


async def _aresolve(value):
    return value


async def _empty():
    return set()


async def _coverage(item):
    return {item}
