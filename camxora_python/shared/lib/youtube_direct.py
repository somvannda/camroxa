"""Direct desktop -> YouTube upload (resumable), no storage copy.

Shared by the in-app uploader. Mirrors scripts/youtube_direct_upload.py but uses
httpx, which is already bundled with the desktop app.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable

import httpx

UPLOAD_ENDPOINT = "https://www.googleapis.com/upload/youtube/v3/videos"
THUMB_ENDPOINT = "https://www.googleapis.com/upload/youtube/v3/thumbnails/set"
PLAYLIST_ENDPOINT = "https://www.googleapis.com/youtube/v3/playlistItems"
CATEGORY_MUSIC = "10"
CHUNK_BYTES = 16 * 1024 * 1024


class UploadCancelled(RuntimeError):
    """Raised when the user stops a transfer."""


# YouTube rejects the whole upload when the keyword block is invalid: tags may
# not contain angle brackets, must be non-empty, and the list is capped at 500
# characters in total. Studio also trims very long tags.
MAX_TAG_CHARS = 60
MAX_TAGS_TOTAL_CHARS = 500


def sanitize_tags(raw: Any) -> list[str]:
    if isinstance(raw, str):
        candidates = [part for part in raw.split(",")]
    elif isinstance(raw, (list, tuple, set)):
        candidates = [str(part) for part in raw]
    else:
        candidates = []
    tags: list[str] = []
    seen: set[str] = set()
    total = 0
    for candidate in candidates:
        text = " ".join(
            str(candidate).replace("<", "").replace(">", "").split()
        ).strip()
        if not text:
            continue
        if len(text) > MAX_TAG_CHARS:
            text = text[:MAX_TAG_CHARS].rstrip()
        key = text.lower()
        if key in seen:
            continue
        if total + len(text) + 1 > MAX_TAGS_TOTAL_CHARS:
            break
        seen.add(key)
        tags.append(text)
        total += len(text) + 1
    return tags


def album_from_path(video: Path) -> str:
    name = video.parent.name
    stem = name.split("_", 1)[1] if "_" in name else name
    return stem.replace("-", " ").replace("_", " ").strip() or video.stem


def render_template(template: str, *, album: str, channel: str) -> str:
    text = str(template or "{title}")
    for key, value in (("{title}", album), ("{album}", album), ("{channel}", channel)):
        text = text.replace(key, value)
    return " ".join(text.split())


def next_publish_at(raw: str) -> str | None:
    text = str(raw or "").strip()
    if not text:
        return None
    if "T" in text:
        return text
    try:
        hour, minute = (int(part) for part in text.split(":", 1))
    except ValueError:
        return None
    from datetime import datetime, timedelta, timezone

    local = datetime.now().astimezone()
    target = local.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= local:
        target = target + timedelta(days=1)
    return target.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def build_metadata(profile: Any, video: Path) -> dict[str, Any]:
    """Publication settings from Settings -> profile -> Publication."""
    config = dict(getattr(profile, "youtube_config", None) or {})
    album = album_from_path(video)
    channel = str(getattr(profile, "name", "") or "")

    title = render_template(str(config.get("title_template") or "{title}"), album=album, channel=channel)
    description = render_template(
        str(config.get("description_template") or ""), album=album, channel=channel
    )
    tags = sanitize_tags(config.get("tags") or "")

    visibility = str(config.get("visibility") or "private").strip().lower()
    if visibility not in {"private", "unlisted", "public", "scheduled"}:
        visibility = "private"

    thumbnail = video.parent / "thumbnail-16x9.png"
    return {
        "title": title[:100] or video.stem[:100],
        "description": description[:5000],
        "tags": tags[:30],
        "visibility": visibility,
        "publish_at": next_publish_at(str(config.get("publish_at") or ""))
        if visibility == "scheduled"
        else None,
        "category": str(config.get("category") or CATEGORY_MUSIC),
        "made_for_kids": bool(config.get("made_for_kids", False)),
        "contains_synthetic_media": bool(config.get("ai_use", False)),
        "playlist": str(config.get("playlist") or "").strip(),
        "thumbnail": str(thumbnail) if thumbnail.is_file() else None,
    }


def start_session(access_token: str, meta: dict[str, Any]) -> str:
    # The API rejects "scheduled": a scheduled video is uploaded private with
    # publishAt set, which is what YouTube Studio shows as "Scheduled".
    privacy = meta["visibility"]
    scheduled = privacy == "scheduled" and bool(meta.get("publish_at"))
    status: dict[str, Any] = {
        "privacyStatus": "private" if privacy == "scheduled" else privacy,
        "selfDeclaredMadeForKids": bool(meta["made_for_kids"]),
        "containsSyntheticMedia": bool(meta["contains_synthetic_media"]),
    }
    if scheduled:
        status["publishAt"] = meta["publish_at"]
    body = {
        "snippet": {
            "title": meta["title"],
            "description": meta["description"],
            "tags": meta["tags"],
            "categoryId": meta["category"] or CATEGORY_MUSIC,
        },
        "status": status,
    }
    with httpx.Client(timeout=60.0) as client:
        response = client.post(
            UPLOAD_ENDPOINT,
            params={"uploadType": "resumable", "part": "snippet,status"},
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json; charset=UTF-8",
                "X-Upload-Content-Type": "video/*",
            },
            json=body,
        )
    if response.status_code >= 400:
        raise RuntimeError(f"YouTube refused the upload session: {response.status_code} {response.text[:300]}")
    session_url = response.headers.get("Location", "")
    if not session_url:
        raise RuntimeError("YouTube did not return a resumable session URL.")
    return session_url


def upload_file(
    session_url: str,
    path: Path,
    *,
    chunk_bytes: int = CHUNK_BYTES,
    on_progress: Callable[[int, int], None] | None = None,
    is_cancelled: Callable[[], bool] | None = None,
) -> dict[str, Any]:
    size = path.stat().st_size
    offset = 0
    timeout = httpx.Timeout(900.0, connect=30.0)

    with httpx.Client(timeout=timeout) as client:
        probe = client.put(session_url, headers={"Content-Range": f"bytes */{size}"})
        if probe.status_code in (200, 201):
            return probe.json()
        if probe.status_code == 308:
            received = probe.headers.get("Range", "")
            if "-" in received:
                offset = int(received.rsplit("-", 1)[1]) + 1
        if on_progress:
            on_progress(offset, size)

        with path.open("rb") as handle:
            while offset < size:
                if is_cancelled is not None and is_cancelled():
                    raise UploadCancelled("Upload cancelled.")
                handle.seek(offset)
                payload = handle.read(chunk_bytes)
                response = client.put(
                    session_url,
                    content=payload,
                    headers={
                        "Content-Range": f"bytes {offset}-{offset + len(payload) - 1}/{size}",
                        "Content-Type": "video/*",
                    },
                )
                if response.status_code in (200, 201):
                    return response.json()
                if response.status_code != 308:
                    raise RuntimeError(
                        f"Upload failed at byte {offset}: {response.status_code} {response.text[:300]}"
                    )
                received = response.headers.get("Range", "")
                offset = (
                    int(received.rsplit("-", 1)[1]) + 1
                    if "-" in received
                    else offset + len(payload)
                )
                if on_progress:
                    on_progress(offset, size)
    raise RuntimeError("Upload ended without a video id.")


def set_thumbnail(access_token: str, video_id: str, path: Path) -> str | None:
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    with path.open("rb") as handle, httpx.Client(timeout=120.0) as client:
        response = client.post(
            THUMB_ENDPOINT,
            params={"videoId": video_id},
            headers={"Authorization": f"Bearer {access_token}"},
            files={"file": (path.name, handle, mime)},
        )
    return None if response.status_code < 400 else f"thumbnail failed: {response.status_code}"


def add_to_playlist(access_token: str, playlist_id: str, video_id: str) -> str | None:
    with httpx.Client(timeout=60.0) as client:
        response = client.post(
            PLAYLIST_ENDPOINT,
            params={"part": "snippet"},
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "snippet": {
                    "playlistId": playlist_id,
                    "resourceId": {"kind": "youtube#video", "videoId": video_id},
                }
            },
        )
    if response.status_code >= 400:
        return f"playlist failed: {response.status_code}"
    return None


def video_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


def human_bytes(value: float) -> str:
    return f"{value / 1048576:.0f} MB" if value < 1073741824 else f"{value / 1073741824:.2f} GB"


def elapsed_label(started: float) -> str:
    seconds = max(0.0, time.time() - started)
    minutes = int(seconds // 60)
    return f"{minutes}m" if minutes < 60 else f"{minutes // 60}h {minutes % 60}m"
