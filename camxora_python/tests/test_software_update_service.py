from __future__ import annotations

import json
from pathlib import Path

import pytest

from shared.lib.software_update_persistence import (
    PHASE_FAILED,
    PHASE_INSTALLING,
    PersistedSoftwareUpdate,
    clear_all_update_markers,
    load_pending_update,
    load_update_status,
    save_pending_update,
)
from shared.services.software_update_service import SoftwareUpdateOffer, SoftwareUpdateService


@pytest.fixture()
def updates_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    work = tmp_path / "updates"
    work.mkdir()
    monkeypatch.setattr(
        "shared.lib.software_update_persistence.get_updates_work_dir",
        lambda: work,
    )
    return work


def test_parse_version() -> None:
    from shared.lib.version_compare import parse_version

    assert parse_version("2.5.0") == (2, 5, 0)
    assert parse_version("10") == (10, 0, 0)
    assert parse_version("\ufeff2.5.0") == (2, 5, 0)


def test_is_remote_version_newer() -> None:
    from shared.lib.version_compare import is_remote_version_newer

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


def test_force_update_blocks_dismiss(monkeypatch: pytest.MonkeyPatch, updates_dir: Path) -> None:
    del updates_dir
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
    pending = load_pending_update()
    assert pending is not None
    assert pending.version == "9.9.9"
    assert pending.mandatory is True


def test_persist_and_restore_in_progress_update(
    monkeypatch: pytest.MonkeyPatch,
    updates_dir: Path,
) -> None:
    monkeypatch.setattr(
        "shared.services.software_update_service.get_app_version",
        lambda: "1.0.14",
    )
    save_pending_update(
        PersistedSoftwareUpdate(
            version="1.0.16",
            download_url="https://example.com/CamxoraSetup-1.0.16.exe",
            mandatory=True,
            release_notes="notes",
            notification_id="n1",
            install_in_progress=True,
        )
    )
    (updates_dir / "update-status.json").write_text(
        json.dumps({"phase": PHASE_INSTALLING, "exit_code": 0}),
        encoding="utf-8",
    )

    finishing: list[bool] = []
    service = SoftwareUpdateService()
    service.install_finishing.connect(lambda: finishing.append(True))
    offer = service.restore_from_disk()
    assert offer is not None
    assert offer.version == "1.0.16"
    assert service.install_in_progress is True
    assert finishing == [True]
    service._stop_status_poll()


def test_restore_failed_status_emits_try_again(
    monkeypatch: pytest.MonkeyPatch,
    updates_dir: Path,
) -> None:
    monkeypatch.setattr(
        "shared.services.software_update_service.get_app_version",
        lambda: "1.0.14",
    )
    save_pending_update(
        PersistedSoftwareUpdate(
            version="1.0.16",
            download_url="https://example.com/CamxoraSetup-1.0.16.exe",
            mandatory=True,
            release_notes="",
            notification_id="n2",
            install_in_progress=True,
        )
    )
    (updates_dir / "update-status.json").write_text(
        json.dumps(
            {
                "phase": PHASE_FAILED,
                "exit_code": 1,
                "error": "Setup exited with code 1",
            }
        ),
        encoding="utf-8",
    )

    failures: list[str] = []
    service = SoftwareUpdateService()
    service.install_failed.connect(failures.append)
    offer = service.restore_from_disk()
    assert offer is not None
    assert service.install_in_progress is False
    assert failures
    assert "Setup exited" in failures[0]


def test_restore_clears_when_already_on_target(
    monkeypatch: pytest.MonkeyPatch,
    updates_dir: Path,
) -> None:
    monkeypatch.setattr(
        "shared.services.software_update_service.get_app_version",
        lambda: "1.0.16",
    )
    save_pending_update(
        PersistedSoftwareUpdate(
            version="1.0.16",
            download_url="https://example.com/CamxoraSetup-1.0.16.exe",
            mandatory=True,
            release_notes="",
            notification_id="n3",
            install_in_progress=True,
        )
    )
    service = SoftwareUpdateService()
    assert service.restore_from_disk() is None
    assert load_pending_update() is None
    assert load_update_status() is None
    clear_all_update_markers()
