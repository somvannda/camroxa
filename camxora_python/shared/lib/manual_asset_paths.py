"""Manual image asset inspection — port of manualAssetPaths.ts."""

from __future__ import annotations

import re
from dataclasses import dataclass

MANUAL_IMAGE_EXTENSIONS = ("png", "jpg", "jpeg", "webp")

MANUAL_ASSET_SPECS = (
    ("background-16x9", "BG 16:9"),
    ("background-9x16", "BG 9:16"),
    ("thumbnail-16x9", "TH 16:9"),
    ("thumbnail-9x16", "TH 9:16"),
)


@dataclass(frozen=True, slots=True)
class ManualAssetInspection:
    directory: str
    ready: bool
    ready_count: int
    total: int
    missing_labels: tuple[str, ...]
    found_files: tuple[str, ...]


def _basename(target_path: str) -> str:
    normalized = str(target_path or "").replace("\\", "/")
    parts = normalized.split("/")
    return parts[-1] if parts else normalized


def inspect_manual_asset_files(directory: str, files: list[str]) -> ManualAssetInspection:
    normalized_names = {_basename(file_path).lower() for file_path in files}
    missing_labels: list[str] = []
    found_files: list[str] = []

    for _key, label in MANUAL_ASSET_SPECS:
        file_stem = _key
        matched_file = next(
            (
                f"{file_stem}.{extension}"
                for extension in MANUAL_IMAGE_EXTENSIONS
                if f"{file_stem}.{extension}" in normalized_names
            ),
            None,
        )
        if matched_file:
            found_files.append(matched_file)
        else:
            missing_labels.append(label)

    total = len(MANUAL_ASSET_SPECS)
    ready_count = total - len(missing_labels)
    return ManualAssetInspection(
        directory=directory,
        ready=not missing_labels,
        ready_count=ready_count,
        total=total,
        missing_labels=tuple(missing_labels),
        found_files=tuple(found_files),
    )


def normalize_image_source_mode(value: object) -> str:
    return "manual" if str(value or "").strip().lower() == "manual" else "ai"


def manual_inspection_key(batch_id: str, profile_id: str, role: str) -> str:
    return f"{batch_id}:{profile_id}:{role}"


def _sanitize_folder_segment(value: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "-", str(value or "").strip())
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = re.sub(r"\.+$", "", cleaned).strip()
    return (cleaned[:80] or "item")


def _sanitize_run_label(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9 _.-]+", "", str(value or ""))
    cleaned = re.sub(r"\s+", " ", cleaned).strip().replace(" ", "-")
    return cleaned[:64]


def build_run_folder_label(*, run_date: str, album: str | None = None) -> str:
    date_part = _sanitize_run_label(str(run_date or "").strip())[:10] or "run"
    album_slug = _sanitize_run_label(str(album or "").strip())
    if album_slug and album_slug.lower() not in {"run", "item"}:
        return f"{date_part}_{album_slug}"[:64]
    return date_part


def _join_windows_path(*segments: str) -> str:
    parts: list[str] = []
    for index, segment in enumerate(segments):
        normalized = str(segment or "").replace("/", "\\")
        if index == 0:
            parts.append(normalized.rstrip("\\"))
        else:
            parts.append(normalized.strip("\\"))
    return "\\".join(part for part in parts if part)


@dataclass(frozen=True, slots=True)
class PlannedManualRunDirectories:
    ok_run_dir: str
    alt_run_dir: str
    run_folder_name: str


def plan_manual_asset_run_directories(
    *,
    base_dir: str,
    ok_profile_folder: str,
    alt_profile_folder: str,
    run_label: str,
    existing_ok_entries: list[str] | None = None,
    existing_alt_entries: list[str] | None = None,
) -> PlannedManualRunDirectories:
    base = str(base_dir or "").strip().rstrip("\\/")
    if not base:
        return PlannedManualRunDirectories(ok_run_dir="", alt_run_dir="", run_folder_name="")

    ok_profile_dir = _join_windows_path(base, _sanitize_folder_segment(ok_profile_folder))
    alt_profile_dir = _join_windows_path(base, _sanitize_folder_segment(alt_profile_folder))
    base_name = _sanitize_run_label(run_label) or "run"
    pattern = re.compile(rf"^{re.escape(base_name)}(?:_(\d{{2,}}))?$")

    def max_index(entries: list[str]) -> int:
        maximum = 0
        for entry in entries:
            match = pattern.match(str(entry or "").strip())
            if not match:
                continue
            if not match.group(1):
                maximum = max(maximum, 1)
            else:
                maximum = max(maximum, int(match.group(1)))
        return maximum

    existing_ok = existing_ok_entries or []
    existing_alt = existing_alt_entries or []
    max_existing = max(max_index(existing_ok), max_index(existing_alt))
    run_folder_name = base_name if max_existing == 0 else f"{base_name}_{max_existing + 1:02d}"
    return PlannedManualRunDirectories(
        ok_run_dir=_join_windows_path(ok_profile_dir, run_folder_name),
        alt_run_dir=_join_windows_path(alt_profile_dir, run_folder_name),
        run_folder_name=run_folder_name,
    )
