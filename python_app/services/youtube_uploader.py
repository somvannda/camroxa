from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass(frozen=True)
class UploadResult:
    video_id: str
    url: str
    thumbnail_error: str = ""
    playlist_item_id: str = ""
    playlist_error: str = ""


@dataclass(frozen=True)
class VideoProcessingStatus:
    processing_status: str
    upload_status: str
    rejection_reason: str = ""
    failure_reason: str = ""


def _make_youtube_service(*, client_id: str, client_secret: str, refresh_token: str, scopes: list[str]) -> Any:
    cid = str(client_id or "").strip()
    sec = str(client_secret or "").strip()
    rt = str(refresh_token or "").strip()
    scopes2 = [str(s).strip() for s in (scopes or []) if str(s).strip()]
    if not cid or not sec or not rt:
        raise ValueError("Missing OAuth credentials")
    if not scopes2:
        raise ValueError("Missing OAuth scopes")
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
    except Exception as exc:
        raise RuntimeError(f"Missing Google libraries: {exc}")
    creds = Credentials(
        token=None,
        refresh_token=rt,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=cid,
        client_secret=sec,
        scopes=scopes2,
    )
    creds.refresh(Request())
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def get_video_processing_status(
    *,
    video_id: str,
    client_id: str,
    client_secret: str,
    refresh_token: str,
    scopes: list[str],
) -> VideoProcessingStatus:
    vid = str(video_id or "").strip()
    if not vid:
        raise ValueError("Missing video_id")
    service = _make_youtube_service(client_id=client_id, client_secret=client_secret, refresh_token=refresh_token, scopes=scopes)
    resp = service.videos().list(part="status,processingDetails", id=vid, maxResults=1).execute()
    items = resp.get("items") if isinstance(resp, dict) else None
    row = items[0] if isinstance(items, list) and items else {}
    status = row.get("status") if isinstance(row, dict) else {}
    proc = row.get("processingDetails") if isinstance(row, dict) else {}
    upload_status = str((status or {}).get("uploadStatus", "")).strip()
    rejection_reason = str((status or {}).get("rejectionReason", "")).strip()
    processing_status = str((proc or {}).get("processingStatus", "")).strip()
    failure_reason = str((proc or {}).get("processingFailureReason", "")).strip()
    return VideoProcessingStatus(
        processing_status=processing_status,
        upload_status=upload_status,
        rejection_reason=rejection_reason,
        failure_reason=failure_reason,
    )


