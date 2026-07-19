"""Music workspace settings — port of MusicWorkspacePage settings helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

LANGUAGE_OPTIONS = (
    ("en", "English"),
    ("km", "Khmer"),
    ("de", "German"),
    ("es", "Spanish"),
    ("fr", "French"),
)

DEFAULT_LANGUAGE_OPTIONS = LANGUAGE_OPTIONS


@dataclass
class MusicSettingsState:
    language: str = "en"
    secondary_language: str = ""
    default_description_id: str = ""
    default_structure_id: str = ""
    creativity: int = 55
    unique_opening: bool = False
    shuffle_structure: bool = False
    use_content_pools: bool = False
    strict_level: int = 3
    history_window: int = 100
    song_count: int = 4
    auto_gen_image: bool = False
    auto_gsuno: bool = False
    auto_video_after_suno: bool = False
    auto_merge_after_video: bool = False
    auto_reel_after_video: bool = False
    auto_upload_youtube: bool = False
    polish_strength: int = 85


def _clamp(value: int, minimum: int, maximum: int) -> int:
    return min(maximum, max(minimum, value))


def read_boolean_setting(settings: dict[str, Any] | None, key: str, fallback: bool) -> bool:
    value = (settings or {}).get(key)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized == "true":
            return True
        if normalized == "false":
            return False
    return fallback


def read_number_setting(settings: dict[str, Any] | None, key: str, fallback: int) -> int:
    value = (settings or {}).get(key)
    if isinstance(value, (int, float)) and float(value) == float(value):
        return int(value)
    if isinstance(value, str):
        try:
            return int(float(value))
        except ValueError:
            return fallback
    return fallback


def read_string_setting(settings: dict[str, Any] | None, key: str, fallback: str = "") -> str:
    value = (settings or {}).get(key)
    if value is None:
        return fallback
    text = str(value).strip()
    return text if text else fallback


def normalize_language_setting(
    value: object,
    *,
    options: tuple[tuple[str, str], ...] | None = None,
) -> str:
    available = options or DEFAULT_LANGUAGE_OPTIONS
    if not isinstance(value, str):
        return available[0][0]
    normalized = value.strip().lower()
    for code, label in available:
        if code == normalized or label.lower() == normalized:
            return code
    return available[0][0]


def _read_language_field(item: object, field: str) -> str:
    if isinstance(item, dict):
        return str(item.get(field) or "").strip()
    return str(getattr(item, field, "") or "").strip()


def language_options_from_response(items: list[object]) -> list[tuple[str, str]]:
    options: list[tuple[str, str]] = []
    for item in items:
        code = _read_language_field(item, "code")
        label = _read_language_field(item, "label")
        if code and label:
            options.append((code, label))
    return options or list(DEFAULT_LANGUAGE_OPTIONS)


def blank_music_settings_state() -> MusicSettingsState:
    return MusicSettingsState()


def build_music_settings_state(
    settings: dict[str, Any] | None,
    *,
    language_options: tuple[tuple[str, str], ...] | None = None,
) -> MusicSettingsState:
    defaults = blank_music_settings_state()
    return MusicSettingsState(
        language=normalize_language_setting(
            (settings or {}).get("language"),
            options=language_options,
        ),
        secondary_language=str((settings or {}).get("secondaryLanguage") or "").strip().lower(),
        default_description_id=read_string_setting(settings, "defaultDescriptionId"),
        default_structure_id=read_string_setting(settings, "defaultStructureId"),
        creativity=_clamp(read_number_setting(settings, "creativity", defaults.creativity), 0, 100),
        unique_opening=read_boolean_setting(settings, "uniqueOpening", defaults.unique_opening),
        shuffle_structure=read_boolean_setting(settings, "shuffleStructure", defaults.shuffle_structure),
        use_content_pools=read_boolean_setting(settings, "useContentPools", defaults.use_content_pools),
        strict_level=_clamp(read_number_setting(settings, "strictLevel", defaults.strict_level), 1, 5),
        history_window=_clamp(
            read_number_setting(settings, "uniquenessHistoryWindow", defaults.history_window),
            50,
            1500,
        ),
        song_count=_clamp(read_number_setting(settings, "defaultSongCount", defaults.song_count), 1, 50),
        auto_gen_image=read_boolean_setting(settings, "autoGenImage", defaults.auto_gen_image),
        auto_gsuno=read_boolean_setting(settings, "autoGSuno", defaults.auto_gsuno),
        auto_video_after_suno=read_boolean_setting(settings, "autoVideoAfterSuno", defaults.auto_video_after_suno),
        auto_merge_after_video=read_boolean_setting(settings, "autoMergeAfterVideo", defaults.auto_merge_after_video),
        auto_reel_after_video=read_boolean_setting(settings, "autoReelAfterVideo", defaults.auto_reel_after_video),
        auto_upload_youtube=read_boolean_setting(settings, "autoUploadYouTube", defaults.auto_upload_youtube),
        polish_strength=_clamp(
            read_number_setting(settings, "lyricsPolishStrength", defaults.polish_strength),
            0,
            100,
        ),
    )


def build_music_prompt_defaults_patch(
    *,
    default_description_id: str,
    default_structure_id: str,
) -> dict[str, object]:
    return {
        "defaultDescriptionId": default_description_id.strip(),
        "defaultStructureId": default_structure_id.strip(),
    }


def build_music_settings_patch(settings: MusicSettingsState) -> dict[str, object]:
    return {
        "language": settings.language,
        "secondaryLanguage": settings.secondary_language,
        "creativity": settings.creativity,
        "uniqueOpening": settings.unique_opening,
        "shuffleStructure": settings.shuffle_structure,
        "useContentPools": settings.use_content_pools,
        "strictLevel": settings.strict_level,
        "uniquenessHistoryWindow": settings.history_window,
        "defaultSongCount": settings.song_count,
        "autoGenImage": settings.auto_gen_image,
        "autoGSuno": settings.auto_gsuno,
        "autoVideoAfterSuno": settings.auto_video_after_suno,
        "autoMergeAfterVideo": settings.auto_merge_after_video,
        "autoReelAfterVideo": settings.auto_reel_after_video,
        "autoUploadYouTube": settings.auto_upload_youtube,
        "lyricsPolishStrength": settings.polish_strength,
    }


def settings_snapshot(settings: MusicSettingsState) -> str:
    import json

    return json.dumps(build_music_settings_patch(settings), sort_keys=True)


def save_status_message(status: str) -> str:
    if status == "saving":
        return "Saving music defaults..."
    if status == "saved":
        return "Music defaults saved."
    if status == "error":
        return "Unable to save music defaults."
    return "Music defaults are ready."
