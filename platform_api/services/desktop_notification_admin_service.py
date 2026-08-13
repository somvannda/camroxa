"""Admin-managed desktop push notifications and software update publishing."""

from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from platform_api.services.billing_config_service import load_system_setting
from platform_api.services.workspace_notifications import (
    SOFTWARE_UPDATE_AVAILABLE_EVENT,
    notify_software_update_available,
)

logger = logging.getLogger(__name__)

NOTIFICATION_MESSAGE_EVENT = "notification.message"

SOFTWARE_UPDATE_VERSION_KEY = "desktop.software_update.version"
SOFTWARE_UPDATE_DOWNLOAD_URL_KEY = "desktop.software_update.download_url"
SOFTWARE_UPDATE_MANDATORY_KEY = "desktop.software_update.mandatory"
SOFTWARE_UPDATE_RELEASE_NOTES_KEY = "desktop.software_update.release_notes"
SOFTWARE_UPDATE_PUBLISHED_AT_KEY = "desktop.software_update.published_at"
SOFTWARE_UPDATE_LIVE_KEY = "desktop.software_update.live"
SOFTWARE_UPDATE_LIVE_HISTORY_KEY = "desktop.software_update.live_history"
PUSH_NOTIFICATION_HISTORY_KEY = "desktop.push_notifications.history"

MAX_HISTORY_ITEMS = 25
MAX_LIVE_HISTORY = 25
RELEASE_NOTES_CATEGORY = "Release notes"
_VERSION_PATTERN = re.compile(r"^(\d+)(?:\.(\d+))?(?:\.(\d+))?")


@dataclass(frozen=True, slots=True)
class SoftwareUpdateConfig:
    version: str
    download_url: str
    mandatory: bool
    release_notes: str
    published_at: str | None
    live_version: str = ""
    live_download_url: str = ""
    live_mandatory: bool = False
    live_release_notes: str = ""
    live_published_at: str | None = None


@dataclass(frozen=True, slots=True)
class InstallerCandidate:
    version: str
    download_url: str
    filename: str = ""


@dataclass(frozen=True, slots=True)
class UnpublishResult:
    draft: SoftwareUpdateConfig
    unpublished_version: str
    restored_live_version: str | None


@dataclass(frozen=True, slots=True)
class PushNotificationHistoryItem:
    id: str
    title: str
    message: str
    created_at: str
    recipients: int


def _parse_bool(value: str | None) -> bool:
    if not value:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_version(value: str | None) -> tuple[int, int, int]:
    text = str(value or "").replace("\ufeff", "").strip()
    if len(text) >= 2 and text[0] in {"v", "V"} and text[1].isdigit():
        text = text[1:].strip()
    if not text:
        return (0, 0, 0)
    match = _VERSION_PATTERN.match(text)
    if match is None:
        return (0, 0, 0)
    return (
        int(match.group(1) or 0),
        int(match.group(2) or 0),
        int(match.group(3) or 0),
    )


def _installer_filename_from_url(url: str) -> str:
    path = unquote(urlparse(str(url or "")).path)
    return Path(path).name.strip()


def _same_installer(
    left_url: str,
    right_url: str,
    *,
    left_version: str = "",
    right_version: str = "",
    filename: str = "",
) -> bool:
    left = str(left_url or "").strip()
    right = str(right_url or "").strip()
    if left and right and left == right:
        return True
    left_name = _installer_filename_from_url(left).lower()
    right_name = _installer_filename_from_url(right).lower()
    file_name = Path(str(filename or "")).name.strip().lower()
    if left_name and right_name and left_name == right_name:
        return True
    if file_name and left_name == file_name:
        return True
    # Version-only fallback when a URL is missing (legacy settings / deleted file).
    left_ver = str(left_version or "").strip()
    right_ver = str(right_version or "").strip()
    if left_ver and right_ver and left_ver == right_ver and (not left or not right):
        return True
    return False


