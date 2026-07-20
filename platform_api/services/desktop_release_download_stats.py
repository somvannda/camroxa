"""Per-version desktop installer download counters (system_settings JSON blob)."""

from __future__ import annotations

import json
from typing import Any

from platform_api.services.billing_config_service import load_system_setting
from platform_api.services.desktop_release_upload_service import extract_version_from_installer_filename

DESKTOP_DOWNLOAD_COUNTS_KEY = "desktop.software_update.download_counts"


def _normalize_counts(raw: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for key, value in raw.items():
        version = str(key or "").strip()
        if not version:
            continue
        try:
            counts[version] = max(0, int(value))
        except (TypeError, ValueError):
            continue
    return counts


async def _load_counts(pool: Any) -> dict[str, int]:
    raw = await load_system_setting(pool, DESKTOP_DOWNLOAD_COUNTS_KEY)
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    return _normalize_counts(parsed)


async def _save_counts(pool: Any, counts: dict[str, int]) -> None:
    payload = json.dumps(_normalize_counts(counts), separators=(",", ":"))
    await pool.execute(
        """
        INSERT INTO system_settings (key, value, value_type, updated_at)
        VALUES ($1, $2, 'json', NOW())
        ON CONFLICT (key) DO UPDATE
        SET value = EXCLUDED.value,
            value_type = EXCLUDED.value_type,
            updated_at = NOW()
        """,
        DESKTOP_DOWNLOAD_COUNTS_KEY,
        payload,
    )


async def get_download_counts(pool: Any) -> dict[str, int]:
    return await _load_counts(pool)


async def get_download_count_for_version(pool: Any, version: str) -> int:
    normalized = str(version or "").strip()
    if not normalized:
        return 0
    counts = await _load_counts(pool)
    return int(counts.get(normalized, 0))


async def get_total_downloads(pool: Any) -> int:
    counts = await _load_counts(pool)
    return sum(counts.values())


async def increment_download_for_filename(pool: Any, filename: str) -> tuple[str | None, int]:
    """Increment counter for installer version parsed from filename. Returns (version, new_count)."""
    version = extract_version_from_installer_filename(filename)
    if not version:
        return None, 0
    counts = await _load_counts(pool)
    new_count = int(counts.get(version, 0)) + 1
    counts[version] = new_count
    await _save_counts(pool, counts)
    return version, new_count
