"""Operation names and plan/pricing lookup keys for credits-only v3."""

from __future__ import annotations

PLAN_OP_COLUMNS: dict[str, str] = {
    "lyric": "lyric_credits",
    "title": "title_credits",
    "album": "album_credits",
    "music": "music_credits",
    "style": "style_credits",
    "image": "image_credits",
    "video": "video_credits",
    "merge": "merge_credits",
}

# Studio operations are priced directly from `credit_pricing`; they do not
# map to a plan column.
STUDIO_OPS = ("studio_edit", "studio_stems_2", "studio_stems_12")
SUPPORTED_OPS = (*PLAN_OP_COLUMNS.keys(), *STUDIO_OPS)

# Credits page (credit_pricing) fallbacks. First hit wins.
PRICING_FALLBACKS: dict[str, tuple[tuple[str, str], ...]] = {
    "lyric": (("openai", "lyric"), ("deepseek", "lyric"), ("suno", "lyric")),
    "title": (("openai", "title"), ("deepseek", "title")),
    "album": (("openai", "album"), ("deepseek", "album")),
    "music": (("suno", "music"), ("suno", "music_generation")),
    "style": (("suno", "web_music_style"), ("suno", "style")),
    "image": (("fal", "background_image"), ("openai", "background_image")),
    "video": (("local", "video"), ("local", "video_manual")),
    "merge": (("local", "video_merge"), ("local", "merge")),
    "studio_edit": (("suno", "studio_edit"),),
    "studio_stems_2": (("suno", "studio_stems_2"),),
    "studio_stems_12": (("suno", "studio_stems_12"),),
}

PATCHABLE_PLAN_FIELDS = frozenset(
    {
        "monthly_credits",
        "daily_credits",
        "is_public",
        "is_active",
        "pricing_features",
        "pricing_credit_lines",
        *PLAN_OP_COLUMNS.values(),
    }
)
