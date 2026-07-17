from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class UploadResult:
    video_id: str
    url: str
    thumbnail_error: str = ""
    playlist_error: str = ""


@dataclass(frozen=True, slots=True)
class VideoProcessingStatus:
    processing_status: str
    upload_status: str
    rejection_reason: str = ""
    failure_reason: str = ""


def _build_youtube_service(credentials: Any) -> Any:
    try:
        from googleapiclient.discovery import build
    except Exception as exc:
        raise RuntimeError(f"Missing Google API client libraries: {exc}") from exc
    return build("youtube", "v3", credentials=credentials, cache_discovery=False)


def get_video_processing_status(*, credentials: Any, video_id: str) -> VideoProcessingStatus:
    vid = str(video_id or "").strip()
    if not vid:
        raise ValueError("Missing video_id")

    service = _build_youtube_service(credentials)
    response = service.videos().list(part="status,processingDetails", id=vid, maxResults=1).execute()
    items = response.get("items") if isinstance(response, dict) else None
    row = items[0] if isinstance(items, list) and items else {}
    status = row.get("status") if isinstance(row, dict) else {}
    proc = row.get("processingDetails") if isinstance(row, dict) else {}

    return VideoProcessingStatus(
        processing_status=str((proc or {}).get("processingStatus", "")).strip(),
        upload_status=str((status or {}).get("uploadStatus", "")).strip(),
        rejection_reason=str((status or {}).get("rejectionReason", "")).strip(),
        failure_reason=str((proc or {}).get("processingFailureReason", "")).strip(),
    )


def set_thumbnail(*, credentials: Any, video_id: str, thumbnail_path: str) -> str:
    vid = str(video_id or "").strip()
    thumb = str(thumbnail_path or "").strip()
    if not vid:
        raise ValueError("Missing video_id")
    if not thumb:
        raise ValueError("Missing thumbnail_path")

    path = Path(thumb)
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(thumb)

    try:
        from googleapiclient.http import MediaFileUpload
    except Exception as exc:
        raise RuntimeError(f"Missing Google API client libraries: {exc}") from exc

    service = _build_youtube_service(credentials)
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    try:
        service.thumbnails().set(
            videoId=vid,
            media_body=MediaFileUpload(str(path), mimetype=mime),
        ).execute()
        return ""
    except Exception as exc:
        message = str(exc).strip() or "Failed to set thumbnail"
        lower = message.lower()
        if "not verified" in lower or "custom thumbnail" in lower:
            return (
                "Custom thumbnails are not enabled for this YouTube channel/account. "
                "Verify the channel/account and enable custom thumbnails, then retry."
            )
        if "too large" in lower or "file size" in lower:
            return f"Thumbnail rejected by YouTube (size/format). Details: {message}"
        return message


def add_to_playlist(*, credentials: Any, video_id: str, playlist_id: str) -> str:
    vid = str(video_id or "").strip()
    playlist = str(playlist_id or "").strip()
    if not vid:
        raise ValueError("Missing video_id")
    if not playlist:
        raise ValueError("Missing playlist_id")

    service = _build_youtube_service(credentials)
    try:
        service.playlistItems().insert(
            part="snippet",
            body={
                "snippet": {
                    "playlistId": playlist,
                    "resourceId": {"kind": "youtube#video", "videoId": vid},
                }
            },
        ).execute()
        return ""
    except Exception as exc:
        message = str(exc).strip() or "Failed to add uploaded video to playlist"
        lower = message.lower()
        if "insufficient authentication scopes" in lower or "insufficientpermission" in lower:
            return (
                "Playlist action requires additional OAuth permissions. "
                "Disconnect and reconnect this profile to YouTube, approve the new permissions, then retry."
            )
        return message


def upload_video(
    *,
    credentials: Any,
    file_path: str,
    title: str,
    description: str,
    tags: list[str],
    category_id: str,
    made_for_kids: bool,
    contains_synthetic_media: bool,
    privacy_status: str,
    publish_at: str,
    thumbnail_path: str = "",
    playlist_id: str = "",
    chunk_size_mb: int = 256,
) -> UploadResult:
    target = str(file_path or "").strip()
    if not target:
        raise ValueError("Missing file_path")

    path = Path(target)
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(target)

    try:
        from googleapiclient.http import MediaFileUpload
    except Exception as exc:
        raise RuntimeError(f"Missing Google API client libraries: {exc}") from exc

    chunk_size = max(8, int(chunk_size_mb or 256)) * 1024 * 1024
    service = _build_youtube_service(credentials)

    snippet: dict[str, Any] = {
        "title": str(title or "").strip()[:100],
        "description": str(description or "").strip(),
        "tags": [str(tag).strip() for tag in (tags or []) if str(tag).strip()],
    }
    if str(category_id or "").strip():
        snippet["categoryId"] = str(category_id).strip()

    status: dict[str, Any] = {
        "privacyStatus": str(privacy_status or "private").strip() or "private",
        "selfDeclaredMadeForKids": bool(made_for_kids),
        "containsSyntheticMedia": bool(contains_synthetic_media),
    }
    if str(publish_at or "").strip():
        status["publishAt"] = str(publish_at).strip()

    request = service.videos().insert(
        part="snippet,status",
        body={"snippet": snippet, "status": status},
        media_body=MediaFileUpload(str(path), chunksize=chunk_size, resumable=True),
    )

    response = None
    while response is None:
        _, response = request.next_chunk(num_retries=3)

    video_id = str((response or {}).get("id") or "").strip()
    if not video_id:
        raise RuntimeError("YouTube upload completed without returning a video id.")

    url = f"https://www.youtube.com/watch?v={video_id}"
    thumbnail_error = ""
    playlist_error = ""
    if str(thumbnail_path or "").strip():
        thumbnail_error = set_thumbnail(
            credentials=credentials,
            video_id=video_id,
            thumbnail_path=thumbnail_path,
        )
    if str(playlist_id or "").strip():
        playlist_error = add_to_playlist(
            credentials=credentials,
            video_id=video_id,
            playlist_id=playlist_id,
        )

    return UploadResult(
        video_id=video_id,
        url=url,
        thumbnail_error=thumbnail_error,
        playlist_error=playlist_error,
    )
