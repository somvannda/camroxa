"""Tests for local effect pack registry service."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from features.video.services.effect_pack_service import EffectPackService


def _build_manifest(**overrides: object) -> dict:
    manifest = {
        "manifestVersion": 1,
        "packId": "pack.spectrum.alpha",
        "name": "Spectrum Alpha",
        "vendor": "CAMXORA",
        "version": "1.0.0",
        "domain": "spectrum",
        "description": "Pack for tests",
        "tags": ["test"],
        "appVersionRange": "^0.1.0",
        "domainContractVersion": 1,
        "preview": {
            "title": "Spectrum Alpha",
            "summary": "Test pack",
            "accentColor": "#ff00ff",
        },
        "payload": {
            "templatePatch": {
                "style": "flying-glow",
                "audioSettings": {"inputGain": 2.5},
            },
        },
    }
    manifest.update(overrides)
    return manifest


def _write_pack_zip(path: Path, manifest: dict) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("pack/manifest.json", json.dumps(manifest))
        archive.writestr("pack/marker.txt", "marker")


@pytest.fixture()
def registry_root(tmp_path: Path) -> Path:
    return tmp_path / "effect-packs"


def test_install_list_and_remove_effect_pack(registry_root: Path) -> None:
    service = EffectPackService(registry_root=registry_root, app_version="0.1.0")
    zip_path = registry_root.parent / "pack.zip"
    registry_root.mkdir(parents=True, exist_ok=True)
    _write_pack_zip(zip_path, _build_manifest())

    install_result = service.install_from_file(str(zip_path))
    assert install_result["ok"] is True
    assert install_result["item"] is not None
    assert install_result["item"]["packId"] == "pack.spectrum.alpha"
    assert install_result["item"]["status"] == "ready"

    catalog = service.list_catalog()
    assert len(catalog["items"]) == 1
    assert catalog["items"][0]["packId"] == "pack.spectrum.alpha"

    remove_result = service.remove_version("pack.spectrum.alpha", "1.0.0")
    assert remove_result["ok"] is True
    assert service.list_catalog()["items"] == []


def test_rejects_unsupported_domain_contract(registry_root: Path) -> None:
    service = EffectPackService(registry_root=registry_root, app_version="0.1.0")
    zip_path = registry_root.parent / "bad-pack.zip"
    registry_root.mkdir(parents=True, exist_ok=True)
    _write_pack_zip(
        zip_path,
        _build_manifest(domainContractVersion=99),
    )

    result = service.install_from_file(str(zip_path))
    assert result["ok"] is False
    assert "contract" in str(result["error"]).lower()