async def _upsert_system_setting(
    pool: Any,
    *,
    key: str,
    value: str,
    value_type: str = "string",
) -> None:
    await pool.execute(
        """
        INSERT INTO system_settings (key, value, value_type, updated_at)
        VALUES ($1, $2, $3, NOW())
        ON CONFLICT (key) DO UPDATE
        SET value = EXCLUDED.value,
            value_type = EXCLUDED.value_type,
            updated_at = NOW()
        """,
        key,
        value,
        value_type,
    )


def _snapshot_from_values(
    *,
    version: str,
    download_url: str,
    mandatory: bool,
    release_notes: str,
    published_at: str,
    changelog_slug: str = "",
) -> dict[str, Any]:
    return {
        "version": str(version or "").strip(),
        "download_url": str(download_url or "").strip(),
        "mandatory": bool(mandatory),
        "release_notes": str(release_notes or "").strip(),
        "published_at": str(published_at or "").strip(),
        "changelog_slug": str(changelog_slug or "").strip(),
    }


def _snapshot_is_valid(snapshot: dict[str, Any] | None) -> bool:
    if not isinstance(snapshot, dict):
        return False
    return bool(str(snapshot.get("version") or "").strip() and str(snapshot.get("published_at") or "").strip())


def _config_from_snapshot(snapshot: dict[str, Any]) -> SoftwareUpdateConfig:
    version = str(snapshot.get("version") or "").strip()
    download_url = str(snapshot.get("download_url") or "").strip()
    release_notes = str(snapshot.get("release_notes") or "").strip()
    published_at = str(snapshot.get("published_at") or "").strip() or None
    mandatory = bool(snapshot.get("mandatory"))
    return SoftwareUpdateConfig(
        version=version,
        download_url=download_url,
        mandatory=mandatory,
        release_notes=release_notes,
        published_at=published_at,
        live_version=version,
        live_download_url=download_url,
        live_mandatory=mandatory,
        live_release_notes=release_notes,
        live_published_at=published_at,
    )


async def _load_json_setting(pool: Any, key: str) -> Any:
    raw = await load_system_setting(pool, key)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


async def _load_live_snapshot(pool: Any) -> dict[str, Any] | None:
    payload = await _load_json_setting(pool, SOFTWARE_UPDATE_LIVE_KEY)
    if not isinstance(payload, dict):
        return None
    return payload


async def _save_live_snapshot(pool: Any, snapshot: dict[str, Any] | None) -> None:
    if snapshot is None:
        await _upsert_system_setting(pool, key=SOFTWARE_UPDATE_LIVE_KEY, value="", value_type="json")
        await _upsert_system_setting(pool, key=SOFTWARE_UPDATE_PUBLISHED_AT_KEY, value="")
        return
    await _upsert_system_setting(
        pool,
        key=SOFTWARE_UPDATE_LIVE_KEY,
        value=json.dumps(snapshot),
        value_type="json",
    )
    await _upsert_system_setting(
        pool,
        key=SOFTWARE_UPDATE_PUBLISHED_AT_KEY,
        value=str(snapshot.get("published_at") or "").strip(),
    )


async def _load_live_history(pool: Any) -> list[dict[str, Any]]:
    payload = await _load_json_setting(pool, SOFTWARE_UPDATE_LIVE_HISTORY_KEY)
    if not isinstance(payload, list):
        return []
    items: list[dict[str, Any]] = []
    for entry in payload:
        if isinstance(entry, dict) and _snapshot_is_valid(entry):
            items.append(entry)
    return items[:MAX_LIVE_HISTORY]


async def _save_live_history(pool: Any, items: list[dict[str, Any]]) -> None:
    await _upsert_system_setting(
        pool,
        key=SOFTWARE_UPDATE_LIVE_HISTORY_KEY,
        value=json.dumps(items[:MAX_LIVE_HISTORY]),
        value_type="json",
    )


