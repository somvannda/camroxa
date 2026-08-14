"""Per-machine workspace folder roots for the signed-in account.

Absolute media paths (``sunoOutputDir``, ``downloadsDir``, …) are inherently
machine-specific, but historically lived only in account-wide
``user_settings``. Logging into the same account on a second PC replayed the
first machine's drive letters / Windows profile paths.

This module stores those path keys under
``%LOCALAPPDATA%\\Camxora\\users\\{userId}\\device-workspace-paths.json`` —
already machine-local via LOCALAPPDATA — so each PC keeps its own roots.
Absolute media roots are **not** account settings; the API plans portable
``channel\\date_album`` run keys and each desktop joins its own Suno root.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from shared.lib.path_locality import is_foreign_windows_profile_path
from shared.lib.workspace_defaults import (
    default_workspace_paths,
    is_usable_workspace_path,
    workspace_paths_equivalent,
)
from shared.services.local_user_scope import get_user_workspace_dir

# Imported lazily in hydrate to avoid cycles with workspace_defaults_sync.

# Folder roots only — ffmpeg is resolved separately via bundled/hint logic.
DEVICE_MEDIA_PATH_KEYS = (
    "downloadsDir",
    "sunoOutputDir",
    "mergedDir",
    "imageBackgroundSamplesDir",
    "imageThumbnailSamplesDir",
    "imageOutputDir",
)

_STORE_NAME = "device-workspace-paths.json"


def _normalize_stored_path(value: str) -> str:
    """Normalize path text for Windows storage (keep drive letters consistent)."""
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        import os

        return os.path.normpath(text)
    except OSError:
        return text.replace("/", "\\")


def _read_device_workspace_payload(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(parsed, dict):
        return {}
    out: dict[str, str] = {}
    for key in DEVICE_MEDIA_PATH_KEYS:
        value = str(parsed.get(key) or "").strip()
        if value:
            out[key] = value
    return out


def get_device_workspace_paths_path(user_id: str | None = None) -> Path:
    return get_user_workspace_dir(user_id) / _STORE_NAME


def get_legacy_device_workspace_paths_path() -> Path:
    """Pre-login / pre-scoping store at ``%LOCALAPPDATA%\\Camxora\\``."""
    from shared.lib.app_paths import get_user_data_dir

    return get_user_data_dir() / _STORE_NAME


def load_device_workspace_paths(user_id: str | None = None) -> dict[str, str]:
    path = get_device_workspace_paths_path(user_id)
    loaded = _read_device_workspace_payload(path)
    if loaded:
        return loaded
    legacy = get_legacy_device_workspace_paths_path()
    try:
        if legacy.resolve() != path.resolve():
            return _read_device_workspace_payload(legacy)
    except OSError:
        if str(legacy) != str(path):
            return _read_device_workspace_payload(legacy)
    return {}


def _prefer_custom_device_paths(primary: dict[str, str], fallback: dict[str, str]) -> dict[str, str]:
    """Merge stores; a saved custom folder beats a machine-default AppData path."""
    defaults = default_workspace_paths()
    out = dict(primary)
    for key in DEVICE_MEDIA_PATH_KEYS:
        current = str(out.get(key) or "").strip()
        extra = str(fallback.get(key) or "").strip()
        if not extra:
            continue
        if not current:
            out[key] = extra
            continue
        default = str(defaults.get(key) or "")
        if workspace_paths_equivalent(current, default) and not workspace_paths_equivalent(extra, default):
            out[key] = extra
    return out


def migrate_legacy_device_workspace_paths(user_id: str | None = None) -> None:
    """Move/merge root ``device-workspace-paths.json`` into the signed-in user folder.

    Account scoping stores this file under ``users/{userId}/``. If it was written
    while no user was active (or left at the Camxora root after an upgrade),
    login used to skip it whenever the scoped folder already had other files —
    then startup seeded AppData ``Media\\Suno`` and overwrote Preferences.
    """
    scoped_path = get_device_workspace_paths_path(user_id)
    legacy_path = get_legacy_device_workspace_paths_path()
    try:
        if legacy_path.resolve() == scoped_path.resolve():
            return
    except OSError:
        if str(legacy_path) == str(scoped_path):
            return
    if not legacy_path.is_file():
        return
    merged = _prefer_custom_device_paths(
        _read_device_workspace_payload(scoped_path),
        _read_device_workspace_payload(legacy_path),
    )
    if not merged:
        return
    try:
        scoped_path.parent.mkdir(parents=True, exist_ok=True)
        scoped_path.write_text(json.dumps(merged, indent=2), encoding="utf-8")
        legacy_path.unlink()
    except OSError:
        return


def save_device_workspace_paths(
    paths: dict[str, Any] | None,
    user_id: str | None = None,
    *,
    replace_machine_defaults: bool = True,
) -> dict[str, str]:
    """Persist media path keys from ``paths`` into the local device store."""
    payload: dict[str, str] = {}
    source = dict(paths or {})
    existing = load_device_workspace_paths(user_id)
    defaults = default_workspace_paths()
    for key in DEVICE_MEDIA_PATH_KEYS:
        value = _normalize_stored_path(str(source.get(key) or ""))
        if value:
            saved = str(existing.get(key) or "").strip()
            default = str(defaults.get(key) or "")
            if (
                not replace_machine_defaults
                and saved
                and workspace_paths_equivalent(value, default)
                and not workspace_paths_equivalent(saved, default)
            ):
                payload[key] = _normalize_stored_path(saved) or saved
                continue
            payload[key] = value
        elif key in existing:
            payload[key] = _normalize_stored_path(existing[key]) or existing[key]
    if not payload:
        return {}
    target = get_device_workspace_paths_path(user_id)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except OSError:
        return payload
    return payload


def overlay_device_paths(
    settings: dict[str, Any] | None,
    user_id: str | None = None,
) -> dict[str, Any]:
    """Prefer this machine's stored media paths over account-cloud values."""
    merged = dict(settings or {})
    local = load_device_workspace_paths(user_id)
    for key in DEVICE_MEDIA_PATH_KEYS:
        local_value = str(local.get(key) or "").strip()
        if not local_value:
            continue
        if not is_usable_workspace_path(local_value):
            continue
        merged[key] = local_value
    return merged


