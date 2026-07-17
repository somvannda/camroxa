"""Effect pack manifest validation — subset of effectPackContracts.ts."""

from __future__ import annotations

import re
from typing import Any

from features.video.lib.template_value_utils import to_record, to_string_value

EFFECT_PACK_DOMAIN_CONTRACT_VERSIONS = {
    "spectrum": 1,
    "background": 1,
    "logo": 1,
    "particles": 1,
    "album": 1,
    "title": 1,
}

_PACK_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


def validate_effect_pack_manifest(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("Effect pack manifest must be a JSON object.")

    manifest_version = raw.get("manifestVersion")
    if manifest_version != 1:
        raise ValueError("Unsupported effect pack manifest version.")

    pack_id = to_string_value(raw.get("packId"), "")
    if not _PACK_ID_PATTERN.match(pack_id):
        raise ValueError("Effect pack manifest packId is invalid.")

    domain = to_string_value(raw.get("domain"), "")
    if domain not in EFFECT_PACK_DOMAIN_CONTRACT_VERSIONS:
        raise ValueError(f"Unsupported effect pack domain: {domain}")

    domain_contract_version = raw.get("domainContractVersion")
    expected = EFFECT_PACK_DOMAIN_CONTRACT_VERSIONS[domain]
    if domain_contract_version != expected:
        raise ValueError(
            f"{domain} pack contract {domain_contract_version} is not supported; expected {expected}."
        )

    name = to_string_value(raw.get("name"), "")
    vendor = to_string_value(raw.get("vendor"), "")
    version = to_string_value(raw.get("version"), "")
    if not name or not vendor or not version:
        raise ValueError("Effect pack manifest requires name, vendor, and version.")

    payload = to_record(raw.get("payload"))
    template_patch = payload.get("templatePatch")
    if not isinstance(template_patch, dict):
        raise ValueError("Effect pack manifest payload.templatePatch must be an object.")

    app_version_range = to_string_value(raw.get("appVersionRange"), "*") or "*"

    return {
        "manifestVersion": 1,
        "packId": pack_id,
        "name": name,
        "vendor": vendor,
        "version": version,
        "domain": domain,
        "domainContractVersion": expected,
        "appVersionRange": app_version_range,
        "description": to_string_value(raw.get("description"), ""),
        "tags": list(raw.get("tags")) if isinstance(raw.get("tags"), list) else [],
        "preview": raw.get("preview") if isinstance(raw.get("preview"), dict) else None,
        "payload": {"templatePatch": template_patch},
    }
