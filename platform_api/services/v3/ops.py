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
# Entries are (ai_service, operation_type, sub_model); None means the
# provider-wide default row. Routed providers are tried before this chain.
PRICING_FALLBACKS: dict[str, tuple[tuple[str, str, str | None], ...]] = {
    "lyric": (("openai", "lyric", None), ("deepseek", "lyric", None), ("suno", "lyric", None)),
    "title": (("openai", "title", None), ("deepseek", "title", None)),
    "album": (("openai", "album", None), ("deepseek", "album", None)),
    "music": (("suno", "music", None), ("suno", "music_generation", None)),
    "style": (("suno", "web_music_style", None), ("suno", "style", None)),
    "image": (("fal", "background_image", None), ("openai", "background_image", None)),
    "video": (("local", "video", None), ("local", "video_manual", None)),
    "merge": (("local", "video_merge", None), ("local", "merge", None)),
    "studio_edit": (("suno", "studio_edit", None),),
    "studio_stems_2": (("suno", "studio_stems_2", None),),
    "studio_stems_12": (("suno", "studio_stems_12", None),),
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