async def _read_draft_fields(pool: Any) -> dict[str, Any]:
    return {
        "version": await load_system_setting(pool, SOFTWARE_UPDATE_VERSION_KEY) or "",
        "download_url": await load_system_setting(pool, SOFTWARE_UPDATE_DOWNLOAD_URL_KEY) or "",
        "mandatory": _parse_bool(await load_system_setting(pool, SOFTWARE_UPDATE_MANDATORY_KEY)),
        "release_notes": await load_system_setting(pool, SOFTWARE_UPDATE_RELEASE_NOTES_KEY) or "",
        "published_at": await load_system_setting(pool, SOFTWARE_UPDATE_PUBLISHED_AT_KEY) or "",
    }


async def ensure_live_snapshot(pool: Any) -> dict[str, Any] | None:
    """Promote legacy draft+published_at into a live snapshot if needed."""
    live = await _load_live_snapshot(pool)
    if _snapshot_is_valid(live):
        return live
    draft = await _read_draft_fields(pool)
    if not str(draft["version"]).strip() or not str(draft["published_at"]).strip():
        return None
    snapshot = _snapshot_from_values(
        version=str(draft["version"]),
        download_url=str(draft["download_url"]),
        mandatory=bool(draft["mandatory"]),
        release_notes=str(draft["release_notes"]),
        published_at=str(draft["published_at"]),
    )
    await _save_live_snapshot(pool, snapshot)
    return snapshot


def _draft_matches_live(draft: dict[str, Any], live: dict[str, Any] | None) -> bool:
    if not _snapshot_is_valid(live):
        return False
    draft_version = str(draft.get("version") or "").strip()
    live_version = str(live.get("version") or "").strip()
    if not draft_version or draft_version != live_version:
        return False
    return _same_installer(
        str(live.get("download_url") or ""),
        str(draft.get("download_url") or ""),
        left_version=live_version,
        right_version=draft_version,
    )


def _hosted_installer_url(url: str) -> bool:
    path = unquote(urlparse(str(url or "")).path).lower()
    return "/desktop-release/files/" in path


def _draft_installer_is_missing(
    draft: dict[str, Any],
    live: dict[str, Any] | None,
    installer_candidates: list[InstallerCandidate],
) -> bool:
    """True when draft points at a Camxora installer that is no longer on disk."""
    if _draft_matches_live(draft, live):
        return False
    version = str(draft.get("version") or "").strip()
    url = str(draft.get("download_url") or "").strip()
    if not version and not url:
        return False
    for candidate in installer_candidates:
        if _same_installer(
            url,
            candidate.download_url,
            left_version=version,
            right_version=candidate.version,
            filename=candidate.filename,
        ):
            return False
    if url:
        return _hosted_installer_url(url)
    return bool(version)


async def _copy_live_into_draft(pool: Any, live: dict[str, Any] | None) -> None:
    """Make the working draft match live, or clear it when nothing is published."""
    if _snapshot_is_valid(live):
        await _upsert_system_setting(
            pool, key=SOFTWARE_UPDATE_VERSION_KEY, value=str((live or {}).get("version") or "").strip()
        )
        await _upsert_system_setting(
            pool,
            key=SOFTWARE_UPDATE_DOWNLOAD_URL_KEY,
            value=str((live or {}).get("download_url") or "").strip(),
        )
        await _upsert_system_setting(
            pool,
            key=SOFTWARE_UPDATE_MANDATORY_KEY,
            value="true" if bool((live or {}).get("mandatory")) else "false",
            value_type="boolean",
        )
        await _upsert_system_setting(
            pool,
            key=SOFTWARE_UPDATE_RELEASE_NOTES_KEY,
            value=str((live or {}).get("release_notes") or "").strip(),
        )
        return
    await _upsert_system_setting(pool, key=SOFTWARE_UPDATE_VERSION_KEY, value="")
    await _upsert_system_setting(pool, key=SOFTWARE_UPDATE_DOWNLOAD_URL_KEY, value="")


async def list_active_user_ids(pool: Any) -> list[str]:
    rows = await pool.fetch(
        """
        SELECT id::text AS user_id
        FROM users
        WHERE deleted_at IS NULL
          AND status = 'active'
        """
    )
    return [str(row["user_id"]) for row in rows]


