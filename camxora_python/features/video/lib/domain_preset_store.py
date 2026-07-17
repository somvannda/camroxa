"""Local JSON store for built-in domain preset overrides.

Factory recipes stay in code. User tweaks are written under
``%LOCALAPPDATA%/Camxora/video-presets/{domain}.json`` and survive app
restarts. Explicit Restore clears one preset slot back to factory.
Saved video templates are unchanged — this store is independent of Save.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from shared.lib.app_paths import get_video_presets_dir

DomainName = str  # particles | spectrum | background | logo | text


def _domain_path(domain: DomainName) -> Path:
    return get_video_presets_dir() / f"{str(domain).strip()}.json"


def _read_domain_file(domain: DomainName) -> dict[str, Any]:
    path = _domain_path(domain)
    if not path.is_file():
        return {}
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _write_domain_file(domain: DomainName, payload: dict[str, Any]) -> None:
    path = _domain_path(domain)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def list_domain_preset_overrides(domain: DomainName) -> dict[str, Any]:
    return dict(_read_domain_file(domain))


def get_domain_preset_override(domain: DomainName, preset_id: str) -> Any | None:
    key = str(preset_id or "").strip()
    if not key:
        return None
    stored = _read_domain_file(domain).get(key)
    return stored if stored is not None else None


def has_domain_preset_override(domain: DomainName, preset_id: str) -> bool:
    return get_domain_preset_override(domain, preset_id) is not None


def save_domain_preset_override(domain: DomainName, preset_id: str, payload: Any) -> None:
    key = str(preset_id or "").strip()
    if not key:
        return
    data = _read_domain_file(domain)
    data[key] = payload
    _write_domain_file(domain, data)


def clear_domain_preset_override(domain: DomainName, preset_id: str) -> bool:
    """Remove one preset override. Returns True if something was cleared."""
    key = str(preset_id or "").strip()
    if not key:
        return False
    data = _read_domain_file(domain)
    if key not in data:
        return False
    del data[key]
    _write_domain_file(domain, data)
    return True


def clear_all_domain_preset_overrides(domain: DomainName) -> None:
    path = _domain_path(domain)
    if path.is_file():
        try:
            path.unlink()
        except OSError:
            return
