"""Free-tier premium previews for music.camxora.com.

A user whose only spendable credits are the Free plan grant (no paid
subscription, no purchased/admin pack credits) may generate V6 and V6_WILD,
but each model is capped to one *preview* per billing month. A preview is the
first 60 seconds of the track; buying a credit pack unlocks full-length
generation and downloads.

This module is intentionally pure so the product rules can be unit-tested
without a database. Reservation and usage counting live in
``WebMusicService`` because they need the shared pool.
"""

from __future__ import annotations

from typing import Any, Mapping

# Models a free user may try as a preview. V6_MINI is the everyday free model
# and is always generated in full, so it is never listed here.
PREVIEW_MODELS: tuple[str, ...] = ("V6", "V6_WILD")

# One preview per model per billing month.
PREVIEW_PER_MODEL_LIMIT = 1

# Delivered length for a preview, in seconds.
PREVIEW_SECONDS = 60

MODEL_LABELS: dict[str, str] = {
    "V6": "V6 Pro",
    "V6_MINI": "V6 Mini",
    "V6_WILD": "V6 Wild",
}


def normalize_model(model: str | None) -> str:
    return str(model or "").strip().upper()


def model_label(model: str | None) -> str:
    key = normalize_model(model)
    return MODEL_LABELS.get(key, key or "V6")


def is_preview_model(model: str | None) -> bool:
    return normalize_model(model) in PREVIEW_MODELS


def should_preview(
    model: str | None,
    *,
    is_paid: bool,
    has_pack_credits: bool,
) -> bool:
    """True when this generation must be delivered as a short preview.

    Paid subscribers and anyone holding purchased/admin credits get the full
    track. Everyone else is a free user: only the preview models are capped.
    """
    if is_paid or has_pack_credits:
        return False
    return is_preview_model(model)


def preview_quota_payload(
    used_by_model: Mapping[str, int],
    *,
    eligible: bool,
    per_model_limit: int = PREVIEW_PER_MODEL_LIMIT,
    seconds: int = PREVIEW_SECONDS,
) -> dict[str, Any]:
    """Serialize this month's preview allowance for the Create UI."""
    limit = max(1, int(per_model_limit))
    models: list[dict[str, Any]] = []
    for model in PREVIEW_MODELS:
        used = max(0, int(used_by_model.get(model, 0)))
        models.append(
            {
                "model": model,
                "label": model_label(model),
                "limit": limit,
                "used": min(used, limit),
                "remaining": max(0, limit - used),
                "seconds": int(seconds),
            }
        )
    return {
        "eligible": bool(eligible),
        "seconds": int(seconds),
        "models": models,
    }
