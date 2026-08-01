"""In-memory store for built-in domain preset overrides.

Factory recipes stay in code. User tweaks live only for the current app
session so they reset on restart unless the user Saves a video template.
Explicit Restore clears one preset slot back to factory.

Legacy on-disk ``video-presets/*.json`` files are ignored and removed once
so old auto-persisted overrides do not keep applying after upgrade.
"""

from __future__ import annotations

from typing import Any

from shared.lib.app_paths import get_video_presets_dir

DomainName = str  # particles | spectrum | background | logo | text

_MEMORY: dict[str, dict[str, Any]] = {}
_DISK_CLEANED = False


def _domain_bucket(domain: DomainName) -> dict[str, Any]:
    key = str(domain or "").strip()
    bucket = _MEMORY.get(key)
    if bucket is None:
        bucket = {}
        _MEMORY[key] = bucket
    return bucket


def _cleanup_legacy_disk_presets() -> None:
    global _DISK_CLEANED
    if _DISK_CLEANED:
        return
    _DISK_CLEANED = True
    root = get_video_presets_dir()
    if not root.is_dir():
        return
    try:
        for path in root.glob("*.json"):
            try:
                path.unlink()
            except OSError:
                continue
    except OSError:
        return


def list_domain_preset_overrides(domain: DomainName) -> dict[str, Any]:
    _cleanup_legacy_disk_presets()
    return dict(_domain_bucket(domain))


def get_domain_preset_override(domain: DomainName, preset_id: str) -> Any | None:
    _cleanup_legacy_disk_presets()
    key = str(preset_id or "").strip()
    if not key:
        return None
    stored = _domain_bucket(domain).get(key)
    return stored if stored is not None else None


def has_domain_preset_override(domain: DomainName, preset_id: str) -> bool:
    return get_domain_preset_override(domain, preset_id) is not None


def save_domain_preset_override(domain: DomainName, preset_id: str, payload: Any) -> None:
    _cleanup_legacy_disk_presets()
    key = str(preset_id or "").strip()
    if not key:
        return
    _domain_bucket(domain)[key] = payload


def clear_domain_preset_override(domain: DomainName, preset_id: str) -> bool:
    """Remove one preset override. Returns True if something was cleared."""
    _cleanup_legacy_disk_presets()
    key = str(preset_id or "").strip()
    if not key:
        return False
    bucket = _domain_bucket(domain)
    if key not in bucket:
        return False
    del bucket[key]
    return True


def clear_all_domain_preset_overrides(domain: DomainName) -> None:
    _cleanup_legacy_disk_presets()
    key = str(domain or "").strip()
    _MEMORY.pop(key, None)


def reset_domain_preset_memory_for_tests() -> None:
    """Test helper: wipe in-memory overrides and allow disk cleanup again."""
    global _DISK_CLEANED
    _MEMORY.clear()
    _DISK_CLEANED = False