async def get_software_update_config(
    pool: Any,
    *,
    installer_candidates: list[InstallerCandidate] | None = None,
) -> SoftwareUpdateConfig:
    await ensure_live_snapshot(pool)
    live = await _load_live_snapshot(pool)
    if installer_candidates:
        draft = await _read_draft_fields(pool)
        if _draft_installer_is_missing(draft, live, installer_candidates):
            await _copy_live_into_draft(pool, live)
    draft = await _read_draft_fields(pool)
    draft_is_live = _draft_matches_live(draft, live)
    live_version = str((live or {}).get("version") or "").strip() if _snapshot_is_valid(live) else ""
    live_download_url = str((live or {}).get("download_url") or "").strip() if live_version else ""
    live_release_notes = str((live or {}).get("release_notes") or "").strip() if live_version else ""
    live_published_at = str((live or {}).get("published_at") or "").strip() or None if live_version else None
    live_mandatory = bool((live or {}).get("mandatory")) if live_version else False
    return SoftwareUpdateConfig(
        version=str(draft["version"]),
        download_url=str(draft["download_url"]),
        mandatory=bool(draft["mandatory"]),
        release_notes=str(draft["release_notes"]),
        published_at=live_published_at if draft_is_live else None,
        live_version=live_version,
        live_download_url=live_download_url,
        live_mandatory=live_mandatory,
        live_release_notes=live_release_notes,
        live_published_at=live_published_at,
    )


async def get_published_desktop_release(pool: Any) -> SoftwareUpdateConfig | None:
    """Return the live public desktop release, or None if nothing is published."""
    live = await ensure_live_snapshot(pool)
    if not _snapshot_is_valid(live):
        return None
    return _config_from_snapshot(live or {})


async def save_software_update_config(
    pool: Any,
    *,
    version: str,
    download_url: str,
    mandatory: bool,
    release_notes: str,
) -> SoftwareUpdateConfig:
    # Snapshot the currently published release before overwriting draft fields.
    live = await ensure_live_snapshot(pool)
    await _upsert_system_setting(pool, key=SOFTWARE_UPDATE_VERSION_KEY, value=version.strip())
    await _upsert_system_setting(pool, key=SOFTWARE_UPDATE_DOWNLOAD_URL_KEY, value=download_url.strip())
    await _upsert_system_setting(
        pool,
        key=SOFTWARE_UPDATE_MANDATORY_KEY,
        value="true" if mandatory else "false",
        value_type="boolean",
    )
    await _upsert_system_setting(pool, key=SOFTWARE_UPDATE_RELEASE_NOTES_KEY, value=release_notes.strip())
    if _snapshot_is_valid(live) and _same_installer(
        str((live or {}).get("download_url") or ""),
        download_url,
        left_version=str((live or {}).get("version") or ""),
        right_version=version,
    ) and str((live or {}).get("version") or "").strip() == version.strip():
        # In-place edit of the live release (e.g. turn Force update off) without a rollback.
        updated = dict(live or {})
        updated["download_url"] = download_url.strip()
        updated["mandatory"] = bool(mandatory)
        updated["release_notes"] = release_notes.strip()
        await _save_live_snapshot(pool, updated)
    return await get_software_update_config(pool)


async def apply_uploaded_installer_to_draft(
    pool: Any,
    *,
    download_url: str,
    version: str | None = None,
) -> SoftwareUpdateConfig:
    """Persist generated installer URL (and optional version) into the draft only."""
    await ensure_live_snapshot(pool)
    await _upsert_system_setting(
        pool,
        key=SOFTWARE_UPDATE_DOWNLOAD_URL_KEY,
        value=str(download_url or "").strip(),
    )
    normalized_version = str(version or "").strip()
    if normalized_version:
        await _upsert_system_setting(pool, key=SOFTWARE_UPDATE_VERSION_KEY, value=normalized_version)
    return await get_software_update_config(pool)


def _slugify_release_title(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(title or "").strip().lower()).strip("-")
    return slug[:180] or "release"


def _release_notes_title(version: str) -> str:
    return f"Camxora Desktop {str(version or '').strip()}"


