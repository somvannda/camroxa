"""Settings workspace helpers — port of SettingsWorkspacePage.tsx logic."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from shared.lib.music_settings import read_boolean_setting, read_number_setting, read_string_setting
from shared.models.auth import ProfileResponse


def clamp(value: int, minimum: int, maximum: int) -> int:
    return min(maximum, max(minimum, value))


def read_string_array_setting(settings: dict[str, Any] | None, key: str) -> list[str]:
    value = (settings or {}).get(key)
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if isinstance(item, str) and str(item).strip()]


def normalize_path(value: str) -> str:
    return value.strip()


def normalize_profile_image_mode(value: object) -> str:
    mode = str(value or "").strip().lower()
    if mode in {"bg_only", "thumb_only"}:
        return mode
    return "bg_thumb"


def normalize_image_source_mode(value: object) -> str:
    mode = str(value or "").strip().lower()
    return "manual" if mode == "manual" else "ai"


def normalize_kind_source_mode(value: object) -> str:
    """BG/TH reference mode: prompt_only | category.

    ``personal_reference`` / User reference is hidden until P2; coerce to category.
    """
    mode = str(value or "").strip().lower()
    if mode in {"prompt", "prompt_only"}:
        return "prompt_only"
    # personal_reference was a 1.1.1 placeholder — map away so UI never sticks on it.
    if mode in {"personal", "personal_reference", "user_reference"}:
        return "category"
    return "category"


def resolve_kind_source_modes(settings: dict[str, Any] | None) -> tuple[str, str]:
    """Resolve BG/TH source modes with legacy ``backgroundSourceMode`` migration."""
    data = settings if isinstance(settings, dict) else {}
    legacy = str(data.get("backgroundSourceMode") or "").strip().lower()
    bg_raw = str(data.get("imageBackgroundSourceMode") or "").strip()
    th_raw = str(data.get("imageThumbnailSourceMode") or "").strip()
    if bg_raw:
        bg = normalize_kind_source_mode(bg_raw)
    elif legacy in {"prompt", "prompt_only"}:
        bg = "prompt_only"
    else:
        bg = "category"
    if th_raw:
        th = normalize_kind_source_mode(th_raw)
    else:
        th = "category"
    return bg, th


def slugify_profile_folder_name(name: str) -> str:
    """Derive a stable profile output folder from the display name."""
    folder_name = str(name or "").strip().lower().replace(" ", "-").replace("/", "-")
    folder_name = "".join(character for character in folder_name if character.isalnum() or character == "-")
    while "--" in folder_name:
        folder_name = folder_name.replace("--", "-")
    folder_name = folder_name.strip("-")
    return (folder_name[:50] if folder_name else "profile")


def resolve_profile_folder_name(name: str, folder_name: str | None = None) -> str:
    cleaned = str(folder_name or "").strip()
    if cleaned:
        return cleaned[:50]
    return slugify_profile_folder_name(name)


def get_profile_search_haystack(profile: ProfileResponse) -> str:
    return " ".join(
        part for part in (profile.name, profile.folder_name or "", profile.run_prefix or "") if part
    ).strip().lower()


def get_profile_initials(name: str) -> str:
    parts = [part for part in name.split(" ") if part]
    initials = "".join(part[0].upper() for part in parts[:2] if part)
    return initials or "P"


def get_youtube_status_label(status: str) -> str:
    mapping = {
        "connected": "Connected",
        "pending_browser": "Waiting for browser sign-in",
        "awaiting_channel_selection": "Choose a channel",
        "error": "Connection issue",
        "not_connected": "Not connected",
    }
    return mapping.get(status, "Not connected")


def get_youtube_connect_button_label(status: str) -> str:
    mapping = {
        "pending_browser": "Restart Sign-In",
        "connected": "Reconnect Channel",
        "error": "Try Again",
        "awaiting_channel_selection": "Start Again",
    }
    return mapping.get(status, "Connect Channel")


def get_youtube_connect_hint(status: str) -> str:
    if status == "pending_browser":
        return (
            "Finish Google sign-in in your browser. If the browser flow was closed or cancelled, "
            "use Restart Sign-In to begin a fresh connection."
        )
    if status == "awaiting_channel_selection":
        return "Google returned more than one channel. Choose which one should be connected to this profile."
    if status == "error":
        return "The previous YouTube connection attempt failed. Use Try Again to start a fresh sign-in flow."
    return "Connect once here, then keep publication defaults per profile in the Publication tab."


@dataclass
class ProfileDraft:
    name: str = ""
    folder_name: str = ""
    run_prefix: str = ""
    logo_path: str = ""
    logo_base64: str | None = None
    cover_path: str = ""
    cover_base64: str | None = None
    video_template_id: str = ""
    reel_template_id: str = ""
    output_resolution: str = "1920x1080"
    image_mode: str = "bg_thumb"


@dataclass
class PublicationDraft:
    description: str = ""
    keywords: str = ""
    visibility: str = "unlisted"
    publish_date: str = ""
    publish_hour: str = "00"
    publish_minute: str = "00"
    made_for_kids: bool = False
    ai_use: bool = False
    category: str = "10"
    playlist: str = ""
    tags: str = ""
    title_template: str = ""
    description_template: str = ""


@dataclass
class SystemSettingsDraft:
    ffmpeg_path: str = ""
    downloads_dir: str = ""
    suno_output_dir: str = ""
    merged_dir: str = ""
    perf_music_workers: int = 1
    perf_image_workers: int = 4
    perf_export_workers: int = 1
    perf_merge_workers: int = 1
    perf_youtube_workers: int = 1
    youtube_upload_chunk_size_mb: int = 256
    image_background_samples_dir: str = ""
    image_thumbnail_samples_dir: str = ""
    image_bg_random: bool = False
    image_thumb_random: bool = False
    image_bg_samples: list[str] = field(default_factory=list)
    image_thumb_samples: list[str] = field(default_factory=list)
    image_output_dir: str = ""
    output_resolution: str = "1920x1080"
    style_strength: int = 80
    image_source_mode: str = "ai"
    image_background_source_mode: str = "category"
    image_thumbnail_source_mode: str = "category"
    thumbnail_overlay_mode: str = "ai"


SUNO_VERSION_OPTIONS = ("v5", "v5.5")


@dataclass
class SunoSettingsDraft:
    suno_callback_url: str = ""
    suno_timeout_ms: int = 90000
    suno_retry_count: int = 3
    suno_default_version: str = "v5.5"
    suno_merge_enabled: bool = False
    suno_merge_group_size: int = 0
    suno_credits_reserve: int = 10
    suno_credits_cost_music: int = 5
    suno_credits_cost_lyrics: int = 1


def split_publish_at(value: object) -> tuple[str, str, str]:
    text = str(value or "").strip()
    match = re.match(r"^(?:(\d{4}-\d{2}-\d{2})[T ])?(\d{1,2}):(\d{2})", text)
    if not match:
        return "", "00", "00"
    hour = str(clamp(int(match.group(2)), 0, 23)).zfill(2)
    minute = str((clamp(int(match.group(3)), 0, 59) // 5) * 5).zfill(2)
    return match.group(1) or "", hour, minute


def build_profile_draft(profile: ProfileResponse | None) -> ProfileDraft:
    if profile is None:
        return ProfileDraft()
    image_config = profile.image_config or {}
    cover_paths = image_config.get("cover_paths")
    cover_path = ""
    if isinstance(cover_paths, list) and cover_paths:
        first = cover_paths[0]
        if isinstance(first, str):
            cover_path = first
    return ProfileDraft(
        name=profile.name or "",
        folder_name=profile.folder_name or "",
        run_prefix=profile.run_prefix or "",
        logo_path=getattr(profile, "logo_path", None) or "",
        cover_path=cover_path,
        video_template_id=getattr(profile, "video_template_id", None) or "",
        reel_template_id=getattr(profile, "reel_template_id", None) or "",
        output_resolution=profile.output_resolution or "1920x1080",
        image_mode=normalize_profile_image_mode(image_config.get("mode")),
    )


def build_publication_draft(profile: ProfileResponse | None) -> PublicationDraft:
    youtube_config = profile.youtube_config if profile and profile.youtube_config else {}
    keywords = youtube_config.get("keywords")
    if isinstance(keywords, list):
        keyword_text = ", ".join(str(item) for item in keywords if isinstance(item, str))
    else:
        keyword_text = str(keywords or "")
    tags = youtube_config.get("tags")
    if isinstance(tags, list):
        tag_text = ", ".join(str(item) for item in tags if isinstance(item, str))
    else:
        tag_text = str(tags or "")
    publish_date, publish_hour, publish_minute = split_publish_at(youtube_config.get("publish_at"))
    return PublicationDraft(
        description=str(youtube_config.get("description") or ""),
        keywords=keyword_text,
        visibility=str(youtube_config.get("visibility") or "unlisted"),
        publish_date=publish_date,
        publish_hour=publish_hour,
        publish_minute=publish_minute,
        made_for_kids=bool(youtube_config.get("made_for_kids") or False),
        ai_use=bool(youtube_config.get("ai_use") or False),
        category=str(youtube_config.get("category") or "10"),
        playlist=str(youtube_config.get("playlist") or ""),
        tags=tag_text,
        title_template=str(youtube_config.get("title_template") or ""),
        description_template=str(youtube_config.get("description_template") or ""),
    )


def build_system_settings_draft(settings: dict[str, Any]) -> SystemSettingsDraft:
    from shared.lib.workspace_defaults import apply_workspace_path_defaults

    normalized, _patch = apply_workspace_path_defaults(settings)
    return SystemSettingsDraft(
        ffmpeg_path=read_string_setting(normalized, "ffmpegPath"),
        downloads_dir=read_string_setting(normalized, "downloadsDir"),
        suno_output_dir=read_string_setting(normalized, "sunoOutputDir"),
        merged_dir=read_string_setting(normalized, "mergedDir"),
        perf_music_workers=clamp(read_number_setting(normalized, "perfMusicWorkers", 1), 1, 5),
        perf_image_workers=clamp(read_number_setting(normalized, "perfImageWorkers", 4), 1, 8),
        perf_export_workers=clamp(
            read_number_setting(
                normalized,
                "videoExportWorkers",
                read_number_setting(normalized, "perfExportWorkers", 1),
            ),
            1,
            10,
        ),
        perf_merge_workers=clamp(read_number_setting(normalized, "perfMergeWorkers", 1), 1, 2),
        perf_youtube_workers=clamp(read_number_setting(normalized, "perfYouTubeWorkers", 1), 1, 5),
        youtube_upload_chunk_size_mb=clamp(
            read_number_setting(normalized, "youtubeUploadChunkSizeMb", 256),
            8,
            512,
        ),
        image_background_samples_dir=read_string_setting(normalized, "imageBackgroundSamplesDir"),
        image_thumbnail_samples_dir=read_string_setting(normalized, "imageThumbnailSamplesDir"),
        image_bg_random=read_boolean_setting(normalized, "imageBgRandom", False),
        image_thumb_random=read_boolean_setting(normalized, "imageThumbRandom", False),
        image_bg_samples=read_string_array_setting(normalized, "imageBgSamples")[:5],
        image_thumb_samples=read_string_array_setting(normalized, "imageThumbSamples")[:5],
        image_output_dir=read_string_setting(normalized, "imageOutputDir"),
        output_resolution=read_string_setting(normalized, "outputResolution")
        or read_string_setting(normalized, "imageResolution", "1920x1080"),
        style_strength=clamp(read_number_setting(normalized, "styleStrength", 80), 0, 100),
        image_source_mode=normalize_image_source_mode(normalized.get("imageSourceMode")),
        image_background_source_mode=resolve_kind_source_modes(normalized)[0],
        image_thumbnail_source_mode=resolve_kind_source_modes(normalized)[1],
        thumbnail_overlay_mode=read_string_setting(normalized, "thumbnailOverlayMode", "ai") or "ai",
    )


def build_suno_settings_draft(settings: dict[str, Any]) -> SunoSettingsDraft:
    return SunoSettingsDraft(
        suno_callback_url=read_string_setting(settings, "sunoCallbackUrl"),
        suno_timeout_ms=max(1000, read_number_setting(settings, "sunoTimeoutMs", 90000)),
        suno_retry_count=max(0, read_number_setting(settings, "sunoRetryCount", 3)),
        suno_default_version=read_string_setting(settings, "sunoDefaultVersion", "v5.5") or "v5.5",
        suno_merge_enabled=read_boolean_setting(settings, "sunoMergeEnabled", False),
        suno_merge_group_size=max(0, read_number_setting(settings, "sunoMergeGroupSize", 0)),
        suno_credits_reserve=max(0, read_number_setting(settings, "sunoCreditsReserve", 10)),
        suno_credits_cost_music=max(0, read_number_setting(settings, "sunoCreditsCostMusic", 5)),
        suno_credits_cost_lyrics=max(0, read_number_setting(settings, "sunoCreditsCostLyrics", 1)),
    )


def _is_local_filesystem_path(value: str) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    # Windows drive path or UNC / POSIX absolute path — not a server uploads/ key.
    if len(text) >= 2 and text[1] == ":":
        return True
    return text.startswith("\\\\") or text.startswith("/")


def build_profile_payload(draft: ProfileDraft, profile: ProfileResponse | None) -> dict[str, object]:
    base_image_config = dict(profile.image_config or {}) if profile else {}
    base_image_config["mode"] = normalize_profile_image_mode(draft.image_mode)
    # Keep existing server cover_paths unless the user uploaded a new cover (base64)
    # or explicitly set a non-local cover path. Never push a Windows browse path.
    if draft.cover_base64:
        pass
    elif draft.cover_path.strip() and not _is_local_filesystem_path(draft.cover_path):
        base_image_config["cover_paths"] = [draft.cover_path.strip()]
    payload: dict[str, object] = {
        "name": draft.name.strip(),
        "folder_name": resolve_profile_folder_name(draft.name, draft.folder_name),
        "run_prefix": draft.run_prefix.strip() or None,
        "video_template_id": draft.video_template_id.strip() or None,
        "reel_template_id": draft.reel_template_id.strip() or None,
        "output_resolution": draft.output_resolution or "1920x1080",
        "image_config": base_image_config,
    }
    # Prefer base64 uploads. Only send logo_path when it looks like a server key.
    if draft.logo_base64:
        payload["logo_base64"] = draft.logo_base64
    elif draft.logo_path.strip() and not _is_local_filesystem_path(draft.logo_path):
        payload["logo_path"] = draft.logo_path.strip()
    if draft.cover_base64:
        payload["cover_images"] = [draft.cover_base64]
    return payload


def build_publication_payload(draft: PublicationDraft, base_config: dict[str, object]) -> dict[str, object]:
    publish_at = f"{draft.publish_hour}:{draft.publish_minute}" if draft.visibility == "scheduled" else None
    return {
        **base_config,
        "description": draft.description.strip(),
        "keywords": [part.strip() for part in draft.keywords.split(",") if part.strip()],
        "visibility": draft.visibility,
        "publish_at": publish_at,
        "made_for_kids": draft.made_for_kids,
        "ai_use": draft.ai_use,
        "category": draft.category.strip(),
        "playlist": draft.playlist.strip(),
        "tags": [part.strip() for part in draft.tags.split(",") if part.strip()],
        "title_template": draft.title_template.strip(),
        "description_template": draft.description_template.strip(),
    }


def device_paths_dict_from_draft(draft: SystemSettingsDraft) -> dict[str, str]:
    """Media roots to write into the per-device local store (never account settings)."""
    return {
        "downloadsDir": normalize_path(draft.downloads_dir),
        "sunoOutputDir": normalize_path(draft.suno_output_dir),
        "mergedDir": normalize_path(draft.merged_dir),
        "imageBackgroundSamplesDir": normalize_path(draft.image_background_samples_dir),
        "imageThumbnailSamplesDir": normalize_path(draft.image_thumbnail_samples_dir),
        "imageOutputDir": normalize_path(draft.image_output_dir),
    }


def device_media_paths_dirty(draft: SystemSettingsDraft, current_settings: dict[str, Any]) -> bool:
    """True when Preferences media roots differ from the overlaid current settings."""
    current = build_system_settings_draft(current_settings)
    return device_paths_dict_from_draft(draft) != device_paths_dict_from_draft(current)


def build_system_settings_patch(
    draft: SystemSettingsDraft,
    current_settings: dict[str, Any],
    *,
    exclude_sample_pack_settings: bool = False,
) -> dict[str, object]:
    current = build_system_settings_draft(current_settings)
    patch: dict[str, object] = {}

    def assign_string(key: str, draft_value: str, current_value: str, patch_key: str | None = None) -> None:
        next_value = normalize_path(draft_value)
        existing = normalize_path(current_value)
        if next_value != existing:
            patch[patch_key or key] = next_value

    # Absolute media folder roots stay on this machine only (device-workspace-paths.json).
    # Pushing them into account settings caused cross-PC thrash and Preferences-save wipes.
    assign_string("ffmpegPath", draft.ffmpeg_path, current.ffmpeg_path)
    assign_string("imageSourceMode", draft.image_source_mode, current.image_source_mode)
    assign_string(
        "imageBackgroundSourceMode",
        draft.image_background_source_mode,
        current.image_background_source_mode,
    )
    assign_string(
        "imageThumbnailSourceMode",
        draft.image_thumbnail_source_mode,
        current.image_thumbnail_source_mode,
    )
    assign_string("thumbnailOverlayMode", draft.thumbnail_overlay_mode, current.thumbnail_overlay_mode)

    number_fields = (
        ("perfMusicWorkers", draft.perf_music_workers, current.perf_music_workers),
        ("perfImageWorkers", draft.perf_image_workers, current.perf_image_workers),
        ("perfMergeWorkers", draft.perf_merge_workers, current.perf_merge_workers),
        ("perfYouTubeWorkers", draft.perf_youtube_workers, current.perf_youtube_workers),
        ("youtubeUploadChunkSizeMb", draft.youtube_upload_chunk_size_mb, current.youtube_upload_chunk_size_mb),
        ("styleStrength", draft.style_strength, current.style_strength),
    )
    for key, next_value, current_value in number_fields:
        if next_value != current_value:
            patch[key] = next_value

    if not exclude_sample_pack_settings:
        if draft.image_bg_random != current.image_bg_random:
            patch["imageBgRandom"] = draft.image_bg_random
        if draft.image_thumb_random != current.image_thumb_random:
            patch["imageThumbRandom"] = draft.image_thumb_random
        if draft.image_bg_samples != current.image_bg_samples:
            patch["imageBgSamples"] = draft.image_bg_samples
        if draft.image_thumb_samples != current.image_thumb_samples:
            patch["imageThumbSamples"] = draft.image_thumb_samples
    if draft.output_resolution != current.output_resolution:
        patch["outputResolution"] = draft.output_resolution
        patch["imageResolution"] = draft.output_resolution
    if draft.perf_export_workers != current.perf_export_workers:
        patch["perfExportWorkers"] = draft.perf_export_workers
        patch["videoExportWorkers"] = draft.perf_export_workers
    return patch


def build_suno_settings_patch(draft: SunoSettingsDraft, current_settings: dict[str, Any]) -> dict[str, object]:
    current = build_suno_settings_draft(current_settings)
    patch: dict[str, object] = {}
    if draft.suno_callback_url.strip() != current.suno_callback_url.strip():
        patch["sunoCallbackUrl"] = draft.suno_callback_url.strip()
    for key, next_value, current_value in (
        ("sunoTimeoutMs", draft.suno_timeout_ms, current.suno_timeout_ms),
        ("sunoRetryCount", draft.suno_retry_count, current.suno_retry_count),
        ("sunoDefaultVersion", draft.suno_default_version, current.suno_default_version),
        ("sunoMergeEnabled", draft.suno_merge_enabled, current.suno_merge_enabled),
        ("sunoMergeGroupSize", draft.suno_merge_group_size, current.suno_merge_group_size),
        ("sunoCreditsReserve", draft.suno_credits_reserve, current.suno_credits_reserve),
        ("sunoCreditsCostMusic", draft.suno_credits_cost_music, current.suno_credits_cost_music),
        ("sunoCreditsCostLyrics", draft.suno_credits_cost_lyrics, current.suno_credits_cost_lyrics),
    ):
        if next_value != current_value:
            patch[key] = next_value
    return patch


def profile_payload_equal(left: dict[str, object], right: dict[str, object]) -> bool:
    return left == right


def publication_draft_equal(left: PublicationDraft, right: PublicationDraft) -> bool:
    return left == right


def toggle_library_sample(samples: list[str], path: str, *, limit: int = 5) -> list[str]:
    if path in samples:
        return [item for item in samples if item != path]
    if len(samples) >= limit:
        return samples
    return [*samples, path]
