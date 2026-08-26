"""Public pricing display helpers.

Song hints use the Credits-page music list price (fallback 10).
One generate returns two song versions.
"""

from __future__ import annotations

from typing import Any

DEFAULT_CREDITS_PER_GENERATE = 10
CREDITS_PER_GENERATE = DEFAULT_CREDITS_PER_GENERATE
SONGS_PER_GENERATE = 2
MAX_PRICING_FEATURE_LINES = 20
MAX_PRICING_FEATURE_LINE_LENGTH = 80

DEFAULT_FREE_PRICING_FEATURES = (
    "Web Create",
    "Daily credit reset",
    "Top-up packs",
)
DEFAULT_PAID_PRICING_FEATURES = (
    "Web Create",
    "Desktop studio",
    "Dual channels",
    "Top-up packs",
)


def normalize_credits_per_generate(value: int | float | None) -> int | float:
    try:
        parsed = float(value) if value is not None else float(DEFAULT_CREDITS_PER_GENERATE)
    except (TypeError, ValueError):
        parsed = float(DEFAULT_CREDITS_PER_GENERATE)
    if parsed <= 0:
        return DEFAULT_CREDITS_PER_GENERATE
    if parsed == int(parsed):
        return int(parsed)
    return parsed


def credits_to_songs(
    credits: int | float | None,
    *,
    credits_per_generate: int | float | None = None,
) -> int:
    """Whole generates × two versions. Leftover credits do not count as a song."""
    per = normalize_credits_per_generate(credits_per_generate)
    generates = int(max(0, int(credits or 0)) / float(per))
    return generates * SONGS_PER_GENERATE


def normalize_pricing_features(value: Any) -> list[str]:
    raw_lines: list[str] = []
    if isinstance(value, str):
        raw_lines = value.splitlines()
    elif isinstance(value, (list, tuple)):
        raw_lines = [str(item) for item in value]
    seen: set[str] = set()
    lines: list[str] = []
    for item in raw_lines:
        text = " ".join(str(item).split()).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        lines.append(text[:MAX_PRICING_FEATURE_LINE_LENGTH])
        if len(lines) >= MAX_PRICING_FEATURE_LINES:
            break
    return lines


def default_pricing_features(*, is_free: bool, daily_credits: int = 0) -> list[str]:
    if is_free:
        if int(daily_credits or 0) > 0:
            return list(DEFAULT_FREE_PRICING_FEATURES)
        return ["Web Create", "Top-up packs"]
    return list(DEFAULT_PAID_PRICING_FEATURES)


def default_pricing_credit_lines(
    *,
    monthly_credits: int = 0,
    daily_credits: int = 0,
    credits_per_generate: int | float | None = None,
) -> list[str]:
    daily = int(daily_credits or 0)
    monthly = int(monthly_credits or 0)
    if daily > 0:
        return [
            "daily credits",
            f"≈ {credits_to_songs(daily, credits_per_generate=credits_per_generate):,} songs/day",
            "Resets at midnight",
        ]
    if monthly > 0:
        return [
            "credits per month",
            f"≈ {credits_to_songs(monthly, credits_per_generate=credits_per_generate):,} songs/mo",
        ]
    return ["credits"]


def resolve_pricing_credit_lines(
    value: Any,
    *,
    monthly_credits: int = 0,
    daily_credits: int = 0,
    credits_per_generate: int | float | None = None,
) -> list[str]:
    stored = normalize_pricing_features(value)
    if stored:
        return stored
    return default_pricing_credit_lines(
        monthly_credits=monthly_credits,
        daily_credits=daily_credits,
        credits_per_generate=credits_per_generate,
    )


def is_free_plan(*, name: str = "", price_cents: int = 0, daily_credits: int = 0) -> bool:
    if int(price_cents or 0) <= 0 and "free" in (name or "").replace("_", " ").replace("-", " ").lower():
        return True
    return int(price_cents or 0) <= 0 and int(daily_credits or 0) > 0


def resolve_pricing_features(
    value: Any,
    *,
    name: str = "",
    price_cents: int = 0,
    daily_credits: int = 0,
) -> list[str]:
    stored = normalize_pricing_features(value)
    if stored:
        return stored
    return default_pricing_features(
        is_free=is_free_plan(name=name, price_cents=price_cents, daily_credits=daily_credits),
        daily_credits=daily_credits,
    )
