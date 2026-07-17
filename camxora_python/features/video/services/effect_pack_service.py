"""Local effect pack registry — port of Electron effectPackRegistry.ts."""

from __future__ import annotations

import json
import shutil
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from features.video.lib.effect_pack_manifest import validate_effect_pack_manifest
from features.video.lib.effect_pack_versioning import matches_app_version_range
from features.video.services.effect_pack_catalog_provider import (
    APP_VERSION,
    EffectPackCatalogProvider,
    LocalRegistryCatalogProvider,
)
from shared.lib.app_paths import get_effect_packs_dir


class EffectPackService:
    def __init__(
        self,
        *,
        registry_root: Path | None = None,
        app_version: str = APP_VERSION,
        catalog_provider: EffectPackCatalogProvider | None = None,
    ) -> None:
        self._registry_root = registry_root or get_effect_packs_dir()
        self._app_version = app_version
        self._catalog_provider = catalog_provider or LocalRegistryCatalogProvider(
            registry_root=self._registry_root,
            app_version=self._app_version,
        )

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

    def _write_registry(self, registry: dict[str, Any]) -> None:
        self._ensure_layout()
        path = self._registry_path()
        temp_path = path.with_suffix(".json.tmp")
        temp_path.write_text(json.dumps(registry, indent=2), encoding="utf-8")
        temp_path.replace(path)

    def _find_manifest_path(self, extract_dir: Path) -> Path:
        manifests = list(extract_dir.rglob("manifest.json"))
        if len(manifests) != 1:
            raise ValueError("Effect pack zip must contain exactly one manifest.json file.")
        return manifests[0]

    @property
    def catalog_provider(self) -> EffectPackCatalogProvider:
        return self._catalog_provider

    def list_catalog(self) -> dict[str, Any]:
        return self._catalog_provider.list_catalog()

    def get_download_url(self, pack_id: str, version: str) -> str | None:
        return self._catalog_provider.get_download_url(pack_id, version)

    def install_from_file(self, zip_path: str) -> dict[str, Any]:
        source = Path(zip_path).resolve()
        if not source.is_file():
            return {"ok": False, "item": None, "replacedVersion": None, "error": "Selected effect pack file is not valid."}

        staging_dir = Path(tempfile.mkdtemp(prefix="camxora-effect-pack-"))
        extract_dir = staging_dir / "extract"
        backup_dir = staging_dir / "backup"
        try:
            extract_dir.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(source, "r") as archive:
                archive.extractall(extract_dir)

            manifest_path = self._find_manifest_path(extract_dir)
            manifest = validate_effect_pack_manifest(json.loads(manifest_path.read_text(encoding="utf-8")))

            if not matches_app_version_range(self._app_version, manifest["appVersionRange"]):
                return {
                    "ok": False,
                    "item": None,
                    "replacedVersion": None,
                    "error": (
                        f"Pack requires app version {manifest['appVersionRange']}, "
                        f"current app is {self._app_version}."
                    ),
                }

            content_root = manifest_path.parent
            version_dir = Path(manifest["packId"]) / manifest["version"]
            target_dir = (self._packs_root() / version_dir).resolve()
            had_existing = target_dir.is_dir()
            if had_existing:
                if backup_dir.exists():
                    shutil.rmtree(backup_dir)
                shutil.move(str(target_dir), str(backup_dir))

            target_dir.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(content_root, target_dir, dirs_exist_ok=True)

            try:
                registry = self._read_registry()
                packs = registry.setdefault("packs", {})
                existing = packs.get(manifest["packId"])
                replaced_version = None
                if isinstance(existing, dict) and existing.get("activeVersion") not in (None, manifest["version"]):
                    replaced_version = existing.get("activeVersion")

                version_record = {
                    "version": manifest["version"],
                    "relativeDir": version_dir.as_posix(),
                    "installedAt": datetime.now(timezone.utc).isoformat(),
                    "sourceType": "file",
                    "sourceValue": str(source),
                    "manifest": manifest,
                }

                if isinstance(existing, dict):
                    versions = dict(existing.get("versions") or {})
                    versions[manifest["version"]] = version_record
                    packs[manifest["packId"]] = {
                        **existing,
                        "enabled": True,
                        "activeVersion": manifest["version"],
                        "previousVersion": replaced_version or existing.get("previousVersion"),
                        "versions": versions,
                    }
                else:
                    packs[manifest["packId"]] = {
                        "packId": manifest["packId"],
                        "enabled": True,
                        "activeVersion": manifest["version"],
                        "previousVersion": None,
                        "versions": {manifest["version"]: version_record},
                    }
                self._write_registry(registry)
            except Exception:
                shutil.rmtree(target_dir, ignore_errors=True)
                if had_existing and backup_dir.is_dir():
                    shutil.move(str(backup_dir), str(target_dir))
                raise

            catalog = self.list_catalog()
            item = next(
                (
                    entry
                    for entry in catalog["items"]
                    if entry.get("packId") == manifest["packId"] and entry.get("version") == manifest["version"]
                ),
                None,
            )
            return {"ok": True, "item": item, "replacedVersion": replaced_version}
        except Exception as error:
            return {
                "ok": False,
                "item": None,
                "replacedVersion": None,
                "error": str(error) or "Unable to install effect pack.",
            }
        finally:
            shutil.rmtree(staging_dir, ignore_errors=True)

    def set_enabled(self, pack_id: str, *, enabled: bool) -> dict[str, Any]:
        registry = self._read_registry()
        record = registry.get("packs", {}).get(pack_id)
        if not isinstance(record, dict):
            return {"ok": False, "item": None, "error": "Effect pack is not installed."}
        record["enabled"] = enabled
        registry["packs"][pack_id] = record
        self._write_registry(registry)
        catalog = self.list_catalog()
        item = next(
            (entry for entry in catalog["items"] if entry.get("packId") == pack_id and entry.get("active")),
            None,
        )
        return {"ok": True, "item": item}

    def activate_version(self, pack_id: str, version: str) -> dict[str, Any]:
        registry = self._read_registry()
        record = registry.get("packs", {}).get(pack_id)
        if not isinstance(record, dict):
            return {"ok": False, "item": None, "error": "Effect pack is not installed."}
        version_record = (record.get("versions") or {}).get(version)
        if not isinstance(version_record, dict):
            return {"ok": False, "item": None, "error": "Requested effect pack version is not installed."}
        manifest = version_record.get("manifest")
        if isinstance(manifest, dict) and not matches_app_version_range(
            self._app_version,
            str(manifest.get("appVersionRange") or "*"),
        ):
            return {"ok": False, "item": None, "error": "Requested effect pack version is not compatible with this app."}

        record["activeVersion"] = version
        registry["packs"][pack_id] = record
        self._write_registry(registry)
        catalog = self.list_catalog()
        item = next(
            (
                entry
                for entry in catalog["items"]
                if entry.get("packId") == pack_id and entry.get("version") == version
            ),
            None,
        )
        return {"ok": True, "item": item}

    def remove_version(self, pack_id: str, version: str) -> dict[str, Any]:
        registry = self._read_registry()
        record = registry.get("packs", {}).get(pack_id)
        if not isinstance(record, dict):
            return {"ok": False, "error": "Effect pack is not installed."}
        versions = dict(record.get("versions") or {})
        version_record = versions.pop(version, None)
        if not isinstance(version_record, dict):
            return {"ok": False, "error": "Requested effect pack version is not installed."}

        relative_dir = str(version_record.get("relativeDir") or "")
        target_dir = self._packs_root() / relative_dir
        shutil.rmtree(target_dir, ignore_errors=True)

        if not versions:
            registry.get("packs", {}).pop(pack_id, None)
        else:
            if record.get("activeVersion") == version:
                record["activeVersion"] = next(iter(versions.keys()))
            record["versions"] = versions
            registry["packs"][pack_id] = record

        self._write_registry(registry)
        return {"ok": True}
