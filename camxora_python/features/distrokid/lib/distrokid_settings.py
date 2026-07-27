"""DistroKid form + upload settings (local JSON store)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

ArtistMode = Literal["single", "dual", "per_channel"]


def _coerce_channel_artists(raw: Any) -> dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, str] = {}
    for key, value in raw.items():
        profile_id = str(key or "").strip()
        artist = str(value or "").strip()
        if profile_id and artist:
            out[profile_id] = artist
    return out


@dataclass
class UploadFormConfig:
    """DistroKid questionnaire defaults (ported from AutoDistroKid)."""

    song_count: int = 15
    previously_released: bool = False
    artist_on_instagram: bool = False
    artist_on_facebook: bool = False
    social_media_pack: bool = False

    language: str = "English"
    primary_genre: str = "Electronic"
    subgenre: str = "House"
    secondary_genre: str = ""

    songwriter_first_name: str = ""
    songwriter_last_name: str = ""
    songwriter_role: str = "Music and Lyrics"

    explicit_lyrics: bool = False
    radio_edit: bool = False
    instrumental: bool = True
    ai_generated: bool = True
    preview_clip_preference: str = "Let streaming services decide"

    apple_music_performers: list[dict] = field(default_factory=list)
    producer_credits: list[dict] = field(default_factory=list)

    retry_count: int = 3
    element_timeout: int = 30
    delay_between_albums: int = 20
    max_albums_per_session: int = 50

    release_date_mode: str = "default"
    custom_release_date: str = ""


@dataclass
class DistroKidSettings:
    """Local DistroKid automation preferences."""

    artist_mode: ArtistMode = "per_channel"
    single_artist_name: str = ""
    primary_artist_name: str = ""
    secondary_artist_name: str = ""
    channel_artists: dict[str, str] = field(default_factory=dict)
    artist_name: str = ""
    auto_submit: bool = False
    keep_browser_open: bool = False
    delete_wav_after_upload: bool = False
    upload_form: UploadFormConfig = field(default_factory=UploadFormConfig)


def _default_settings_path() -> Path:
    from shared.lib.app_paths import get_user_data_dir

    return get_user_data_dir() / "distrokid" / "settings.json"


def _coerce_form(raw: dict[str, Any] | None) -> UploadFormConfig:
    data = raw if isinstance(raw, dict) else {}
    base = UploadFormConfig()
    for key in asdict(base):
        if key in data:
            setattr(base, key, data[key])
    return base


class DistroKidSettingsStore:
    """Read/write DistroKid settings under Camxora user data."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or _default_settings_path()

    def load(self) -> DistroKidSettings:
        if not self.path.is_file():
            return DistroKidSettings()
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return DistroKidSettings()
        if not isinstance(raw, dict):
            return DistroKidSettings()
        mode_raw = str(raw.get("artist_mode") or "").strip().lower()
        if mode_raw == "single":
            artist_mode: ArtistMode = "single"
        elif mode_raw == "dual":
            artist_mode = "dual"
        else:
            artist_mode = "per_channel"
        return DistroKidSettings(
            artist_mode=artist_mode,
            single_artist_name=str(raw.get("single_artist_name") or "").strip(),
            primary_artist_name=str(raw.get("primary_artist_name") or "").strip(),
            secondary_artist_name=str(raw.get("secondary_artist_name") or "").strip(),
            channel_artists=_coerce_channel_artists(raw.get("channel_artists")),
            artist_name=str(raw.get("artist_name") or "").strip(),
            auto_submit=bool(raw.get("auto_submit", False)),
            keep_browser_open=bool(raw.get("keep_browser_open", False)),
            delete_wav_after_upload=bool(raw.get("delete_wav_after_upload", False)),
            upload_form=_coerce_form(raw.get("upload_form") if isinstance(raw.get("upload_form"), dict) else {}),
        )

    def save(self, settings: DistroKidSettings) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "artist_mode": settings.artist_mode,
            "single_artist_name": settings.single_artist_name,
            "primary_artist_name": settings.primary_artist_name,
            "secondary_artist_name": settings.secondary_artist_name,
            "channel_artists": dict(settings.channel_artists),
            "artist_name": settings.artist_name,
            "auto_submit": settings.auto_submit,
            "keep_browser_open": settings.keep_browser_open,
            "delete_wav_after_upload": settings.delete_wav_after_upload,
            "upload_form": asdict(settings.upload_form),
        }
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
