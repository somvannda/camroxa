"""Helpers for ensuring image job outputs exist on the local filesystem."""

from __future__ import annotations

from pathlib import Path

from shared.services.file_service import read_file_bytes, sanitize_local_path
from shared.services.platform_api import PlatformApi


def resolve_local_image_output_path(path: str | None) -> str:
    """Map API-stored image paths onto this PC when needed.

    - Non-foreign absolute paths (this PC / test dirs / Change Run Folder) stay as-is.
    - Portable ``channel\\album\\file.png`` keys and foreign Windows profile paths
      are remapped under this machine's Suno root.
    """
    text = sanitize_local_path(str(path or "").strip())
    if not text:
        return ""
    from shared.lib.device_workspace_paths import local_run_dir_for_disk
    from shared.lib.path_locality import is_foreign_windows_profile_path

    candidate = Path(text)
    # Absolute path on this machine — do not force onto Suno root.
    if candidate.is_absolute() and not is_foreign_windows_profile_path(text):
        return text

    parent = str(candidate.parent).strip()
    name = candidate.name
    if not name or parent in {"", ".", "\\", "/"}:
        return text
    remapped_parent = local_run_dir_for_disk(parent)
    if remapped_parent:
        return str(Path(remapped_parent) / name)
    return text


def ensure_image_output_local(
    api: PlatformApi | None,
    path: str | None,
    job_id: str | None,
) -> str | None:
    """Return a local path to the image, downloading from the API when missing."""
    target_path = resolve_local_image_output_path(path)
    if not target_path:
        return None
    if read_file_bytes(target_path):
        return target_path
    if api is None or not job_id:
        return None
    image_bytes = api.get_image_job_output(job_id)
    if not image_bytes:
        return None
    target = Path(target_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(image_bytes)
    return target_path