def set_thumbnail(
    *,
    video_id: str,
    thumbnail_path: str,
    client_id: str,
    client_secret: str,
    refresh_token: str,
    scopes: list[str],
    cancel_event: Any = None,
) -> str:
    vid = str(video_id or "").strip()
    tp = str(thumbnail_path or "").strip()
    if not vid:
        raise ValueError("Missing video_id")
    if not tp:
        raise ValueError("Missing thumbnail_path")
    p = Path(tp)
    if not p.exists() or not p.is_file():
        raise FileNotFoundError(tp)
    if cancel_event is not None and getattr(cancel_event, "is_set", lambda: False)():
        raise RuntimeError("Upload cancelled")
    service = _make_youtube_service(client_id=client_id, client_secret=client_secret, refresh_token=refresh_token, scopes=scopes)
    try:
        from googleapiclient.http import MediaFileUpload
    except Exception as exc:
        raise RuntimeError(f"Missing Google libraries: {exc}")
    prepared_path = p
    cleanup_path: Path | None = None
    mime = "image/png" if p.name.lower().endswith(".png") else "image/jpeg" if (p.name.lower().endswith(".jpg") or p.name.lower().endswith(".jpeg")) else "image/png"
    try:
        try:
            size = int(p.stat().st_size)
        except Exception:
            size = 0
        if size >= int(1.9 * 1024 * 1024) or mime == "image/png":
            try:
                import tempfile
                from PIL import Image

                tmp = tempfile.NamedTemporaryFile(prefix="ytthumb_", suffix=".jpg", delete=False)
                tmp_path = Path(str(tmp.name))
                tmp.close()
                img = Image.open(p)
                img = img.convert("RGB")
                w, h = img.size
                max_side = max(int(w or 0), int(h or 0))
                if max_side > 1280:
                    scale = 1280.0 / float(max_side)
                    nw = max(1, int(round(float(w) * scale)))
                    nh = max(1, int(round(float(h) * scale)))
                    img = img.resize((nw, nh))
                quality = 85
                while True:
                    img.save(str(tmp_path), format="JPEG", quality=int(quality), optimize=True, progressive=True)
                    try:
                        out_size = int(tmp_path.stat().st_size)
                    except Exception:
                        out_size = 0
                    if out_size <= int(1.9 * 1024 * 1024) or quality <= 45:
                        break
                    quality -= 10
                prepared_path = tmp_path
                cleanup_path = tmp_path
                mime = "image/jpeg"
            except Exception:
                prepared_path = p
                cleanup_path = None
        if cancel_event is not None and getattr(cancel_event, "is_set", lambda: False)():
            raise RuntimeError("Upload cancelled")
        service.thumbnails().set(videoId=vid, media_body=MediaFileUpload(str(prepared_path), mimetype=mime)).execute()
        return ""
    except Exception as exc:
        msg = str(exc).strip() or "Failed to set thumbnail"
        lowm = msg.lower()
        if "not verified" in lowm or "custom thumbnail" in lowm:
            msg = "Custom thumbnails are not enabled for this YouTube channel/account. Verify the channel/account and enable custom thumbnails, then retry."
        elif "too large" in lowm or "file size" in lowm:
            msg = f"Thumbnail rejected by YouTube (size/format). Try a smaller JPG thumbnail. Details: {msg}"
        return msg
    finally:
        if cleanup_path is not None:
            try:
                cleanup_path.unlink(missing_ok=True)
            except Exception:
                pass


def add_to_playlist(
    *,
    video_id: str,
    playlist_id: str,
    client_id: str,
    client_secret: str,
    refresh_token: str,
    scopes: list[str],
    cancel_event: Any = None,
) -> str:
    vid = str(video_id or "").strip()
    plid = str(playlist_id or "").strip()
    if not vid:
        raise ValueError("Missing video_id")
    if not plid:
        raise ValueError("Missing playlist_id")
    if cancel_event is not None and getattr(cancel_event, "is_set", lambda: False)():
        raise RuntimeError("Upload cancelled")
    service = _make_youtube_service(client_id=client_id, client_secret=client_secret, refresh_token=refresh_token, scopes=scopes)
    try:
        if cancel_event is not None and getattr(cancel_event, "is_set", lambda: False)():
            raise RuntimeError("Upload cancelled")
        service.playlistItems().insert(
            part="snippet",
            body={"snippet": {"playlistId": plid, "resourceId": {"kind": "youtube#video", "videoId": vid}}},
        ).execute()
        return ""
    except Exception as exc:
        msg = str(exc).strip() or "Failed to add uploaded video to playlist"
        lowm = msg.lower()
        if "insufficient authentication scopes" in lowm or "insufficientpermission" in lowm:
            msg = "Playlist action requires additional OAuth permissions. Disconnect and reconnect this profile to YouTube, approve the new permissions, then retry."
        return msg


