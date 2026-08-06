"""Plan per-channel batch run directories under the user's Suno output base."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path


@dataclass(frozen=True, slots=True)
class PlannedRunDirectories:
    ok_run_dir: str
    alt_run_dir: str
    run_folder_name: str


def sanitize_folder_segment(value: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "-", str(value or "").strip())
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = re.sub(r"\.+$", "", cleaned).strip()
    return (cleaned[:80] or "item")


def sanitize_run_label(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9 _.-]+", "", str(value or ""))
    cleaned = re.sub(r"\s+", " ", cleaned).strip().replace(" ", "-")
    return cleaned[:64]


def build_run_folder_label(*, run_date: date | str, album: str | None = None) -> str:
    """Build a run folder name with date first, then optional album slug.

    Example: ``2026-07-12_Midnight-Drive`` or ``2026-07-12`` when album is empty.
    """
    if isinstance(run_date, date):
        date_part = run_date.isoformat()
    else:
        date_part = sanitize_run_label(str(run_date or "").strip())[:10] or "run"
    album_slug = sanitize_run_label(str(album or "").strip())
    if album_slug and album_slug.lower() not in {"run", "item"}:
        combined = f"{date_part}_{album_slug}"
        return combined[:64]
    return date_part


def join_windows_path(*segments: str) -> str:
    parts: list[str] = []
    for index, segment in enumerate(segments):
        normalized = str(segment or "").replace("/", "\\")
        if index == 0:
            parts.append(normalized.rstrip("\\"))
        else:
            parts.append(normalized.strip("\\"))
    return "\\".join(part for part in parts if part)


def normalize_run_key(path: str | None) -> str | None:
    """Store/return only ``channel\\date_album`` — never a machine absolute path.

    Desktop owns the local Suno root and joins this key at download/open time.
    Accepts legacy absolute Windows paths and strips them to the trailing key.
    """
    text = str(path or "").strip()
    if not text:
        return None
    normalized = text.replace("/", "\\")
    parts = [part for part in Path(normalized).parts if part not in ("/", "\\", "")]
    if parts and len(parts[0]) == 2 and parts[0][1] == ":":
        parts = parts[1:]
    # Drop UNC host/share prefixes when present (\\server\\share\\channel\\album).
    if len(parts) >= 4 and normalized.startswith("\\\\"):
        parts = parts[-2:]
    if len(parts) >= 2:
        return join_windows_path(parts[-2], parts[-1])
    if len(parts) == 1:
        return parts[0]
    return None


def list_run_folder_entries(base_dir: str, profile_folder: str) -> list[str]:
    profile_dir = Path(join_windows_path(base_dir, sanitize_folder_segment(profile_folder)))
    if not profile_dir.is_dir():
        return []
    return sorted(entry.name for entry in profile_dir.iterdir() if entry.is_dir())


def _resolve_unique_folder_name(base_name: str, entries: list[str]) -> str:
    pattern = re.compile(rf"^{re.escape(base_name)}(?:_(\d{{2,}}))?$")
    maximum = 0
    for entry in entries:
        match = pattern.match(str(entry or "").strip())
        if not match:
            continue
        if not match.group(1):
            maximum = max(maximum, 1)
        else:
            maximum = max(maximum, int(match.group(1)))
    return base_name if maximum == 0 else f"{base_name}_{maximum + 1:02d}"


def plan_relative_run_directories(
    *,
    ok_profile_folder: str,
    alt_profile_folder: str,
    run_label: str,
    ok_run_label: str | None = None,
    alt_run_label: str | None = None,
    existing_ok_entries: list[str] | None = None,
    existing_alt_entries: list[str] | None = None,
) -> PlannedRunDirectories:
    """Plan portable run keys (``channel\\date_album``) with no machine base path."""
    ok_folder = sanitize_folder_segment(ok_profile_folder)
    alt_folder = sanitize_folder_segment(alt_profile_folder)
    if not ok_folder or not alt_folder:
        return PlannedRunDirectories(ok_run_dir="", alt_run_dir="", run_folder_name="")

    ok_base_name = sanitize_run_label(ok_run_label or run_label) or "run"
    alt_base_name = sanitize_run_label(alt_run_label or run_label) or "run"
    ok_folder_name = _resolve_unique_folder_name(ok_base_name, existing_ok_entries or [])
    alt_folder_name = _resolve_unique_folder_name(alt_base_name, existing_alt_entries or [])
    return PlannedRunDirectories(
        ok_run_dir=join_windows_path(ok_folder, ok_folder_name),
        alt_run_dir=join_windows_path(alt_folder, alt_folder_name),
        run_folder_name=ok_folder_name,
    )


def plan_run_directories(
    *,
    base_dir: str,
    ok_profile_folder: str,
    alt_profile_folder: str,
    run_label: str,
    ok_run_label: str | None = None,
    alt_run_label: str | None = None,
    existing_ok_entries: list[str] | None = None,
    existing_alt_entries: list[str] | None = None,
) -> PlannedRunDirectories:
    """Plan run directories. Stored values are always portable relative keys.

    ``base_dir`` is only used for optional on-disk uniqueness listing when that
    folder exists on the API host (usually empty on Linux production).
    """
    relative = plan_relative_run_directories(
        ok_profile_folder=ok_profile_folder,
        alt_profile_folder=alt_profile_folder,
        run_label=run_label,
        ok_run_label=ok_run_label,
        alt_run_label=alt_run_label,
        existing_ok_entries=existing_ok_entries,
        existing_alt_entries=existing_alt_entries,
    )
    return relative


def infer_alt_run_dir_from_ok(*, ok_run_dir: str, alt_profile_folder: str) -> str | None:
    key = normalize_run_key(ok_run_dir)
    if not key:
        return None
    alt_folder = sanitize_folder_segment(alt_profile_folder)
    if not alt_folder:
        return None
    album = Path(key.replace("/", "\\")).name
    if not album:
        return None
    return join_windows_path(alt_folder, album)


def resolve_history_output_dirs(
    *,
    song_output_dir_ok: str | None,
    song_output_dir_alt: str | None,
    batch_ok_run_dir: str | None = None,
    batch_alt_run_dir: str | None = None,
    alt_profile_folder: str | None = None,
    alt_profile_name: str | None = None,
) -> tuple[str | None, str | None]:
    """Resolve per-song history folders with the same ALT inference used by /progress."""
    ok_dir = str(song_output_dir_ok or batch_ok_run_dir or "").strip() or None
    alt_stored = str(song_output_dir_alt or batch_alt_run_dir or "").strip() or None
    alt_dir = resolve_channel_run_dir(
        role="ALT",
        ok_run_dir=ok_dir,
        alt_run_dir=alt_stored,
        alt_profile_folder=alt_profile_folder,
        alt_profile_name=alt_profile_name,
    )
    return ok_dir, alt_dir


def resolve_channel_run_dir(
    *,
    role: str,
    ok_run_dir: str | None,
    alt_run_dir: str | None,
    alt_profile_folder: str | None = None,
    alt_profile_name: str | None = None,
) -> str | None:
    role_key = str(role or "").strip().upper()
    stored_ok = str(ok_run_dir or "").strip()
    stored_alt = str(alt_run_dir or "").strip()

    if role_key == "OK":
        return stored_ok or None

    if stored_alt and (not stored_ok or stored_alt != stored_ok):
        return stored_alt

    alt_folder = str(alt_profile_folder or alt_profile_name or "").strip()
    if stored_ok and alt_folder:
        inferred = infer_alt_run_dir_from_ok(ok_run_dir=stored_ok, alt_profile_folder=alt_folder)
        if inferred:
            return inferred
    return stored_alt or None
