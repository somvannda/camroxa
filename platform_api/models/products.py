"""Account product tags: studio (desktop/user portal) vs music_web."""

from __future__ import annotations

from platform_api.exceptions import ValidationError

PRODUCT_STUDIO = "studio"
PRODUCT_MUSIC_WEB = "music_web"
VALID_PRODUCTS = frozenset({PRODUCT_STUDIO, PRODUCT_MUSIC_WEB})

SUNO_TASK_SOURCE_STUDIO = "studio"
SUNO_TASK_SOURCE_WEB_MUSIC = "web_music"

WEB_MUSIC_FREE_DAILY_LIMIT_KEY = "web_music_free_daily_limit"
WEB_MUSIC_FREE_DAILY_LIMIT_DEFAULT = 5

WEB_MUSIC_FREE_DAILY_CREDITS_KEY = "web_music_free_daily_credits"
WEB_MUSIC_FREE_DAILY_CREDITS_DEFAULT = 50

# Free music-web allowance reset cadence ("daily" | "monthly").
# "monthly" = free pool refills once per calendar month (Phnom_Penh midnight).
MUSIC_WEB_FREE_RESET_PERIOD_KEY = "music_web_free_reset_period"
MUSIC_WEB_FREE_RESET_PERIOD_DEFAULT = "daily"

WEB_MUSIC_CREDITS_PER_SONG = 10


def normalize_signup_product(value: str | None) -> str:
    """Return music_web or studio. Empty/unknown-empty defaults to studio."""
    raw = str(value or "").strip().lower().replace("-", "_")
    if raw in ("", "studio", "desktop", "app", "user"):
        return PRODUCT_STUDIO
    if raw in ("music_web", "musicweb", "music"):
        return PRODUCT_MUSIC_WEB
    raise ValidationError(
        "product must be music_web or studio.",
        details={"field": "product", "product": raw[:64]},
    )
