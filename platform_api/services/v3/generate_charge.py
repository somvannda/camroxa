"""Feature-flagged bridge: v1 generate ops → credits-only v3 charge.

Default is off. Admin setting ``credits_only_v3_charge`` overrides
``PLATFORM_CREDITS_ONLY_V3_CHARGE``. Unmapped ops keep the v1 path.
"""

from __future__ import annotations

from typing import Any

CREDITS_ONLY_V3_CHARGE_SETTING_KEY = "credits_only_v3_charge"

V1_TO_V3_OP: dict[str, str] = {
    "music": "music",
    "music_generation": "music",
    "batch_generation": "music",
    "lyric": "lyric",
    "lyrics": "lyric",
    "web_music_lyrics": "lyric",
    "title": "title",
    "album": "album",
    "style": "style",
    "web_music_style": "style",
    "image_generation": "image",
    "background_image": "image",
    "thumbnail_image": "image",
    "video": "video",
    "video_generation": "video",
    "video_export": "video",
    "video_manual": "video",
    "video_merge": "merge",
    "merge": "merge",
    "auto_merge": "merge",
}


def map_v1_op_to_v3(operation_type: str) -> str | None:
    key = str(operation_type or "").strip().lower()
    return V1_TO_V3_OP.get(key)


def parse_bool_flag(raw: Any) -> bool | None:
    if raw is None:
        return None
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        if raw in (0, 1):
            return bool(int(raw))
        return None
    text = str(raw).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return None


def env_v3_charge_enabled() -> bool:
    try:
        from platform_api.config import get_settings

        return bool(get_settings().credits_only_v3_charge)
    except Exception:
        return False


async def credits_only_v3_charge_enabled(settings_repo: Any | None = None) -> bool:
    if settings_repo is not None:
        getter = getattr(settings_repo, "get_system_setting", None)
        if getter is not None:
            try:
                parsed = parse_bool_flag(await getter(CREDITS_ONLY_V3_CHARGE_SETTING_KEY))
            except Exception:
                parsed = None
            if parsed is not None:
                return parsed
    return env_v3_charge_enabled()
