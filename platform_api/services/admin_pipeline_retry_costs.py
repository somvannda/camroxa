"""Estimated credit costs for admin Pipeline Ops retry confirms (P4.3)."""

from __future__ import annotations

from typing import Any

from platform_api.services.public_usage_rates_service import build_public_usage_rates


async def build_admin_retry_cost_estimates(
    *,
    routing_service: Any,
    pricing_service: Any,
) -> dict[str, Any]:
    """Resolve current list prices for draft / Suno / image retries."""
    rates = await build_public_usage_rates(
        routing_service=routing_service,
        pricing_service=pricing_service,
    )
    by_op = {
        str(item.get("operation_type") or ""): item
        for item in (rates.get("items") or [])
        if isinstance(item, dict)
    }

    def _credits(op: str) -> float | None:
        item = by_op.get(op) or {}
        if not item.get("available"):
            return None
        value = item.get("credits_per_operation")
        if value is None:
            return None
        try:
            return round(float(value), 4)
        except (TypeError, ValueError):
            return None

    lyric = _credits("lyric")
    title = _credits("title")
    album = _credits("album")
    music = _credits("music")
    background = _credits("background_image")
    thumbnail = _credits("thumbnail_image")

    draft_parts = [v for v in (lyric, title, album) if v is not None]
    draft_min = lyric
    draft_max = round(sum(draft_parts), 4) if draft_parts else None

    return {
        "updated_at": rates.get("updated_at"),
        "draft_credits_min": draft_min,
        "draft_credits_max": draft_max,
        "suno_credits": music,
        "background_image_credits": background,
        "thumbnail_image_credits": thumbnail,
        "operations": {
            "lyric": lyric,
            "title": title,
            "album": album,
            "music": music,
            "background_image": background,
            "thumbnail_image": thumbnail,
        },
        "disclaimer": (
            "Estimates use current routing/pricing. Plan allowance may cover the "
            "retry instead of wallet credits. Admin wallet is never charged."
        ),
    }
