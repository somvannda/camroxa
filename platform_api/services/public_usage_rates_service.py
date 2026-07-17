"""Build public-facing credit usage rate rows from AI routing + pricing."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Protocol

from platform_api.services.credit_units import units_to_credits

USER_OPERATION_LABELS: dict[str, str] = {
    "lyric": "Lyrics (draft)",
    "title": "Title (draft)",
    "album": "Album name (draft)",
    "music": "Music — Suno package (Primary + Secondary channel)",
    "background_image": "Cover art (background)",
    "thumbnail_image": "Cover art (thumbnail)",
    "video": "Video generation (per track export)",
    "video_merge": "Auto merge video",
}

# Public overage rates aligned with plan meters (draft / song / image / video / merge).
PUBLIC_OPERATIONS = (
    "lyric",
    "title",
    "album",
    "music",
    "background_image",
    "thumbnail_image",
    "video",
    "video_merge",
)

# Local desktop ops (no AI routing) — prices seed as ai_service=local.
LOCAL_PUBLIC_OPS: dict[str, str] = {
    "video": "local",
    "video_merge": "local",
}


class RoutingServiceProtocol(Protocol):
    async def resolve(self, operation_type: str) -> Any: ...


class PricingServiceProtocol(Protocol):
    async def get_price(
        self, ai_service: str, operation_type: str, sub_model: str | None = None
    ) -> int: ...


async def build_public_usage_rates(
    *,
    routing_service: RoutingServiceProtocol,
    pricing_service: PricingServiceProtocol,
) -> dict[str, Any]:
    """Return user-safe operation credit costs resolved from admin routing."""
    items: list[dict[str, Any]] = []
    for operation_type in PUBLIC_OPERATIONS:
        label = USER_OPERATION_LABELS.get(
            operation_type, operation_type.replace("_", " ").title()
        )
        try:
            local_provider = LOCAL_PUBLIC_OPS.get(operation_type)
            if local_provider is not None:
                credits_units = await pricing_service.get_price(
                    local_provider, operation_type, None
                )
            else:
                routing = await routing_service.resolve(operation_type)
                credits_units = await pricing_service.get_price(
                    routing.provider, operation_type, routing.sub_model
                )
            items.append(
                {
                    "operation_type": operation_type,
                    "label": label,
                    "credits_per_operation": units_to_credits(credits_units),
                    "available": True,
                    "message": None,
                }
            )
        except Exception as exc:
            items.append(
                {
                    "operation_type": operation_type,
                    "label": label,
                    "credits_per_operation": None,
                    "available": False,
                    "message": str(exc),
                }
            )

    by_op = {item["operation_type"]: item for item in items}
    estimated_full_song = None
    # One song package overage ≈ lyric + title + album + one Suno (Primary + Secondary), not ×2 music.
    package_ops = ("lyric", "title", "album", "music")
    parts = [
        float(by_op[op]["credits_per_operation"])
        for op in package_ops
        if by_op.get(op)
        and by_op[op].get("available")
        and by_op[op].get("credits_per_operation") is not None
    ]
    if len(parts) == len(package_ops):
        estimated_full_song = round(sum(parts), 4)

    return {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "items": items,
        "estimated_full_song_credits": estimated_full_song,
        "disclaimer": (
            "Credit costs reflect current platform pricing and may change when admin "
            "updates model costs or routing. Subscription plans include monthly "
            "draft, Suno package, image, video, and merge allowances (account-wide). "
            "One Suno package = Primary + Secondary channel (two tracks) and is billed "
            "once. Video and merge are local (COGS $0) with account daily caps. "
            "Credit packs / overage use the per-operation rates shown."
        ),
    }