def _release_notes_slug_base(version: str) -> str:
    return _slugify_release_title(f"camxora-desktop-{str(version or '').strip()}")


async def _ensure_unique_blog_slug(pool: Any, slug: str) -> str:
    candidate = slug
    suffix = 2
    while True:
        row = await pool.fetchrow("SELECT 1 FROM blog_posts WHERE slug = $1 LIMIT 1", candidate)
        if row is None:
            return candidate
        candidate = f"{slug[:170]}-{suffix}"
        suffix += 1


def _summarize_release_notes_excerpt(notes: str, *, max_len: int = 280) -> str:
    """Build a readable excerpt from Keep-a-Changelog markdown release notes."""
    text = str(notes or "").replace("\r\n", "\n").strip()
    if not text:
        return ""

    added_items: list[str] = []
    in_added = False
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("### "):
            in_added = stripped.lower() == "### added"
            continue
        if in_added and stripped.startswith("- "):
            item = stripped[2:].strip()
            if item:
                added_items.append(item)

    if not added_items:
        for line in text.split("\n"):
            stripped = line.strip()
            if stripped.startswith("- "):
                item = stripped[2:].strip()
                if item:
                    added_items.append(item)

    if added_items:
        summary = "; ".join(added_items[:2])
        if len(added_items) > 2:
            summary = f"{summary}; and more."
    else:
        summary = re.sub(r"^#+\s*", "", text.replace("\n", " "), flags=re.MULTILINE).strip()

    if len(summary) > max_len:
        return f"{summary[: max_len - 1].rstrip()}…"
    return summary


async def unpublish_release_changelog_posts(
    pool: Any,
    *,
    version: str,
    changelog_slug: str | None = None,
) -> None:
    """Hide website changelog entries created for a rolled-back desktop version."""
    normalized_version = str(version or "").strip()
    if not normalized_version:
        return
    base_slug = _release_notes_slug_base(normalized_version)
    title = _release_notes_title(normalized_version)
    await pool.execute(
        """
        UPDATE blog_posts
        SET is_published = FALSE,
            updated_at = NOW()
        WHERE category = $1
          AND is_published = TRUE
          AND (
            slug = $2
            OR slug = $3
            OR slug LIKE $4
            OR lower(title) = lower($5)
          )
        """,
        RELEASE_NOTES_CATEGORY,
        str(changelog_slug or "").strip(),
        base_slug,
        f"{base_slug}-%",
        title,
    )


async def create_release_changelog_post(
    pool: Any,
    *,
    version: str,
    release_notes: str,
) -> str | None:
    """Create or re-publish a blog post in category Release notes. Returns slug or None if skipped."""
    normalized_version = str(version or "").strip()
    notes = str(release_notes or "").strip()
    if not normalized_version:
        return None

    title = _release_notes_title(normalized_version)
    excerpt_source = notes or f"Camxora Desktop {normalized_version} release."
    excerpt = _summarize_release_notes_excerpt(excerpt_source)
    if not excerpt:
        excerpt = f"Camxora Desktop {normalized_version} release."
    content = notes or f"Camxora Desktop {normalized_version} is now available."
    slug_base = _release_notes_slug_base(normalized_version)

    existing = await pool.fetchrow(
        """
        SELECT id, slug
        FROM blog_posts
        WHERE category = $1
          AND (
            slug = $2
            OR slug LIKE $3
            OR lower(title) = lower($4)
          )
        ORDER BY published_at DESC NULLS LAST, created_at DESC
        LIMIT 1
        """,
        RELEASE_NOTES_CATEGORY,
        slug_base,
        f"{slug_base}-%",
        title,
    )
    if existing is not None:
        published_at = datetime.now(timezone.utc)
        await pool.execute(
            """
            UPDATE blog_posts
            SET title = $2,
                excerpt = $3,
                content = $4,
                seo_title = $2,
                seo_description = $3,
                is_published = TRUE,
                published_at = COALESCE(published_at, $5),
                updated_at = NOW()
            WHERE id = $1
            """,
            existing["id"],
            title,
            excerpt,
            content,
            published_at,
        )
        return str(existing["slug"])

    slug = await _ensure_unique_blog_slug(pool, slug_base)
    published_at = datetime.now(timezone.utc)
    post_id = uuid.uuid4()

    await pool.execute(
        """
        INSERT INTO blog_posts (
            id, slug, title, excerpt, content, cover_image_url, category,
            author_name, seo_title, seo_description, is_published, published_at,
            created_at, updated_at
        )
        VALUES (
            $1, $2, $3, $4, $5, NULL, $6, $7, $8, $9, TRUE, $10, NOW(), NOW()
        )
        """,
        post_id,
        slug,
        title,
        excerpt,
        content,
        RELEASE_NOTES_CATEGORY,
        "Camxora",
        title,
        excerpt,
        published_at,
    )
    return slug


