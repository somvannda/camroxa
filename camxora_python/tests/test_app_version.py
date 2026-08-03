from __future__ import annotations

from pathlib import Path

import pytest

from shared.constants import app_version
from shared.lib.version_compare import is_remote_version_newer, normalize_version_text, parse_version
from shared.services.software_update_service import SoftwareUpdateOffer, SoftwareUpdateService


def test_get_app_version_reads_pyproject_in_development(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(app_version, "is_frozen_runtime", lambda: False)
    version = app_version.get_app_version()
    assert version == "1.0.15"


def test_get_app_version_prefers_bundled_file_when_frozen(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resources = tmp_path / "_internal" / "resources"
    resources.mkdir(parents=True)
    (resources / "app-version.txt").write_text("9.9.9", encoding="utf-8")

    monkeypatch.setattr(app_version, "is_frozen_runtime", lambda: True)
    monkeypatch.setattr(app_version, "get_install_dir", lambda: tmp_path)

    assert app_version.get_app_version() == "9.9.9"


def test_get_app_version_strips_utf8_bom_when_frozen(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resources = tmp_path / "_internal" / "resources"
    resources.mkdir(parents=True)
    # Mimic Windows PowerShell Set-Content -Encoding utf8
    (resources / "app-version.txt").write_bytes(b"\xef\xbb\xbf0.2.5")

    monkeypatch.setattr(app_version, "is_frozen_runtime", lambda: True)
    monkeypatch.setattr(app_version, "get_install_dir", lambda: tmp_path)

    assert app_version.get_app_version() == "0.2.5"


def test_parse_version_ignores_bom_and_leading_v() -> None:
    assert parse_version("\ufeff0.2.5") == (0, 2, 5)
    assert parse_version("v0.2.5") == (0, 2, 5)
    assert normalize_version_text("\ufeffv0.2.5") == "0.2.5"
    assert not is_remote_version_newer("\ufeff0.2.5", "0.2.5")


def test_software_update_offer_ignores_same_version(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "shared.services.software_update_service.get_app_version",
        lambda: "0.2.5",
    )
    assert SoftwareUpdateOffer.from_payload({"version": "0.2.5", "mandatory": True}) is None


def test_should_block_clears_stale_equal_version(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "shared.services.software_update_service.get_app_version",
        lambda: "0.2.5",
    )
    service = SoftwareUpdateService()
    service._pending = SoftwareUpdateOffer(
        version="0.2.5",
        download_url="https://example.com/CamxoraSetup.exe",
        mandatory=True,
        release_notes="notes",
        notification_id="update-1",
    )
    assert not service.should_block_app()
    assert service.pending is None