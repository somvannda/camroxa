"""Direct YouTube upload demo client.

Connects a channel through CAMXORA's own Google client, then uploads a video
straight to YouTube with the resumable API -- no storage copy and no third-party
publisher. This is the reference client for the audit form ("complete working
upload script").

Prerequisites
-------------
1. The CAMXORA desktop app is signed in on this machine (the script reuses its
   stored session; it never asks for your password).
2. The Google Cloud project behind CAMXORA has YouTube Data API v3 enabled and
   `https://api.camxora.com/api/v3/youtube/oauth/callback` registered.

Usage
-----
    python scripts/youtube_direct_upload.py --list-profiles
    python scripts/youtube_direct_upload.py --connect --profile "<name or id>"
    python scripts/youtube_direct_upload.py --video "F:/run/MERGED_OK.mp4" \
        --title "My song" --batch-id <uuid> --role OK

Options: --description, --tags, --privacy (private|unlisted|public), --thumbnail,
--playlist, --chunk-mb, --profile.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import webbrowser
from pathlib import Path
from typing import Any

import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
DESKTOP_ROOT = REPO_ROOT / "camxora_python"
if str(DESKTOP_ROOT) not in sys.path:
    sys.path.insert(0, str(DESKTOP_ROOT))

API_BASE = "https://api.camxora.com/api/v3"
UPLOAD_ENDPOINT = "https://www.googleapis.com/upload/youtube/v3/videos"
THUMB_ENDPOINT = "https://www.googleapis.com/upload/youtube/v3/thumbnails/set"
CATEGORY_MUSIC = "10"


class _FixedBaseStorage:
    """Storage shim: the desktop app's store, pinned to the production API.

    The repo runs without the bundled build config, so SecureStorage would fall
    back to localhost. Everything else (sessions, token decoding) still comes
    from the same file the desktop app writes.
    """

    def __init__(self, inner: Any, base_url: str) -> None:
        self._inner = inner
        self._base_url = base_url

    def get_api_base_url(self) -> str:
        return self._base_url

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


# ---------------------------------------------------------------------------
# CAMXORA session (reuses the app's stored login)
# ---------------------------------------------------------------------------


def _api(api_base: str = API_BASE, *, login: bool = False):
    from shared.services.platform_api import PlatformApi
    from shared.services.platform_client import PlatformClient
    from shared.services.secure_storage import SecureStorage
    from shared.services.session_service import SessionService

    store = SecureStorage()
    client = PlatformClient(storage=_FixedBaseStorage(store, api_base.rstrip("/")))
    api = PlatformApi(client)
    session = SessionService(storage=store, api=api)
    tokens = session.get_tokens()
    if tokens is None and not login:
        raise SystemExit(
            "No CAMXORA session found on this machine. Open the desktop app and sign in, "
            "or re-run with --login."
        )
    if login or tokens is None:
        import getpass

        from shared.models.auth import AuthTokens

        email = input("CAMXORA email: ").strip()
        password = getpass.getpass("Password: ")
        response = api.login(email, password)
        session.set_tokens(AuthTokens.from_token_response(response))
    else:
        try:
            session.ensure_fresh_session()
        except Exception:
            # An expired access token is fine as long as refresh works; surface
            # real failures when the first API call is made.
            pass
    return session.api


def _pick_profile(api, wanted: str | None) -> Any:
    profiles = api.list_profiles()
    if not profiles:
        raise SystemExit("This account has no channel profiles.")
    if wanted:
        needle = wanted.strip().lower()
        for profile in profiles:
            if needle in {str(profile.id).lower(), str(profile.name).lower()}:
                return profile
        raise SystemExit(f"No profile matched {wanted!r}.")
    if len(profiles) == 1:
        return profiles[0]
    print("Channel profiles:")
    for index, profile in enumerate(profiles, start=1):
        print(f"  {index}. {profile.name}  ({profile.id})")
    choice = input("Pick a profile number: ").strip()
    return profiles[int(choice) - 1]


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------


def _connection_for(api, profile_id: str) -> Any:
    for item in api.list_youtube_connections():
        if str(getattr(item, "profile_id", "")) == profile_id:
            return item
    return None


def connect(api, profile, *, timeout_seconds: int = 300) -> None:
    existing = _connection_for(api, str(profile.id))
    if existing is not None and str(existing.status).lower() in {"connected", "active"}:
        print(f"Already connected: {existing.channel_title or existing.channel_id}")
        return

    started = api.start_youtube_connection(str(profile.id))
    print("\nOpen this URL and choose the channel to publish to:\n")
    print(f"  {started.auth_url}\n")
    try:
        webbrowser.open(started.auth_url)
    except Exception:
        pass

    deadline = time.time() + timeout_seconds
    last_note = ""
    while time.time() < deadline:
        state = _connection_for(api, str(profile.id))
        if state is not None:
            status = str(state.status).lower()
            channels = list(getattr(state, "channels", []) or [])
            if status in {"pending_channel", "channel_selection"} and channels:
                if last_note != "select":
                    print("Several channels are available:")
                    for index, channel in enumerate(channels, start=1):
                        print(f"  {index}. {channel.title}  ({channel.id})")
                    last_note = "select"
                choice = input("Pick a channel number: ").strip()
                api.select_youtube_channel(str(state.session_id), channels[int(choice) - 1].id)
            elif status in {"connected", "active"}:
                print(f"Connected: {state.channel_title or state.channel_id}")
                return
            elif status in {"failed", "error"}:
                raise SystemExit(f"Google connect failed: {state.message or status}")
        time.sleep(3)
    raise SystemExit("Timed out waiting for the Google consent to finish.")


# ---------------------------------------------------------------------------
# Resumable upload
# ---------------------------------------------------------------------------


def start_session(token: str, *, title: str, description: str, tags: list[str], privacy: str) -> str:
    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "tags": tags[:30],
            "categoryId": CATEGORY_MUSIC,
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
        },
    }
    response = requests.post(
        UPLOAD_ENDPOINT,
        params={"uploadType": "resumable", "part": "snippet,status"},
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Type": "video/*",
        },
        data=json.dumps(body),
        timeout=60,
    )
    if response.status_code >= 400:
        raise SystemExit(f"YouTube refused the upload session: {response.status_code} {response.text[:400]}")
    session_url = response.headers.get("Location", "")
    if not session_url:
        raise SystemExit("YouTube did not return a resumable session URL.")
    return session_url


def upload(session_url: str, path: Path, *, chunk_mb: int = 16) -> dict[str, Any]:
    size = path.stat().st_size
    chunk = max(256 * 1024, chunk_mb * 1024 * 1024)

    offset = 0
    probe = requests.put(
        session_url,
        headers={"Content-Range": f"bytes */{size}"},
        timeout=60,
    )
    if probe.status_code in (200, 201):
        return probe.json()
    if probe.status_code == 308:
        received = probe.headers.get("Range", "")
        if "-" in received:
            offset = int(received.rsplit("-", 1)[1]) + 1
    print(f"Uploading {size / 1073741824:.2f} GB in {chunk // 1048576} MB chunks…")

    started = time.time()
    last_print = 0.0
    with path.open("rb") as handle:
        while offset < size:
            handle.seek(offset)
            payload = handle.read(chunk)
            headers = {
                "Content-Range": f"bytes {offset}-{offset + len(payload) - 1}/{size}",
                "Content-Type": "video/*",
            }
            response = requests.put(session_url, data=payload, headers=headers, timeout=900)
            if response.status_code in (200, 201):
                return response.json()
            if response.status_code != 308:
                raise SystemExit(
                    f"Upload failed at byte {offset}: {response.status_code} {response.text[:400]}"
                )
            received = response.headers.get("Range", "")
            offset = int(received.rsplit("-", 1)[1]) + 1 if "-" in received else offset + len(payload)
            now = time.time()
            if now - last_print > 1:
                last_print = now
                speed = offset / max(now - started, 0.1) / 1048576
                print(
                    f"  {offset * 100 // size:3d}%  "
                    f"{offset / 1073741824:.2f}/{size / 1073741824:.2f} GB  "
                    f"{speed:.1f} MB/s",
                    end="\r",
                    flush=True,
                )
    raise SystemExit("Upload ended without a video id.")


def set_thumbnail(token: str, video_id: str, path: Path) -> str | None:
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    with path.open("rb") as handle:
        response = requests.post(
            THUMB_ENDPOINT,
            params={"videoId": video_id},
            headers={"Authorization": f"Bearer {token}"},
            files={"file": (path.name, handle, mime)},
            timeout=120,
        )
    if response.status_code >= 400:
        return f"thumbnail failed: {response.status_code}"
    return None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="Upload a merged video straight to YouTube.")
    parser.add_argument("--list-profiles", action="store_true")
    parser.add_argument("--connect", action="store_true", help="Connect the channel, then exit")
    parser.add_argument("--profile", default=None, help="Profile name or id")
    parser.add_argument("--video", default=None, help="Path to the merged MP4")
    parser.add_argument("--title", default=None)
    parser.add_argument("--description", default="")
    parser.add_argument("--tags", default="")
    parser.add_argument("--privacy", default="private", choices=["private", "unlisted", "public"])
    parser.add_argument("--thumbnail", default=None)
    parser.add_argument("--batch-id", default=None, help="Batch uuid (to update Progress)")
    parser.add_argument("--role", default="OK")
    parser.add_argument("--chunk-mb", type=int, default=16)
    parser.add_argument("--api", default=API_BASE, help="CAMXORA API base URL")
    parser.add_argument("--login", action="store_true", help="Sign in with email/password first")
    args = parser.parse_args()

    api = _api(args.api, login=args.login)

    if args.list_profiles:
        for profile in api.list_profiles():
            state = _connection_for(api, str(profile.id))
            status = getattr(state, "status", "not connected") if state else "not connected"
            print(f"{profile.id}  {profile.name}  ->  YouTube: {status}")
        return 0

    profile = _pick_profile(api, args.profile)

    if args.connect or not args.video:
        connect(api, profile)
        if not args.video:
            return 0

    token_data = api.issue_youtube_access_token(str(profile.id))
    access_token = str(token_data.get("access_token") or "")
    if not access_token:
        raise SystemExit("Could not obtain a YouTube access token for this profile.")
    print(f"Access token acquired for {token_data.get('channel_title') or profile.name}.")

    video = Path(args.video)
    if not video.is_file():
        raise SystemExit(f"Video not found: {video}")
    title = (args.title or video.stem)[:100]
    tags = [tag.strip() for tag in args.tags.split(",") if tag.strip()]

    session_url = start_session(
        access_token,
        title=title,
        description=args.description,
        tags=tags,
        privacy=args.privacy,
    )
    result = upload(session_url, video, chunk_mb=args.chunk_mb)
    video_id = str(result.get("id") or "")
    if not video_id:
        raise SystemExit("YouTube returned no video id.")
    url = f"https://www.youtube.com/watch?v={video_id}"
    print(f"\nPublished: {url}")

    if args.thumbnail:
        thumb = Path(args.thumbnail)
        if thumb.is_file():
            warning = set_thumbnail(access_token, video_id, thumb)
            if warning:
                print(warning)

    if args.batch_id:
        api.report_youtube_upload(
            batch_id=args.batch_id,
            profile_id=str(profile.id),
            role=args.role,
            video_id=video_id,
            video_url=url,
            title=title,
        )
        print("Recorded on the Progress row.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
