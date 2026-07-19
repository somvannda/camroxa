"""Helpers for ensuring image job outputs exist on the local filesystem."""

from __future__ import annotations

from pathlib import Path

from shared.services.file_service import read_file_bytes, sanitize_local_path
from shared.services.platform_api import PlatformApi


def ensure_image_output_local(
    api: PlatformApi | None,
    path: str | None,
    job_id: str | None,
) -> str | None:
    """Return a local path to the image, downloading from the API when missing."""
    target_path = sanitize_local_path(str(path or "").strip())
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
