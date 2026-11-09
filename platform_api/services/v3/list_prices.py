"""Credits-page list prices for v3 ops.

Plans grant credits. They do not set what an operation costs.
"""

from __future__ import annotations

import logging
from typing import Any

from platform_api.services.credit_units import units_to_credits
from platform_api.services.pricing_display import DEFAULT_CREDITS_PER_GENERATE
from platform_api.services.v3.ops import PLAN_OP_COLUMNS, PRICING_FALLBACKS, SUPPORTED_OPS

logger = logging.getLogger(__name__)

# (ai_service, operation_type, sub_model) — sub_model None means the
# provider-wide default row (``sub_model = ''``).
PricingLookup = tuple[str, str, str | None]

OP_SCAN_ALIASES: dict[str, tuple[str, ...]] = {
    "lyric": ("lyric", "lyrics", "web_music_lyrics"),
    "title": ("title",),
    "album": ("album",),
    "music": ("music", "music_generation"),
    "style": ("style", "web_music_style"),
    "image": ("background_image", "thumbnail_image", "image"),
    "video": ("video", "video_manual"),
    "merge": ("video_merge", "merge"),
    "studio_edit": ("studio_edit",),
    "studio_stems_2": ("studio_stems_2",),
    "studio_stems_12": ("studio_stems_12",),
    "publish": ("upload", "publish"),
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


def _row_field(row: dict[str, Any], name: str) -> str:
    return str(row.get(name) or "").strip().lower()


async def _scan_pricing_units(
    pricing: Any,
    op: str,
    *,
    ai_service: str | None = None,
    operation_type: str | None = None,
) -> int | None:
    """Last-resort scan of every pricing row for an operation alias.

    The routed provider is tried first, then the concrete operation name, then
    the alias order. Charging the first unrelated row was how an image debit
    could silently land on another provider's price, so a cross-provider match
    is logged instead of being taken for granted.
    """
    getter = getattr(pricing, "get_all_pricing", None)
    if getter is None:
        return None
    rows = [row for row in (await getter()) or [] if isinstance(row, dict)]
    aliases = OP_SCAN_ALIASES.get(op, (op,))
    provider = str(ai_service or "").strip().lower()
    preferred = str(operation_type or "").strip().lower()

    targets = [name for name in (preferred, *aliases) if name]
    seen: set[str] = set()
    ordered_targets: list[str] = []
    for name in targets:
        if name not in seen:
            seen.add(name)
            ordered_targets.append(name)

    # Pass 1: routed provider. Pass 2: any provider.
    for restrict_provider in (True, False):
        if restrict_provider and not provider:
            continue
        for target in ordered_targets:
            for row in rows:
                if _row_field(row, "operation_type") != target:
                    continue
                row_provider = _row_field(row, "ai_service")
                if restrict_provider and row_provider != provider:
                    continue
                units = _row_units(row)
                if units is None:
                    continue
                if provider and row_provider != provider:
                    logger.warning(
                        "Pricing scan for op '%s' used %s/%s instead of routed %s "
                        "(no pricing row for the routed provider)",
                        op,
                        row_provider or "?",
                        target,
                        provider,
                    )
                return units
    return None


def _dedupe(chain: list[PricingLookup]) -> tuple[PricingLookup, ...]:
    seen: set[PricingLookup] = set()
    out: list[PricingLookup] = []
    for item in chain:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return tuple(out)


def _music_fallbacks(music_provider: str | None) -> tuple[PricingLookup, ...]:
    """Pricing lookup chain for ``music``.

    The routed provider (``suno`` / ``camxora_music_api``) wins so its row is
    charged; the static chain is the fallback for a provider that has no row
    configured yet.
    """
    fallbacks = PRICING_FALLBACKS["music"]
    provider = str(music_provider or "").strip().lower()
    if provider:
        return _dedupe(
            [
                (provider, "music", None),
                (provider, "music_generation", None),
                *fallbacks,
            ]
        )
    return fallbacks


def _image_fallbacks(
    image_provider: str | None,
    image_sub_model: str | None,
    image_operation: str | None,
) -> tuple[PricingLookup, ...]:
    """Pricing lookup chain for ``image``.

    ``background_image`` and ``thumbnail_image`` are separate routing
    assignments but both bill the single ``image`` op. The routed provider and
    model win so the debit matches the model that actually runs; the static
    chain is only a fallback for a provider with no configured row.
    """
    provider = str(image_provider or "").strip().lower()
    model = str(image_sub_model or "").strip() or None
    operation = str(image_operation or "").strip().lower()
    if operation not in {"background_image", "thumbnail_image"}:
        operation = "background_image"

    chain: list[PricingLookup] = []
    if provider:
        chain.extend(
            [
                (provider, operation, model),
                (provider, operation, None),
                (provider, "background_image", model),
                (provider, "thumbnail_image", model),
                (provider, "background_image", None),
                (provider, "thumbnail_image", None),
            ]
        )
    chain.extend(PRICING_FALLBACKS["image"])
    return _dedupe(chain)


def _fallbacks_for(
    op: str,
    *,
    music_provider: str | None,
    image_provider: str | None,
    image_sub_model: str | None,
    image_operation: str | None,
) -> tuple[PricingLookup, ...]:
    if op == "music":
        return _music_fallbacks(music_provider)
    if op == "image":
        return _image_fallbacks(image_provider, image_sub_model, image_operation)
    return PRICING_FALLBACKS[op]


async def resolve_op_list_units(
    pricing: Any,
    op: str,
    *,
    music_provider: str | None = None,
    image_provider: str | None = None,
    image_sub_model: str | None = None,
    image_operation: str | None = None,
) -> int:
    fallbacks = _fallbacks_for(
        op,
        music_provider=music_provider,
        image_provider=image_provider,
        image_sub_model=image_sub_model,
        image_operation=image_operation,
    )
    last_error: Exception | None = None
    for ai_service, operation_type, sub_model in fallbacks:
        try:
            units = await pricing.get_price(ai_service, operation_type, sub_model)
            return max(0, int(units))
        except Exception as exc:
            last_error = exc
            continue
    scanned = await _scan_pricing_units(
        pricing,
        op,
        ai_service=image_provider if op == "image" else None,
        operation_type=image_operation if op == "image" else None,
    )
    if scanned is not None:
        return scanned
    if last_error is not None:
        raise last_error
    return 0


async def resolve_op_list_credits(
    pricing: Any,
    op: str,
    *,
    music_provider: str | None = None,
    image_provider: str | None = None,
    image_sub_model: str | None = None,
    image_operation: str | None = None,
) -> float:
    return units_to_credits(
        await resolve_op_list_units(
            pricing,
            op,
            music_provider=music_provider,
            image_provider=image_provider,
            image_sub_model=image_sub_model,
            image_operation=image_operation,
        )
    )


async def resolve_all_op_list_credits(
    pricing: Any,
    *,
    music_provider: str | None = None,
    image_provider: str | None = None,
    image_sub_model: str | None = None,
) -> dict[str, float]:
    out: dict[str, float] = {}
    for op in SUPPORTED_OPS:
        try:
            out[op] = await resolve_op_list_credits(
                pricing,
                op,
                music_provider=music_provider,
                image_provider=image_provider,
                image_sub_model=image_sub_model,
            )
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
