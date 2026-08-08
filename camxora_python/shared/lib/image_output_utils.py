"""Helpers for ensuring image job outputs exist on the local filesystem."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from shared.services.file_service import read_file_bytes, sanitize_local_path
from shared.services.platform_api import PlatformApi

# Re-download when the job row is clearly newer than the local file (clock skew buffer).
_REMOTE_NEWER_SKEW_SEC = 2.0


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


def remote_updated_at_epoch(value: object | None) -> float | None:
    """Parse API ``updated_at`` into UTC epoch seconds, or None if unknown."""
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def invalidate_local_image_output(path: str | None) -> bool:
    """Delete a local image output so the next ensure re-downloads from the API.

    Used when regenerating: the server reuses the same relative output path, so a
    leftover local PNG would otherwise keep showing the previous generation.
    """
    target_path = resolve_local_image_output_path(path)
    if not target_path:
        return False
    target = Path(target_path)
    try:
        if target.is_file():
            target.unlink()
            return True
    except OSError:
        return False
    return False


def ensure_image_output_local(
    api: PlatformApi | None,
    path: str | None,
    job_id: str | None,
    *,
    force: bool = False,
    remote_updated_at: object | None = None,
) -> str | None:
    """Return a local path to the image, downloading from the API when missing/stale.

    When ``remote_updated_at`` is set and the local file's mtime is older than that
    job timestamp, re-download and overwrite. Regenerates keep the same filename, so
    existence alone is not enough to treat the file as current.
    """
    target_path = resolve_local_image_output_path(path)
    if not target_path:
        return None
    target = Path(target_path)
    if target.is_file() and not force:
        remote_ts = remote_updated_at_epoch(remote_updated_at)
        if remote_ts is None:
            if read_file_bytes(target_path):
                return target_path
        else:
            try:
                local_mtime = float(target.stat().st_mtime)
            except OSError:
                local_mtime = 0.0
            if local_mtime + _REMOTE_NEWER_SKEW_SEC >= remote_ts and read_file_bytes(target_path):
                return target_path
    if api is None or not job_id:
        return target_path if target.is_file() and read_file_bytes(target_path) else None
    image_bytes = api.get_image_job_output(job_id)
    if not image_bytes:
        return None
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(image_bytes)
    return target_path