def list_playlists(
    *,
    client_id: str,
    client_secret: str,
    refresh_token: str,
    scopes: list[str],
) -> list[dict[str, str]]:
    cid = str(client_id or "").strip()
    sec = str(client_secret or "").strip()
    rt = str(refresh_token or "").strip()
    scopes2 = [str(s).strip() for s in (scopes or []) if str(s).strip()]
    if not cid or not sec or not rt:
        raise ValueError("Missing OAuth credentials")
    if not scopes2:
        raise ValueError("Missing OAuth scopes")
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
    except Exception as exc:
        raise RuntimeError(f"Missing Google libraries: {exc}")
    creds = Credentials(
        token=None,
        refresh_token=rt,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=cid,
        client_secret=sec,
        scopes=scopes2,
    )
    creds.refresh(Request())
    service = build("youtube", "v3", credentials=creds, cache_discovery=False)
    out: list[dict[str, str]] = []
    token = None
    while True:
        try:
            resp = service.playlists().list(part="snippet", mine=True, maxResults=50, pageToken=token).execute()
        except Exception as exc:
            msg = str(exc).strip() or "Failed to list playlists"
            lowm = msg.lower()
            if "insufficient authentication scopes" in lowm or "insufficientpermission" in lowm:
                raise RuntimeError(
                    "Playlist list requires additional OAuth permissions. Disconnect and reconnect this profile to YouTube, approve the new permissions, then refresh playlists."
                )
            raise
        items = resp.get("items") if isinstance(resp, dict) else None
        if isinstance(items, list):
            for row in items:
                if not isinstance(row, dict):
                    continue
                pid = str(row.get("id", "")).strip()
                snippet = row.get("snippet") if isinstance(row.get("snippet"), dict) else {}
                title = str(snippet.get("title", "")).strip()
                if pid:
                    out.append({"id": pid, "title": title})
        token = str(resp.get("nextPageToken", "")).strip() if isinstance(resp, dict) else ""
        if not token:
            break
    return out


