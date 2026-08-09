"""Minimal Plugin SDK loader (doc 11) — manifest + registry merge."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class StudioPlugin:
    id: str
    name: str
    version: str
    plugin_type: str
    root: Path
    manifest: dict[str, Any]


def discover_plugins(plugins_dir: Path) -> list[StudioPlugin]:
    plugins_dir.mkdir(parents=True, exist_ok=True)
    found: list[StudioPlugin] = []
    for manifest_path in plugins_dir.glob("*/manifest.json"):
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        pid = str(data.get("id") or "").strip()
        if not pid:
            continue
        found.append(
            StudioPlugin(
                id=pid,
                name=str(data.get("name") or pid),
                version=str(data.get("version") or "0.0.0"),
                plugin_type=str(data.get("type") or data.get("pluginType") or "unknown"),
                root=manifest_path.parent,
                manifest=data,
            )
        )
    return found


def plugin_catalog_entries(plugins: list[StudioPlugin]) -> list[dict[str, Any]]:
    """Expose plugin assets to Asset Library search as synthetic rows."""
    rows: list[dict[str, Any]] = []
    for plugin in plugins:
        assets = plugin.manifest.get("assets")
        if not isinstance(assets, list):
            rows.append(
                {
                    "id": plugin.id,
                    "category": "plugin",
                    "name": plugin.name,
                    "tags": (plugin.plugin_type,),
                    "ai_description": f"Plugin {plugin.name} v{plugin.version}",
                }
            )
            continue
        for asset in assets:
            if not isinstance(asset, dict):
                continue
            rows.append(
                {
                    "id": str(asset.get("id") or plugin.id),
                    "category": str(asset.get("category") or plugin.plugin_type).lower(),
                    "name": str(asset.get("name") or plugin.name),
                    "tags": tuple(asset.get("tags") or (plugin.plugin_type,)),
                    "ai_description": str(asset.get("description") or plugin.name),
                }
            )
    return rows
