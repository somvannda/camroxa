"""Tests for effect pack runtime helpers."""

from __future__ import annotations

from features.video.lib.effect_pack_runtime import (
    build_effect_pack_catalog_options,
    build_template_effect_pack_apply_patch,
    build_template_effect_pack_reference_patch,
    parse_effect_pack_catalog_value,
    read_template_effect_pack_map,
    resolve_effect_pack_selection_status,
)


def _catalog_item(**overrides: object) -> dict:
    item = {
        "packId": "pack.spectrum.alpha",
        "version": "1.0.0",
        "domain": "spectrum",
        "name": "Spectrum Alpha",
        "vendor": "CAMXORA",
        "description": "",
        "tags": [],
        "appVersionRange": "^0.1.0",
        "domainContractVersion": 1,
        "manifestVersion": 1,
        "enabled": True,
        "active": True,
        "status": "ready",
        "installedAt": "2026-07-04T00:00:00.000Z",
        "sourceType": "file",
        "sourceValue": "D:/packs/spectrum-alpha.zip",
        "directoryPath": "D:/packs/spectrum-alpha",
        "preview": None,
        "templatePatch": {
            "style": "flying-glow",
            "audioSettings": {
                "inputGain": 3.2,
            },
        },
        "issues": [],
    }
    item.update(overrides)
    return item


def test_read_template_effect_pack_map() -> None:
    result = read_template_effect_pack_map(
        {
            "effectPacks": {
                "spectrum": {"packId": "pack.spectrum.alpha", "version": "1.0.0"},
                "logo": {"packId": "pack.logo.beta", "version": "2.1.0"},
            }
        }
    )
    assert result == {
        "spectrum": {"packId": "pack.spectrum.alpha", "version": "1.0.0"},
        "logo": {"packId": "pack.logo.beta", "version": "2.1.0"},
    }


def test_build_template_effect_pack_apply_patch_merges_reference_and_payload() -> None:
    patch = build_template_effect_pack_apply_patch("spectrum", _catalog_item())
    assert patch == {
        "effectPacks": {
            "spectrum": {"packId": "pack.spectrum.alpha", "version": "1.0.0"},
        },
        "style": "flying-glow",
        "audioSettings": {"inputGain": 3.2},
    }


def test_resolve_effect_pack_selection_status() -> None:
    ready_item = _catalog_item()
    disabled_item = _catalog_item(
        enabled=False,
        status="disabled",
        issues=["Pack is disabled."],
    )

    ready_status = resolve_effect_pack_selection_status(
        "spectrum",
        {"packId": ready_item["packId"], "version": ready_item["version"]},
        [ready_item],
    )
    assert ready_status["status"] == "ready"
    assert ready_status["item"] == ready_item

    disabled_status = resolve_effect_pack_selection_status(
        "spectrum",
        {"packId": disabled_item["packId"], "version": disabled_item["version"]},
        [disabled_item],
    )
    assert disabled_status["status"] == "disabled"
    assert disabled_status["message"] == "Pack is disabled."

    missing_status = resolve_effect_pack_selection_status(
        "spectrum",
        {"packId": "missing.pack", "version": "9.9.9"},
        [ready_item],
    )
    assert missing_status["status"] == "missing"


def test_build_effect_pack_catalog_options_and_reference_patch() -> None:
    items = [
        _catalog_item(),
        _catalog_item(
            packId="pack.spectrum.beta",
            version="1.1.0",
            status="available",
            active=False,
        ),
        _catalog_item(
            packId="pack.spectrum.disabled",
            version="1.2.0",
            status="disabled",
            enabled=False,
        ),
    ]

    assert build_effect_pack_catalog_options("spectrum", items) == [
        {"value": "pack.spectrum.alpha::1.0.0", "label": "Spectrum Alpha (1.0.0)"},
        {"value": "pack.spectrum.beta::1.1.0", "label": "Spectrum Alpha (1.1.0)"},
    ]
    assert parse_effect_pack_catalog_value("pack.spectrum.alpha::1.0.0") == {
        "packId": "pack.spectrum.alpha",
        "version": "1.0.0",
    }
    assert build_template_effect_pack_reference_patch("background", None) == {
        "effectPacks": {"background": None},
    }