def upload_video(
    *,
    file_path: str,
    thumbnail_path: str = "",
    playlist_id: str = "",
    client_id: str,
    client_secret: str,
    refresh_token: str,
    scopes: list[str],
    title: str,
    description: str,
    tags: list[str],
    category_id: str,
    made_for_kids: bool,
    contains_synthetic_media: bool,
    privacy_status: str,
    publish_at: str,
    on_progress: Callable[[float], None] | None = None,
    cancel_event: Any = None,
    chunk_size_mb: int = 256,
) -> UploadResult:
    fp = str(file_path or "").strip()
    if not fp:
        raise ValueError("Missing file_path")
    p = Path(fp)
    if not p.exists() or not p.is_file():
        raise FileNotFoundError(fp)
    cid = str(client_id or "").strip()
    sec = str(client_secret or "").strip()
    rt = str(refresh_token or "").strip()
    if not cid or not sec or not rt:
        raise ValueError("Missing OAuth credentials")
    scopes2 = [str(s).strip() for s in (scopes or []) if str(s).strip()]
    if not scopes2:
        raise ValueError("Missing OAuth scopes")
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
    except Exception as exc:
        raise RuntimeError(f"Missing Google libraries: {exc}")

    # #region debug-point A:oauth-refresh-start
    try:
        import json, urllib.request

        _p = ".dbg/youtube-upload-issues.env"
        _u, _s = "http://127.0.0.1:7777/event", "youtube-upload-issues"
        exec(
            "try:\n"
            "  with open(_p,'r',encoding='utf-8') as f:\n"
            "    c=f.read()\n"
            "  _u=next((l.split('=',1)[1] for l in c.split('\\n') if l.startswith('DEBUG_SERVER_URL=')),_u)\n"
            "  _s=next((l.split('=',1)[1] for l in c.split('\\n') if l.startswith('DEBUG_SESSION_ID=')),_s)\n"
            "except: pass"
        )
        try:
            sz = int(p.stat().st_size)
        except Exception:
            sz = 0
        urllib.request.urlopen(
            urllib.request.Request(
                _u,
                data=json.dumps(
                    {
                        "sessionId": _s,
                        "runId": "pre",
                        "hypothesisId": "A",
                        "location": "youtube_uploader.py:upload_video",
                        "msg": "[DEBUG] oauth refresh starting",
                        "data": {"fileName": p.name, "fileSize": sz, "scopesCount": len(scopes2), "chunkSizeMb": int(chunk_size_mb or 0)},
                    }
                ).encode(),
                headers={"Content-Type": "application/json"},
            ),
            timeout=0.2,
        ).read()
    except Exception:
        pass
    # #endregion

    creds = Credentials(
        token=None,
        refresh_token=rt,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=cid,
        client_secret=sec,
        scopes=scopes2,
    )
    try:
        creds.refresh(Request())
        # #region debug-point A:oauth-refresh-ok
        try:
            import json, urllib.request

            _p = ".dbg/youtube-upload-issues.env"
            _u, _s = "http://127.0.0.1:7777/event", "youtube-upload-issues"
            exec(
                "try:\n"
                "  with open(_p,'r',encoding='utf-8') as f:\n"
                "    c=f.read()\n"
                "  _u=next((l.split('=',1)[1] for l in c.split('\\n') if l.startswith('DEBUG_SERVER_URL=')),_u)\n"
                "  _s=next((l.split('=',1)[1] for l in c.split('\\n') if l.startswith('DEBUG_SESSION_ID=')),_s)\n"
                "except: pass"
            )
            urllib.request.urlopen(
                urllib.request.Request(
                    _u,
                    data=json.dumps(
                        {
                            "sessionId": _s,
                            "runId": "pre",
                            "hypothesisId": "A",
                            "location": "youtube_uploader.py:upload_video",
                            "msg": "[DEBUG] oauth refresh ok",
                            "data": {"fileName": p.name},
                        }
                    ).encode(),
                    headers={"Content-Type": "application/json"},
                ),
                timeout=0.2,
            ).read()
        except Exception:
            pass
        # #endregion
    except Exception as exc:
        # #region debug-point A:oauth-refresh-failed
        try:
            import json, urllib.request

            _p = ".dbg/youtube-upload-issues.env"
            _u, _s = "http://127.0.0.1:7777/event", "youtube-upload-issues"
            exec(
                "try:\n"
                "  with open(_p,'r',encoding='utf-8') as f:\n"
                "    c=f.read()\n"
                "  _u=next((l.split('=',1)[1] for l in c.split('\\n') if l.startswith('DEBUG_SERVER_URL=')),_u)\n"
                "  _s=next((l.split('=',1)[1] for l in c.split('\\n') if l.startswith('DEBUG_SESSION_ID=')),_s)\n"
                "except: pass"
            )
            urllib.request.urlopen(
                urllib.request.Request(
                    _u,
                    data=json.dumps(
                        {
                            "sessionId": _s,
                            "runId": "pre",
                            "hypothesisId": "A",
                            "location": "youtube_uploader.py:upload_video",
                            "msg": "[DEBUG] oauth refresh failed",
                            "data": {"fileName": p.name, "excType": type(exc).__name__, "message": str(exc)[:400]},
                        }
                    ).encode(),
                    headers={"Content-Type": "application/json"},
                ),
                timeout=0.2,
            ).read()
        except Exception:
            pass
        # #endregion
        raise
    service = build("youtube", "v3", credentials=creds, cache_discovery=False)

    snippet: dict = {"title": str(title or "").strip() or p.stem, "description": str(description or "")}
    tag_list = [str(t).strip() for t in (tags or []) if str(t).strip()]
    if tag_list:
        snippet["tags"] = tag_list
    cat = str(category_id or "").strip()
    if cat:
        snippet["categoryId"] = cat

    status: dict = {
        "privacyStatus": str(privacy_status or "unlisted").strip() or "unlisted",
        "selfDeclaredMadeForKids": bool(made_for_kids),
        "containsSyntheticMedia": bool(contains_synthetic_media),
    }
    pa = str(publish_at or "").strip()
    if pa:
        status["privacyStatus"] = "private"
        status["publishAt"] = pa

    body = {"snippet": snippet, "status": status}
    mb = int(chunk_size_mb or 256)
    mb = max(8, min(512, mb))
    chunksize = mb * 1024 * 1024
    q = 256 * 1024
    chunksize = max(q, int(chunksize / q) * q)
    media = MediaFileUpload(fp, chunksize=chunksize, resumable=True)
    req = service.videos().insert(part="snippet,status", body=body, media_body=media)
    response = None
    while response is None:
        if cancel_event is not None and getattr(cancel_event, "is_set", lambda: False)():
            raise RuntimeError("Upload cancelled")
        try:
            status_obj, response = req.next_chunk(num_retries=3)
        except Exception as exc:
            # #region debug-point C:next-chunk-exception
            try:
                import json, urllib.request

                _p = ".dbg/youtube-upload-issues.env"
                _u, _s = "http://127.0.0.1:7777/event", "youtube-upload-issues"
                exec(
                    "try:\n"
                    "  with open(_p,'r',encoding='utf-8') as f:\n"
                    "    c=f.read()\n"
                    "  _u=next((l.split('=',1)[1] for l in c.split('\\n') if l.startswith('DEBUG_SERVER_URL=')),_u)\n"
                    "  _s=next((l.split('=',1)[1] for l in c.split('\\n') if l.startswith('DEBUG_SESSION_ID=')),_s)\n"
                    "except: pass"
                )
                code = getattr(getattr(exc, "resp", None), "status", None)
                urllib.request.urlopen(
                    urllib.request.Request(
                        _u,
                        data=json.dumps(
                            {
                                "sessionId": _s,
                                "runId": "pre",
                                "hypothesisId": "C",
                                "location": "youtube_uploader.py:upload_video",
                                "msg": "[DEBUG] next_chunk exception",
                                "data": {"fileName": p.name, "excType": type(exc).__name__, "httpStatus": int(code) if isinstance(code, int) else None, "message": str(exc)[:400]},
                            }
                        ).encode(),
                        headers={"Content-Type": "application/json"},
                    ),
                    timeout=0.2,
                ).read()
            except Exception:
                pass
            # #endregion
            raise
        if status_obj is not None and on_progress is not None:
            try:
                on_progress(float(status_obj.progress() or 0.0))
            except Exception:
                pass
    vid = str((response or {}).get("id", "")).strip()
    if not vid:
        raise RuntimeError("Upload succeeded but video id is missing in response")
    # #region debug-point C:upload-ok
    try:
        import json, urllib.request

        _p = ".dbg/youtube-upload-issues.env"
        _u, _s = "http://127.0.0.1:7777/event", "youtube-upload-issues"
        exec(
            "try:\n"
            "  with open(_p,'r',encoding='utf-8') as f:\n"
            "    c=f.read()\n"
            "  _u=next((l.split('=',1)[1] for l in c.split('\\n') if l.startswith('DEBUG_SERVER_URL=')),_u)\n"
            "  _s=next((l.split('=',1)[1] for l in c.split('\\n') if l.startswith('DEBUG_SESSION_ID=')),_s)\n"
            "except: pass"
        )
        urllib.request.urlopen(
            urllib.request.Request(
                _u,
                data=json.dumps(
                    {"sessionId": _s, "runId": "pre", "hypothesisId": "C", "location": "youtube_uploader.py:upload_video", "msg": "[DEBUG] upload ok", "data": {"fileName": p.name, "videoId": vid}}
                ).encode(),
                headers={"Content-Type": "application/json"},
            ),
            timeout=0.2,
        ).read()
    except Exception:
        pass
    # #endregion
    playlist_item_id = ""
    playlist_error = ""
    thumbnail_error = ""
    if cancel_event is not None and getattr(cancel_event, "is_set", lambda: False)():
        plid0 = str(playlist_id or "").strip()
        return UploadResult(
            video_id=vid,
            url=f"https://www.youtube.com/watch?v={vid}",
            thumbnail_error="Cancelled by user",
            playlist_item_id="",
            playlist_error="Cancelled by user" if plid0 else "",
        )
    thumb = str(thumbnail_path or "").strip()
    if thumb:
        tp = Path(thumb)
        if not tp.exists() or not tp.is_file():
            raise FileNotFoundError(thumb)
        prepared_path = tp
        cleanup_path: Path | None = None
        try:
            low = tp.name.lower()
            mime = "image/png" if low.endswith(".png") else "image/jpeg" if (low.endswith(".jpg") or low.endswith(".jpeg")) else "image/png"
            try:
                size = int(tp.stat().st_size)
            except Exception:
                size = 0
            if size >= int(1.9 * 1024 * 1024) or mime == "image/png":
                try:
                    import tempfile
                    from PIL import Image

                    tmp = tempfile.NamedTemporaryFile(prefix="ytthumb_", suffix=".jpg", delete=False)
                    tmp_path = Path(str(tmp.name))
                    tmp.close()
                    img = Image.open(tp)
                    img = img.convert("RGB")
                    w, h = img.size
                    max_side = max(int(w or 0), int(h or 0))
                    if max_side > 1280:
                        scale = 1280.0 / float(max_side)
                        nw = max(1, int(round(float(w) * scale)))
                        nh = max(1, int(round(float(h) * scale)))
                        img = img.resize((nw, nh))
                    quality = 85
                    while True:
                        img.save(str(tmp_path), format="JPEG", quality=int(quality), optimize=True, progressive=True)
                        try:
                            out_size = int(tmp_path.stat().st_size)
                        except Exception:
                            out_size = 0
                        if out_size <= int(1.9 * 1024 * 1024) or quality <= 45:
                            break
                        quality -= 10
                    prepared_path = tmp_path
                    cleanup_path = tmp_path
                    mime = "image/jpeg"
                except Exception:
                    prepared_path = tp
                    cleanup_path = None
            service.thumbnails().set(videoId=vid, media_body=MediaFileUpload(str(prepared_path), mimetype=mime)).execute()
        except Exception as exc:
            msg = str(exc).strip() or "Failed to set thumbnail"
            lowm = msg.lower()
            if "not verified" in lowm or "custom thumbnail" in lowm:
                msg = "Custom thumbnails are not enabled for this YouTube channel/account. Verify the channel/account and enable custom thumbnails, then retry."
            elif "too large" in lowm or "file size" in lowm:
                msg = f"Thumbnail rejected by YouTube (size/format). Try a smaller JPG thumbnail. Details: {msg}"
            thumbnail_error = msg
        finally:
            if cleanup_path is not None:
                try:
                    cleanup_path.unlink(missing_ok=True)
                except Exception:
                    pass
    if cancel_event is not None and getattr(cancel_event, "is_set", lambda: False)():
        plid0 = str(playlist_id or "").strip()
        return UploadResult(
            video_id=vid,
            url=f"https://www.youtube.com/watch?v={vid}",
            thumbnail_error=thumbnail_error or "Cancelled by user",
            playlist_item_id="",
            playlist_error="Cancelled by user" if plid0 else "",
        )
    plid = str(playlist_id or "").strip()
    if plid:
        try:
            resp = (
                service.playlistItems()
                .insert(
                    part="snippet",
                    body={
                        "snippet": {
                            "playlistId": plid,
                            "resourceId": {"kind": "youtube#video", "videoId": vid},
                        }
                    },
                )
                .execute()
            )
            playlist_item_id = str((resp or {}).get("id", "")).strip()
        except Exception as exc:
            if cancel_event is not None and getattr(cancel_event, "is_set", lambda: False)():
                return UploadResult(
                    video_id=vid,
                    url=f"https://www.youtube.com/watch?v={vid}",
                    thumbnail_error=thumbnail_error,
                    playlist_item_id="",
                    playlist_error="Cancelled by user",
                )
            msg = str(exc).strip() or "Failed to add uploaded video to playlist"
            lowm = msg.lower()
            if "insufficient authentication scopes" in lowm or "insufficientpermission" in lowm:
                msg = "Playlist action requires additional OAuth permissions. Disconnect and reconnect this profile to YouTube, approve the new permissions, then retry."
            playlist_error = msg
    return UploadResult(
        video_id=vid,
        url=f"https://www.youtube.com/watch?v={vid}",
        thumbnail_error=thumbnail_error,
        playlist_item_id=playlist_item_id,
        playlist_error=playlist_error,
    )
