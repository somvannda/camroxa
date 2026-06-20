from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class YouTubeOAuthResult:
    refresh_token: str
    channel_id: str
    channel_title: str
    scopes: list[str]
    channels: list[dict[str, str]]


YOUTUBE_UPLOAD_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]


def oauth_connect(client_id: str, client_secret: str, scopes: list[str] | None = None) -> YouTubeOAuthResult:
    cid = str(client_id or "").strip()
    sec = str(client_secret or "").strip()
    if not cid or not sec:
        raise ValueError("YouTube OAuth client id/secret is missing")
    use_scopes = [str(s).strip() for s in (scopes or YOUTUBE_UPLOAD_SCOPES) if str(s).strip()]
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except Exception as exc:
        raise RuntimeError(f"Missing Google libraries: {exc}")
    config = {
        "installed": {
            "client_id": cid,
            "client_secret": sec,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }
    flow = InstalledAppFlow.from_client_config(config, scopes=use_scopes)
    creds = flow.run_local_server(
        host="127.0.0.1",
        port=0,
        open_browser=True,
        access_type="offline",
        prompt="consent",
        include_granted_scopes="true",
    )
    refresh_token = str(getattr(creds, "refresh_token", "") or "").strip()
    if not refresh_token:
        raise RuntimeError("OAuth did not return a refresh_token. Ensure consent prompt and offline access are enabled.")
    service = build("youtube", "v3", credentials=creds, cache_discovery=False)
    resp = service.channels().list(part="snippet", mine=True, maxResults=50).execute()
    items = resp.get("items") if isinstance(resp, dict) else None
    channels: list[dict[str, str]] = []
    if isinstance(items, list):
        for row in items:
            if not isinstance(row, dict):
                continue
            cid2 = str(row.get("id", "")).strip()
            snippet = row.get("snippet") if isinstance(row.get("snippet"), dict) else {}
            title2 = str(snippet.get("title", "")).strip()
            if cid2:
                channels.append({"id": cid2, "title": title2})
    if not channels:
        raise RuntimeError("Unable to read YouTube channel list from the authenticated account.")
    channel_id = str(channels[0].get("id", "")).strip()
    channel_title = str(channels[0].get("title", "")).strip()
    return YouTubeOAuthResult(refresh_token=refresh_token, channel_id=channel_id, channel_title=channel_title, scopes=use_scopes, channels=channels)
