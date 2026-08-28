"""Credits-page list prices for v3 ops.

Plans grant credits. They do not set what an operation costs.
"""

from __future__ import annotations

from typing import Any

from platform_api.services.credit_units import units_to_credits
from platform_api.services.pricing_display import DEFAULT_CREDITS_PER_GENERATE
from platform_api.services.v3.ops import PLAN_OP_COLUMNS, PRICING_FALLBACKS, SUPPORTED_OPS

OP_SCAN_ALIASES: dict[str, tuple[str, ...]] = {
    "lyric": ("lyric", "lyrics", "web_music_lyrics"),
    "title": ("title",),
    "album": ("album",),
    "music": ("music", "music_generation"),
    "style": ("style", "web_music_style"),
    "image": ("background_image", "thumbnail_image", "image"),
    "video": ("video", "video_manual"),
    "merge": ("video_merge", "merge"),
}


def _row_units(row: dict[str, Any]) -> int | None:
    raw = row.get("credits_per_operation")
    if raw is None:
        raw = row.get("credits")
    if raw is None:
        return None
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        return None


async def _scan_pricing_units(pricing: Any, op: str) -> int | None:
    getter = getattr(pricing, "get_all_pricing", None)
    if getter is None:
        return None
    rows = await getter()
    aliases = OP_SCAN_ALIASES.get(op, (op,))
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        operation = str(row.get("operation_type") or "").strip().lower()
        if operation not in aliases:
            continue
        units = _row_units(row)
        if units is not None:
            return units
    return None


async def resolve_op_list_units(pricing: Any, op: str) -> int:
    last_error: Exception | None = None
    for ai_service, operation_type in PRICING_FALLBACKS[op]:
        try:
            units = await pricing.get_price(ai_service, operation_type)
            return max(0, int(units))
        except Exception as exc:
            last_error = exc
            continue
    scanned = await _scan_pricing_units(pricing, op)
    if scanned is not None:
        return scanned
    if last_error is not None:
        raise last_error
    return 0


async def resolve_op_list_credits(pricing: Any, op: str) -> float:
    return units_to_credits(await resolve_op_list_units(pricing, op))


async def resolve_all_op_list_credits(pricing: Any) -> dict[str, float]:
    out: dict[str, float] = {}
    for op in SUPPORTED_OPS:
        try:
            out[op] = await resolve_op_list_credits(pricing, op)
        except Exception:
            continue
    return out


def music_credits_per_generate(op_credits: dict[str, float] | None) -> int | float:
    raw = (op_credits or {}).get("music")
    if raw is None:
        return DEFAULT_CREDITS_PER_GENERATE
    value = float(raw)
    if value <= 0:
        return DEFAULT_CREDITS_PER_GENERATE
    if value == int(value):
        return int(value)
    return value


def overlay_plan_list_prices(
    plan: dict[str, Any],
    op_credits: dict[str, float],
    *,
    overlay_ops: bool = False,
) -> dict[str, Any]:
    out = dict(plan)
    out["credits_per_generate"] = music_credits_per_generate(op_credits)
    if overlay_ops:
        for op, column in PLAN_OP_COLUMNS.items():
            if op not in op_credits:
                continue
            value = op_credits[op]
            out[column] = int(value) if float(value) == int(value) else value
    return out
