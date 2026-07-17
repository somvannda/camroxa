"""Effect pack runtime helpers — port of effectPackRuntime.ts."""

from __future__ import annotations

from typing import Any

from features.video.lib.merge_records import merge_records
from features.video.lib.template_value_utils import to_record, to_string_value

EFFECT_PACK_DOMAINS = ("spectrum", "background", "logo", "particles", "album", "title")


def read_template_effect_pack_map(template: dict[str, Any]) -> dict[str, dict[str, str]]:
    effect_packs = to_record(template.get("effectPacks"))
    result: dict[str, dict[str, str]] = {}
    for domain in EFFECT_PACK_DOMAINS:
        entry = effect_packs.get(domain)
        if not isinstance(entry, dict):
            continue
        pack_id = to_string_value(entry.get("packId"), "")
        version = to_string_value(entry.get("version"), "")
        if pack_id and version:
            result[domain] = {"packId": pack_id, "version": version}
    return result


def build_template_effect_pack_reference_patch(
    domain: str,
    selection: dict[str, str] | None,
) -> dict[str, Any]:
    return {
        "effectPacks": {
            domain: (
                {"packId": selection["packId"], "version": selection["version"]}
                if selection
                else None
            ),
        }
    }


def build_template_effect_pack_apply_patch(domain: str, item: dict[str, Any]) -> dict[str, Any]:
    reference = build_template_effect_pack_reference_patch(
        domain,
        {"packId": str(item["packId"]), "version": str(item["version"])},
    )
    template_patch = item.get("templatePatch")
    patch = dict(template_patch) if isinstance(template_patch, dict) else {}
    return merge_records(reference, patch)


def parse_effect_pack_catalog_value(value: str) -> dict[str, str] | None:
    parts = str(value or "").split("::", maxsplit=1)
    if len(parts) != 2:
        return None
    pack_id, version = parts[0].strip(), parts[1].strip()
    if not pack_id or not version:
        return None
    return {"packId": pack_id, "version": version}


def build_effect_pack_catalog_options(domain: str, catalog_items: list[dict[str, Any]]) -> list[dict[str, str]]:
    options: list[dict[str, str]] = []
    for item in catalog_items:
        if item.get("domain") != domain:
            continue
        if item.get("status") not in {"ready", "available"}:
            continue
        options.append(
            {
                "value": f"{item['packId']}::{item['version']}",
                "label": f"{item['name']} ({item['version']})",
            }
        )
    return options


def resolve_effect_pack_selection_status(
    domain: str,
    selection: dict[str, str] | None,
    catalog_items: list[dict[str, Any]],
) -> dict[str, Any]:
    if not selection:
        return {
            "domain": domain,
            "selection": None,
            "item": None,
            "status": "missing",
            "message": "No effect pack selected.",
        }

    exact = next(
        (
            item
            for item in catalog_items
            if item.get("domain") == domain
            and item.get("packId") == selection.get("packId")
            and item.get("version") == selection.get("version")
        ),
        None,
    )
    if exact is None:
        return {
            "domain": domain,
            "selection": selection,
            "item": None,
            "status": "missing",
            "message": (
                f"Selected {domain} pack {selection.get('packId')}@{selection.get('version')} "
                "is not installed."
            ),
        }

    status = str(exact.get("status") or "missing")
    if status in {"ready", "available"}:
        return {
            "domain": domain,
            "selection": selection,
            "item": exact,
            "status": status,
            "message": f"{exact.get('name')} ({exact.get('version')}) is available.",
        }

    issues = exact.get("issues") if isinstance(exact.get("issues"), list) else []
    reason = issues[0] if issues else f"{exact.get('name')} ({exact.get('version')}) is not available."
    return {
        "domain": domain,
        "selection": selection,
        "item": exact,
        "status": status,
        "message": str(reason),
    }


def selection_to_value(selection: dict[str, str] | None) -> str:
    if not selection:
        return ""
    return f"{selection['packId']}::{selection['version']}"
