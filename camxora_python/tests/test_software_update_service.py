from __future__ import annotations

import pytest

from shared.lib.version_compare import is_remote_version_newer, parse_version
from shared.services.software_update_service import SoftwareUpdateOffer, SoftwareUpdateService


def test_parse_version() -> None:
    assert parse_version("2.5.0") == (2, 5, 0)
    assert parse_version("10") == (10, 0, 0)
    assert parse_version("\ufeff2.5.0") == (2, 5, 0)


def test_is_remote_version_newer() -> None:
    assert is_remote_version_newer("0.1.0", "2.5.0")
    assert not is_remote_version_newer("2.5.0", "2.5.0")
    assert not is_remote_version_newer("3.0.0", "2.5.0")
    assert not is_remote_version_newer("\ufeff2.5.0", "2.5.0")


def test_software_update_offer_ignores_same_or_older_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "shared.services.software_update_service.get_app_version",
        lambda: "2.5.0",
    )
    assert SoftwareUpdateOffer.from_payload({"version": "0.1.0", "mandatory": True}) is None
    assert SoftwareUpdateOffer.from_payload({"version": "2.5.0", "mandatory": True}) is None


def test_force_update_blocks_dismiss(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "shared.services.software_update_service.get_app_version",
        lambda: "0.1.0",
    )
    service = SoftwareUpdateService()
    offer = service.apply_push_payload(
        {
            "version": "9.9.9",
            "download_url": "https://example.com/Camxora.exe",
            "mandatory": True,
            "notification_id": "update-1",
        }
    )
    assert isinstance(offer, SoftwareUpdateOffer)
    assert service.should_block_app()
    assert not service.can_dismiss("update-1")
