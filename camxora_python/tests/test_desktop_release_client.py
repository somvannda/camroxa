from __future__ import annotations

from shared.services.desktop_release_client import (
    PublishedDesktopRelease,
    desktop_release_url_for_api_base,
    fetch_published_desktop_release,
)
from shared.services.software_update_service import SoftwareUpdateOffer
from shared.workers.software_update_check_worker import SoftwareUpdateCheckWorker


class _FakeResponse:
    def __init__(self, status_code: int, payload: object | None = None) -> None:
        self.status_code = status_code
        self._payload = payload

    @property
    def is_success(self) -> bool:
        return 200 <= self.status_code < 300

    def json(self) -> object:
        return self._payload


def test_desktop_release_url_for_api_base() -> None:
    assert (
        desktop_release_url_for_api_base("https://api.camxora.com/api/v1")
        == "https://api.camxora.com/api/v1/public/desktop-release"
    )


def test_fetch_published_desktop_release_success(monkeypatch) -> None:
    def fake_get(url: str, timeout: float = 8.0):
        assert url.endswith("/public/desktop-release")
        return _FakeResponse(
            200,
            {
                "version": "1.2.1",
                "download_url": "https://example.com/CamxoraSetup-1.2.1.exe",
                "release_notes": "notes",
                "mandatory": True,
                "published_at": "2026-08-08T00:00:00+00:00",
            },
        )

    monkeypatch.setattr("shared.services.desktop_release_client.httpx.get", fake_get)
    release = fetch_published_desktop_release("https://api.camxora.com/api/v1")
    assert release is not None
    assert release.version == "1.2.1"
    assert release.mandatory is True
    payload = release.as_update_payload()
    assert payload["notification_id"] == "startup-desktop-release"


def test_fetch_published_desktop_release_404(monkeypatch) -> None:
    monkeypatch.setattr(
        "shared.services.desktop_release_client.httpx.get",
        lambda *args, **kwargs: _FakeResponse(404),
    )
    assert fetch_published_desktop_release("https://api.camxora.com/api/v1") is None


def test_software_update_check_worker_emits_mandatory_offer(monkeypatch) -> None:
    monkeypatch.setattr(
        "shared.services.software_update_service.get_app_version",
        lambda: "1.2.0",
    )
    release = PublishedDesktopRelease(
        version="1.2.1",
        download_url="https://example.com/a.exe",
        release_notes="x",
        mandatory=True,
    )
    monkeypatch.setattr(
        "shared.workers.software_update_check_worker.fetch_published_desktop_release",
        lambda _url: release,
    )
    worker = SoftwareUpdateCheckWorker("https://api.camxora.com/api/v1")
    seen: list[object] = []
    worker.finished_with_offer.connect(seen.append)
    worker.run()
    assert len(seen) == 1
    assert isinstance(seen[0], SoftwareUpdateOffer)
    assert seen[0].version == "1.2.1"


def test_software_update_check_worker_skips_optional(monkeypatch) -> None:
    release = PublishedDesktopRelease(
        version="9.9.9",
        download_url="https://example.com/a.exe",
        release_notes="",
        mandatory=False,
    )
    monkeypatch.setattr(
        "shared.workers.software_update_check_worker.fetch_published_desktop_release",
        lambda _url: release,
    )
    worker = SoftwareUpdateCheckWorker("https://api.camxora.com/api/v1")
    seen: list[object] = []
    worker.finished_with_offer.connect(seen.append)
    worker.run()
    assert seen == [None]