def persist_device_paths_from_settings(
    settings: dict[str, Any] | None,
    user_id: str | None = None,
    *,
    replace_machine_defaults: bool = True,
) -> dict[str, str]:
    return save_device_workspace_paths(
        settings, user_id, replace_machine_defaults=replace_machine_defaults
    )


def device_path_patch_against_cloud(
    merged_settings: dict[str, Any] | None,
    cloud_settings: dict[str, Any] | None,
) -> dict[str, object]:
    """Keys where this machine's resolved paths differ from cloud (push-active)."""
    patch: dict[str, object] = {}
    merged = dict(merged_settings or {})
    cloud = dict(cloud_settings or {})
    for key in DEVICE_MEDIA_PATH_KEYS:
        local_value = str(merged.get(key) or "").strip()
        cloud_value = str(cloud.get(key) or "").strip()
        if local_value and local_value != cloud_value:
            patch[key] = local_value
    return patch


def resolve_local_suno_output_dir(
    user_id: str | None = None,
    settings: dict[str, Any] | None = None,
) -> str:
    """Best Suno root for this machine (device store → settings → default)."""
    local = load_device_workspace_paths(user_id)
    candidate = _normalize_stored_path(str(local.get("sunoOutputDir") or ""))
    if candidate and is_usable_workspace_path(candidate):
        return candidate

    for source in (settings,):
        if not isinstance(source, dict):
            continue
        cloud_val = _normalize_stored_path(str(source.get("sunoOutputDir") or ""))
        if cloud_val and is_usable_workspace_path(cloud_val):
            persist_device_paths_from_settings({**source, "sunoOutputDir": cloud_val}, user_id)
            return cloud_val

    default = default_workspace_paths()["sunoOutputDir"]
    persist_device_paths_from_settings(
        {"sunoOutputDir": default}, user_id, replace_machine_defaults=False
    )
    return default


def hydrate_local_suno_output_dir(
    *,
    api: Any | None = None,
    settings: dict[str, Any] | None = None,
    user_id: str | None = None,
    persist_cloud: bool = True,
) -> str:
    """Ensure device-store Suno root is ready and optionally push it to cloud.

    Called from the download worker so mid-session generates do not keep planning
    under a stale AppData path until the next app restart.
    """
    cloud = dict(settings or {})
    if not cloud and api is not None:
        try:
            response = api.get_settings()
            if hasattr(response, "model_dump"):
                cloud = response.model_dump(by_alias=True)
            elif isinstance(response, dict):
                cloud = dict(response)
        except Exception:
            cloud = {}

    from shared.lib.workspace_defaults import apply_workspace_path_defaults

    merged, heal_patch = apply_workspace_path_defaults(cloud)
    persist_device_paths_from_settings(merged, user_id, replace_machine_defaults=False)
    # Do not push this PC's absolute media roots into account settings.
    # Run planning uses portable relative keys on the API.
    cloud_patch = {key: value for key, value in heal_patch.items() if key not in DEVICE_MEDIA_PATH_KEYS}
    if persist_cloud and cloud_patch and api is not None:
        try:
            api.patch_settings(cloud_patch)
        except Exception:
            pass
    return resolve_local_suno_output_dir(user_id, merged)


