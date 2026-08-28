"""Shared formatting helpers for the Profile workspace."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from shared.lib.formatting import format_short_date
from shared.models.auth import ProfileResponse
from shared.models.platform import RecentActivity
from shared.services.local_user_scope import get_user_workspace_dir


def short_list(values: list[str], *, empty: str = "None yet", limit: int = 3) -> str:
    cleaned = [value.strip() for value in values if value and value.strip()]
    if not cleaned:
        return empty
    if len(cleaned) <= limit:
        return ", ".join(cleaned)
    return ", ".join(cleaned[:limit]) + f" (+{len(cleaned) - limit})"


def profile_names_summary(profiles: list[ProfileResponse]) -> str:
    return short_list([profile.name for profile in profiles])


def profile_folders_summary(profiles: list[ProfileResponse]) -> str:
    folders: list[str] = []
    for profile in profiles:
        folder = (profile.folder_name or profile.run_prefix or "").strip()
        if folder and folder not in folders:
            folders.append(folder)
    return short_list(folders, empty="Not set")


def local_data_hint(user_id: str) -> str:
    path = get_user_workspace_dir(user_id)
    parts = Path(path).parts
    if "Camxora" in parts:
        index = parts.index("Camxora")
        return "/".join(parts[index:])
    return str(path)


def profile_updated_label(profile: ProfileResponse) -> str:
    extra = getattr(profile, "model_extra", None) or {}
    raw = extra.get("updated") or extra.get("updated_at") or extra.get("modified_at")
    if raw is None:
        raw = getattr(profile, "updated", None) or getattr(profile, "updated_at", None)
    if not raw:
        return "—"
    try:
        return format_short_date(raw)
    except Exception:
        return str(raw)


def plan_subtitle(plan_name: str | None) -> str:
    text = str(plan_name or "").strip().lower()
    if "year" in text or "annual" in text:
        return "Annual plan"
    if "week" in text:
        return "Weekly plan"
    if text:
        return "Monthly plan"
    return "No active plan"


def visibility_key(value: str | None) -> str:
    return str(value or "unlisted").strip().lower() or "unlisted"


def title_visibility(value: str | None) -> str:
    key = visibility_key(value)
    return key[:1].upper() + key[1:] if key else "Unlisted"


def relative_timestamp(value: datetime | str | None) -> str:
    if value is None:
        return ""
    parsed = value if isinstance(value, datetime) else _parse_datetime(str(value))
    if parsed is None:
        return str(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    seconds = max(0, int((now - parsed.astimezone(timezone.utc)).total_seconds()))
    if seconds < 45:
        return "just now"
    if seconds < 3600:
        minutes = max(1, seconds // 60)
        return f"{minutes} min ago"
    if seconds < 86400:
        hours = max(1, seconds // 3600)
        return f"{hours} hr ago"
    days = max(1, seconds // 86400)
    return f"{days}d ago"


def activity_title(item: RecentActivity) -> str:
    kind = str(item.kind or "").strip()
    if not kind:
        return "Activity"
    lowered = kind.lower()
    if lowered in {"song", "songs"}:
        return "Generated songs"
    if lowered in {"image", "images"}:
        return "Created image"
    if lowered in {"video", "videos"}:
        return "Exported video"
    if "credit" in lowered:
        return "Credits spent"
    return kind


def _parse_datetime(value: str) -> datetime | None:
    normalized = value.strip()
    if not normalized:
        return None
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None