def _pick_previous_from_history(
    history: list[dict[str, Any]],
    *,
    unpublished_version: str,
    unpublished_url: str,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    remaining: list[dict[str, Any]] = []
    chosen: dict[str, Any] | None = None
    for entry in history:
        if chosen is None and not _same_installer(
            str(entry.get("download_url") or ""),
            unpublished_url,
            left_version=str(entry.get("version") or ""),
            right_version=unpublished_version,
        ):
            chosen = entry
            continue
        remaining.append(entry)
    return chosen, remaining


def _pick_previous_from_installers(
    candidates: list[InstallerCandidate],
    *,
    unpublished_version: str,
    unpublished_url: str,
    unpublished_filename: str = "",
) -> InstallerCandidate | None:
    best: InstallerCandidate | None = None
    best_tuple = (-1, -1, -1)
    unpublished_tuple = _parse_version(unpublished_version)
    for candidate in candidates:
        if _same_installer(
            candidate.download_url,
            unpublished_url,
            left_version=candidate.version,
            right_version=unpublished_version,
            filename=unpublished_filename,
        ):
            continue
        if unpublished_filename and Path(candidate.filename).name.lower() == Path(unpublished_filename).name.lower():
            continue
        version_tuple = _parse_version(candidate.version)
        if unpublished_version and version_tuple >= unpublished_tuple and unpublished_tuple != (0, 0, 0):
            continue
        if best is None or version_tuple > best_tuple:
            best = candidate
            best_tuple = version_tuple
    return best


async def _restore_previous_live(
    pool: Any,
    *,
    unpublished_version: str,
    unpublished_url: str,
    unpublished_filename: str = "",
    installer_candidates: list[InstallerCandidate] | None = None,
) -> str | None:
    history = await _load_live_history(pool)
    previous, remaining = _pick_previous_from_history(
        history,
        unpublished_version=unpublished_version,
        unpublished_url=unpublished_url,
    )
    if previous is None:
        candidate = _pick_previous_from_installers(
            installer_candidates or [],
            unpublished_version=unpublished_version,
            unpublished_url=unpublished_url,
            unpublished_filename=unpublished_filename,
        )
        if candidate is None or not candidate.version.strip() or not candidate.download_url.strip():
            await _save_live_snapshot(pool, None)
            await _save_live_history(pool, remaining)
            return None
        previous = _snapshot_from_values(
            version=candidate.version,
            download_url=candidate.download_url,
            mandatory=False,
            release_notes="",
            published_at=datetime.now(timezone.utc).isoformat(),
        )
    await _save_live_snapshot(pool, previous)
    await _save_live_history(pool, remaining)
    return str(previous.get("version") or "").strip() or None


async def unpublish_software_update(
    pool: Any,
    *,
    installer_candidates: list[InstallerCandidate] | None = None,
    unpublished_filename: str = "",
) -> UnpublishResult:
    """Move the live release back to draft and restore the previous live version."""
    live = await ensure_live_snapshot(pool)
    unpublished_version = str((live or {}).get("version") or "").strip()
    unpublished_url = str((live or {}).get("download_url") or "").strip()
    changelog_slug = str((live or {}).get("changelog_slug") or "").strip()
    if not unpublished_version:
        draft_fields = await _read_draft_fields(pool)
        unpublished_version = str(draft_fields.get("version") or "").strip()
        unpublished_url = str(draft_fields.get("download_url") or "").strip()

    if unpublished_version:
        await unpublish_release_changelog_posts(
            pool,
            version=unpublished_version,
            changelog_slug=changelog_slug or None,
        )

    restored_live_version = await _restore_previous_live(
        pool,
        unpublished_version=unpublished_version,
        unpublished_url=unpublished_url,
        unpublished_filename=unpublished_filename,
        installer_candidates=installer_candidates,
    )
    draft = await get_software_update_config(pool)
    return UnpublishResult(
        draft=draft,
        unpublished_version=unpublished_version,
        restored_live_version=restored_live_version,
    )


async def move_installer_to_draft(
    pool: Any,
    *,
    version: str,
    download_url: str,
    filename: str = "",
    installer_candidates: list[InstallerCandidate] | None = None,
) -> UnpublishResult:
    """Set an installer as the working draft. If it is live, restore the previous live release."""
    live = await ensure_live_snapshot(pool)
    unpublished_version = ""
    restored_live_version = None
    if _snapshot_is_valid(live) and _same_installer(
        str((live or {}).get("download_url") or ""),
        download_url,
        left_version=str((live or {}).get("version") or ""),
        right_version=version,
        filename=filename,
    ):
        result = await unpublish_software_update(
            pool,
            installer_candidates=installer_candidates,
            unpublished_filename=filename,
        )
        unpublished_version = result.unpublished_version
        restored_live_version = result.restored_live_version
    current = await get_software_update_config(pool)
    await save_software_update_config(
        pool,
        version=str(version or current.version).strip() or current.version,
        download_url=download_url.strip(),
        mandatory=current.mandatory,
        release_notes=current.release_notes,
    )
    draft = await get_software_update_config(pool)
    return UnpublishResult(
        draft=draft,
        unpublished_version=unpublished_version,
        restored_live_version=restored_live_version,
    )


async def sync_after_installer_delete(
    pool: Any,
    *,
    filename: str,
    download_url: str,
    version: str = "",
    installer_candidates: list[InstallerCandidate] | None = None,
) -> UnpublishResult:
    """If the deleted file was live, restore previous live; always detach it from draft."""
    live = await ensure_live_snapshot(pool)
    unpublished_version = ""
    restored_live_version = None
    if _snapshot_is_valid(live) and _same_installer(
        str((live or {}).get("download_url") or ""),
        download_url,
        left_version=str((live or {}).get("version") or ""),
        right_version=version,
        filename=filename,
    ):
        result = await unpublish_software_update(
            pool,
            installer_candidates=installer_candidates,
            unpublished_filename=filename,
        )
        unpublished_version = result.unpublished_version
        restored_live_version = result.restored_live_version

    live = await _load_live_snapshot(pool)
    draft = await _read_draft_fields(pool)
    if _same_installer(
        str(draft.get("download_url") or ""),
        download_url,
        left_version=str(draft.get("version") or ""),
        right_version=version,
        filename=filename,
    ) or _draft_installer_is_missing(draft, live, installer_candidates or []):
        await _copy_live_into_draft(pool, live)

    config = await get_software_update_config(pool)
    return UnpublishResult(
        draft=config,
        unpublished_version=unpublished_version,
        restored_live_version=restored_live_version,
    )


async def publish_software_update(
    pool: Any,
    *,
    notify_desktop_users: bool = True,
    create_changelog: bool = False,
) -> tuple[SoftwareUpdateConfig, int, str | None]:
    await ensure_live_snapshot(pool)
    config = await get_software_update_config(pool)
    if not config.version.strip():
        raise ValueError("Software update version is required before publishing.")
    if not config.download_url.strip():
        raise ValueError("Download URL is required before publishing.")

    current_live = await _load_live_snapshot(pool)
    if _snapshot_is_valid(current_live):
        current_version = str((current_live or {}).get("version") or "").strip()
        current_url = str((current_live or {}).get("download_url") or "").strip()
        if current_version and not _same_installer(
            current_url,
            config.download_url,
            left_version=current_version,
            right_version=config.version.strip(),
        ):
            history = await _load_live_history(pool)
            history = [
                entry
                for entry in history
                if not _same_installer(
                    str(entry.get("download_url") or ""),
                    current_url,
                    left_version=str(entry.get("version") or ""),
                    right_version=current_version,
                )
            ]
            history.insert(0, current_live or {})
            await _save_live_history(pool, history)

    published_at = datetime.now(timezone.utc).isoformat()
    changelog_slug = None
    if create_changelog:
        changelog_slug = await create_release_changelog_post(
            pool,
            version=config.version.strip(),
            release_notes=config.release_notes.strip(),
        )

    live_snapshot = _snapshot_from_values(
        version=config.version.strip(),
        download_url=config.download_url.strip(),
        mandatory=config.mandatory,
        release_notes=config.release_notes.strip(),
        published_at=published_at,
        changelog_slug=changelog_slug or "",
    )
    await _save_live_snapshot(pool, live_snapshot)

    recipients = 0
    if notify_desktop_users:
        user_ids = await list_active_user_ids(pool)
        for user_id in user_ids:
            await notify_software_update_available(
                user_id,
                version=config.version.strip(),
                download_url=config.download_url.strip() or None,
                mandatory=config.mandatory,
                release_notes=config.release_notes.strip() or None,
            )
        recipients = len(user_ids)

    published_config = await get_published_desktop_release(pool)
    if published_config is None:
        published_config = _config_from_snapshot(live_snapshot)
    return published_config, recipients, changelog_slug


async def _load_push_history(pool: Any) -> list[PushNotificationHistoryItem]:
    raw = await load_system_setting(pool, PUSH_NOTIFICATION_HISTORY_KEY)
    if not raw:
        return []
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []

    items: list[PushNotificationHistoryItem] = []
    for entry in payload:
        if not isinstance(entry, dict):
            continue
        items.append(
            PushNotificationHistoryItem(
                id=str(entry.get("id") or ""),
                title=str(entry.get("title") or ""),
                message=str(entry.get("message") or ""),
                created_at=str(entry.get("created_at") or ""),
                recipients=int(entry.get("recipients") or 0),
            )
        )
    return [item for item in items if item.id and item.title]


async def _save_push_history(pool: Any, items: list[PushNotificationHistoryItem]) -> None:
    payload = [
        {
            "id": item.id,
            "title": item.title,
            "message": item.message,
            "created_at": item.created_at,
            "recipients": item.recipients,
        }
        for item in items[:MAX_HISTORY_ITEMS]
    ]
    await _upsert_system_setting(
        pool,
        key=PUSH_NOTIFICATION_HISTORY_KEY,
        value=json.dumps(payload),
        value_type="json",
    )


async def list_push_notification_history(pool: Any) -> list[PushNotificationHistoryItem]:
    return await _load_push_history(pool)


async def send_push_notification(
    pool: Any,
    *,
    title: str,
    message: str,
) -> tuple[PushNotificationHistoryItem, int]:
    from platform_api.dependencies import get_notification_service

    notification_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    payload = {
        "notification_id": notification_id,
        "title": title.strip(),
        "message": message.strip(),
        "created_at": created_at,
    }

    service = get_notification_service()
    user_ids = await list_active_user_ids(pool)
    for user_id in user_ids:
        await service.push(user_id, NOTIFICATION_MESSAGE_EVENT, payload)

    history_item = PushNotificationHistoryItem(
        id=notification_id,
        title=payload["title"],
        message=payload["message"],
        created_at=created_at,
        recipients=len(user_ids),
    )
    history = [history_item, *(await _load_push_history(pool))]
    await _save_push_history(pool, history)
    logger.info(
        "Broadcast %s to %d users (notification_id=%s)",
        NOTIFICATION_MESSAGE_EVENT,
        len(user_ids),
        notification_id,
    )
    return history_item, len(user_ids)