def local_run_dir_for_disk(run_dir: str, *, local_suno_base: str | None = None) -> str:
    """Map a server/batch run_dir onto a folder this machine can use.

    Portable keys and legacy absolute paths under the default AppData
    ``Media\\Suno`` tree are always rebased onto this PC's configured Suno
    root. An existing absolute directory outside that default tree is kept
    (Change Run Folder to another drive). Foreign Windows profile paths are
    never trusted as drop targets.
    """
    text = _normalize_stored_path(str(run_dir or ""))
    if not text:
        return ""
    base = str(local_suno_base or "").strip() or resolve_local_suno_output_dir()
    if path_is_under_base(text, base):
        return text

    remapped, _ = remap_suno_download_paths(text, "", base)
    default_suno = _normalize_stored_path(default_workspace_paths()["sunoOutputDir"])
    base_norm = _normalize_stored_path(base)
    # Leftover AppData Media\Suno folders must not win after the user pointed
    # Preferences at another root (e.g. E:\SUNO).
    if (
        default_suno
        and path_is_under_base(text, default_suno)
        and base_norm.casefold() != default_suno.casefold()
    ):
        return remapped or text

    if not is_foreign_windows_profile_path(text):
        try:
            if Path(text).is_dir():
                return text
        except OSError:
            pass
    return remapped or text


def _normalize_path_text(path: str) -> str:
    return _normalize_stored_path(path)


def path_is_under_base(path: str, base: str) -> bool:
    """True when ``path`` resolves under ``base`` (case-insensitive on Windows)."""
    text = _normalize_path_text(path)
    root = _normalize_path_text(base)
    if not text or not root:
        return False
    try:
        Path(text).resolve().relative_to(Path(root).resolve())
        return True
    except (OSError, ValueError):
        # Fallback without resolve (missing parents / permission).
        left = text.rstrip("\\").casefold()
        right = root.rstrip("\\").casefold()
        return left == right or left.startswith(right + "\\")


def album_leaf_relative(output_dir: str) -> Path:
    """Last two segments of a Suno run dir: ``channel / date_album``."""
    parts = [part for part in Path(_normalize_path_text(output_dir)).parts if part not in ("/", "\\")]
    # Drop drive letter segment on Windows ("E:", "C:").
    if parts and len(parts[0]) == 2 and parts[0][1] == ":":
        parts = parts[1:]
    if len(parts) >= 2:
        return Path(parts[-2]) / parts[-1]
    if parts:
        return Path(parts[-1])
    return Path()


def run_key_from_path(path: str) -> str:
    """Relative run key ``channel/date_album`` from any absolute or relative run path.

    Desktop owns the local Suno root; API absolute paths are treated as keys only.
    """
    relative = album_leaf_relative(path)
    if not str(relative):
        return ""
    # Stable string form for joining under localSunoRoot (Path accepts / on Windows).
    return relative.as_posix()


def remap_suno_download_paths(
    output_dir: str,
    target_path: str,
    local_suno_base: str,
) -> tuple[str, str]:
    """Rebase a pending download onto this machine's ``sunoOutputDir``.

    Keeps the trailing ``channel/date_album`` (and filename) so album layout
    stays intact when cloud planned under another PC's absolute base.
    """
    out_text = str(output_dir or "").strip()
    target_text = str(target_path or "").strip()
    base = str(local_suno_base or "").strip()
    if not out_text or not base:
        return out_text, target_text
    if path_is_under_base(out_text, base) and not is_foreign_windows_profile_path(out_text):
        return out_text, target_text

    relative = album_leaf_relative(out_text)
    new_out = Path(base) / relative if str(relative) else Path(base)
    new_out_text = str(new_out)

    if not target_text:
        return new_out_text, target_text

    target = Path(_normalize_path_text(target_text))
    filename = target.name
    # Prefer preserving relative path under the old output_dir when possible.
    try:
        rel_file = target.relative_to(Path(_normalize_path_text(out_text)))
        new_target = new_out / rel_file
    except ValueError:
        new_target = new_out / filename
    return new_out_text, str(new_target)
