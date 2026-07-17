"""Effect pack catalog provider protocol — local registry and future marketplace hook."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from features.video.lib.effect_pack_versioning import matches_app_version_range

APP_VERSION = "0.1.0"
DOMAIN_CONTRACT_VERSIONS = {
    "spectrum": 1,
    "background": 1,
    "logo": 1,
    "particles": 1,
}


@runtime_checkable
class EffectPackCatalogProvider(Protocol):
    def list_catalog(self) -> dict[str, Any]: ...

    def get_download_url(self, pack_id: str, version: str) -> str | None: ...


class LocalRegistryCatalogProvider:
    """Lists installed effect packs from the on-disk registry."""

    def __init__(self, *, registry_root: Path, app_version: str = APP_VERSION) -> None:
        self._registry_root = registry_root
        self._app_version = app_version

    @property
    def registry_root(self) -> Path:
        return self._registry_root

    def _registry_path(self) -> Path:
        return self._registry_root / "registry.json"

    def _packs_root(self) -> Path:
        return self._registry_root / "packs"

    def _ensure_layout(self) -> None:
        self._packs_root().mkdir(parents=True, exist_ok=True)

    def _read_registry(self) -> dict[str, Any]:
        self._ensure_layout()
        path = self._registry_path()
        if not path.is_file():
            return {"packs": {}}
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"packs": {}}
        if not isinstance(raw, dict) or not isinstance(raw.get("packs"), dict):
            return {"packs": {}}
        return raw

    def _build_catalog_item(
        self,
        record: dict[str, Any],
        version_record: dict[str, Any],
        *,
        issues: list[str] | None = None,
    ) -> dict[str, Any]:
        item_issues = list(issues or [])
        manifest = version_record.get("manifest") if isinstance(version_record.get("manifest"), dict) else {}
        relative_dir = str(version_record.get("relativeDir") or "")
        target_dir = (self._packs_root() / relative_dir).resolve()

        status = "available"
        if item_issues:
            status = "broken"
        elif not record.get("enabled", True):
            status = "disabled"
            item_issues.append("Pack is disabled.")
        elif not matches_app_version_range(
            self._app_version,
            str(manifest.get("appVersionRange") or "*"),
        ):
            status = "incompatible"
            item_issues.append(
                f"Pack requires app version {manifest.get('appVersionRange')}, "
                f"current app is {self._app_version}."
            )
        elif record.get("activeVersion") == version_record.get("version"):
            status = "ready"

        preview = manifest.get("preview") if isinstance(manifest.get("preview"), dict) else None
        payload = manifest.get("payload") if isinstance(manifest.get("payload"), dict) else {}
        template_patch = payload.get("templatePatch") if isinstance(payload.get("templatePatch"), dict) else {}

        return {
            "packId": record.get("packId"),
            "version": version_record.get("version"),
            "domain": manifest.get("domain"),
            "name": manifest.get("name"),
            "vendor": manifest.get("vendor"),
            "description": manifest.get("description") or "",
            "tags": manifest.get("tags") if isinstance(manifest.get("tags"), list) else [],
            "appVersionRange": manifest.get("appVersionRange") or "*",
            "domainContractVersion": manifest.get("domainContractVersion"),
            "manifestVersion": manifest.get("manifestVersion"),
            "enabled": bool(record.get("enabled", True)),
            "active": record.get("activeVersion") == version_record.get("version"),
            "status": status,
            "installedAt": version_record.get("installedAt"),
            "sourceType": version_record.get("sourceType"),
            "sourceValue": version_record.get("sourceValue"),
            "directoryPath": str(target_dir),
            "preview": preview,
            "templatePatch": template_patch,
            "issues": item_issues,
        }

    def list_catalog(self) -> dict[str, Any]:
        registry = self._read_registry()
        items: list[dict[str, Any]] = []
        for record in registry.get("packs", {}).values():
            if not isinstance(record, dict):
                continue
            versions = record.get("versions")
            if not isinstance(versions, dict):
                continue
            for version_record in versions.values():
                if not isinstance(version_record, dict):
                    continue
                issues: list[str] = []
                relative_dir = str(version_record.get("relativeDir") or "")
                target_dir = self._packs_root() / relative_dir
                if not target_dir.is_dir():
                    issues.append("Pack files are missing from local storage.")
                manifest = version_record.get("manifest")
                if isinstance(manifest, dict):
                    domain = str(manifest.get("domain") or "")
                    expected = DOMAIN_CONTRACT_VERSIONS.get(domain)
                    if expected and manifest.get("domainContractVersion") != expected:
                        issues.append(
                            f"{domain} pack contract {manifest.get('domainContractVersion')} "
                            f"is not supported; expected {expected}."
                        )
                items.append(self._build_catalog_item(record, version_record, issues=issues))

        items.sort(key=lambda item: f"{item.get('domain')}:{item.get('name')}:{item.get('version')}")
        return {"items": items}

    def get_download_url(self, pack_id: str, version: str) -> str | None:
        _ = (pack_id, version)
        return None
