"""Music workspace setup readiness — gates Generate and Auto-Upload."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from shared.lib.sample_pack_config import SERVER_MANAGED_SAMPLE_PACKS
from shared.lib.settings_workspace import build_system_settings_draft
from shared.models.auth import ProfileResponse
from shared.models.platform import YouTubeConnectionResponse
from shared.services.file_service import list_directory_image_paths

MUSIC_CATEGORY_IDS = {"10", "music"}

SECTION_ICON_BY_NAME = {
    "Profile": "user-round",
    "YouTube": "youtube",
    "Preferences": "settings",
}


@dataclass(frozen=True, slots=True)
class ReadinessItem:
    id: str
    label: str
    section: str
    complete: bool
    required_for_generate: bool = True
    required_for_upload: bool = False
    hint: str = ""


@dataclass(frozen=True, slots=True)
class MusicReadinessReport:
    items: list[ReadinessItem] = field(default_factory=list)

    @property
    def generate_ready(self) -> bool:
        return all(item.complete for item in self.items if item.required_for_generate)

    @property
    def upload_ready(self) -> bool:
        upload_items = [item for item in self.items if item.required_for_upload]
        return bool(upload_items) and all(item.complete for item in upload_items)

    def incomplete_generate_labels(self) -> list[str]:
        return [item.label for item in self.items if item.required_for_generate and not item.complete]

    def incomplete_upload_labels(self) -> list[str]:
        return [item.label for item in self.items if item.required_for_upload and not item.complete]


def _connection_for(
    profile_id: str,
    connections: list[YouTubeConnectionResponse],
) -> YouTubeConnectionResponse | None:
    for connection in connections:
        if connection.profile_id == profile_id:
            return connection
    return None


def _youtube_connected(profile_id: str, connections: list[YouTubeConnectionResponse]) -> bool:
    connection = _connection_for(profile_id, connections)
    return bool(connection and str(connection.status or "").strip().lower() == "connected")


def _publication_ready_for_upload(profile: ProfileResponse) -> bool:
    config = dict(profile.youtube_config or {})
    visibility = str(config.get("visibility") or "").strip()
    if not visibility:
        return False
    if bool(config.get("made_for_kids")):
        return False
    if not bool(config.get("ai_use")):
        return False
    category = str(config.get("category") or "").strip().lower()
    if category not in MUSIC_CATEGORY_IDS:
        return False
    if not str(config.get("title_template") or "").strip():
        return False
    if not str(config.get("description_template") or "").strip():
        return False
    return True


def _path_is_file(value: str) -> bool:
    text = str(value or "").strip()
    return bool(text) and Path(text).is_file()


def _path_is_dir(value: str) -> bool:
    text = str(value or "").strip()
    return bool(text) and Path(text).is_dir()


def evaluate_music_readiness(
    *,
    selected_profiles: list[ProfileResponse],
    settings: dict[str, Any],
    youtube_connections: list[YouTubeConnectionResponse],
    bg_sample_count: int = 0,
    th_sample_count: int = 0,
) -> MusicReadinessReport:
    """Build checklist items for the Music page."""
    draft = build_system_settings_draft(settings)
    items: list[ReadinessItem] = []

    for profile in selected_profiles:
        name = profile.name or "Channel"
        has_template = bool(str(profile.video_template_id or "").strip())
        items.append(
            ReadinessItem(
                id=f"profile:{profile.id}:video_template",
                label=f"Video template selected for {name}",
                section="Profile",
                complete=has_template,
                required_for_generate=True,
                hint="Settings → Profiles → pick a video template for this channel.",
            )
        )

    for profile in selected_profiles:
        name = profile.name or "Channel"
        connected = _youtube_connected(profile.id, youtube_connections)
        items.append(
            ReadinessItem(
                id=f"youtube:{profile.id}:connected",
                label=f"YouTube connected for {name}",
                section="YouTube",
                complete=connected,
                required_for_generate=False,
                required_for_upload=True,
                hint="Settings → YouTube → Connect Channel.",
            )
        )
        pub_ready = connected and _publication_ready_for_upload(profile)
        items.append(
            ReadinessItem(
                id=f"youtube:{profile.id}:publication",
                label=f"Publication defaults complete for {name}",
                section="YouTube",
                complete=pub_ready,
                required_for_generate=False,
                required_for_upload=True,
                hint=(
                    "Settings → Publication: visibility, not made for kids, AI use Yes, "
                    "Category Music, title + description templates."
                ),
            )
        )

    pref_checks: list[tuple[str, str, bool, str]] = [
        (
            "pref:ffmpeg",
            "FFmpeg is available",
            _path_is_file(draft.ffmpeg_path),
            "Camxora usually bundles FFmpeg automatically. If this is missing, open "
            "Settings → Preferences and browse to ffmpeg.exe, or reinstall Camxora.",
        ),
        (
            "pref:downloads",
            "Downloads folder is ready",
            _path_is_dir(draft.downloads_dir),
            "Settings → Preferences → Downloads dir. Camxora creates a default folder "
            "under LocalAppData; pick another path if you prefer.",
        ),
        (
            "pref:suno",
            "Suno output folder is ready",
            _path_is_dir(draft.suno_output_dir),
            "Settings → Preferences → Suno output dir. Default folder is created automatically.",
        ),
        (
            "pref:merged",
            "Merged videos folder is ready",
            _path_is_dir(draft.merged_dir),
            "Settings → Preferences → Merged dir. Default folder is created automatically.",
        ),
    ]
    if not SERVER_MANAGED_SAMPLE_PACKS:
        pref_checks.extend(
            (
                (
                    "pref:bg_dir",
                    "Background samples folder is ready",
                    _path_is_dir(draft.image_background_samples_dir),
                    "Settings → Preferences → BG samples dir. Default folder is created automatically.",
                ),
                (
                    "pref:th_dir",
                    "Thumbnail samples folder is ready",
                    _path_is_dir(draft.image_thumbnail_samples_dir),
                    "Settings → Preferences → Thumb samples dir. Default folder is created automatically.",
                ),
                (
                    "pref:bg_installed",
                    "Background sample pack installed",
                    bg_sample_count > 0,
                    "Settings → Preferences → install a background sample pack into the BG folder.",
                ),
                (
                    "pref:th_installed",
                    "Thumbnail sample pack installed",
                    th_sample_count > 0,
                    "Settings → Preferences → install a thumbnail sample pack into the Thumb folder.",
                ),
            )
        )
    for item_id, label, complete, hint in pref_checks:
        items.append(
            ReadinessItem(
                id=item_id,
                label=label,
                section="Preferences",
                complete=complete,
                required_for_generate=True,
                hint=hint,
            )
        )

    return MusicReadinessReport(items=items)


def build_music_readiness_report(
    *,
    profiles: list[ProfileResponse],
    settings: dict[str, Any],
    youtube_connections: list[YouTubeConnectionResponse],
) -> MusicReadinessReport:
    """Evaluate readiness for the given channel profiles and workspace settings."""
    draft = build_system_settings_draft(settings)
    bg_count = len(list_directory_image_paths(draft.image_background_samples_dir))
    th_count = len(list_directory_image_paths(draft.image_thumbnail_samples_dir))
    return evaluate_music_readiness(
        selected_profiles=profiles,
        settings=settings,
        youtube_connections=youtube_connections,
        bg_sample_count=bg_count,
        th_sample_count=th_count,
    )
