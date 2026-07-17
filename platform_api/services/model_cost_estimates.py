"""Estimate USD costs from registry cost tiers and operation token heuristics."""

from __future__ import annotations

import math
import re
from typing import Any

from platform_api.ai.registry import (
    IMAGE_MODEL_REGISTRY,
    SUNO_MUSIC_MODELS,
    TEXT_MODEL_REGISTRY,
    get_image_model_spec,
    get_music_model_spec,
    get_text_model_spec,
)
from platform_api.ai.types import (
    IMAGE_OPERATIONS,
    OPERATION_SERVICE_TYPE,
    TEXT_OPERATIONS,
    Operation,
    ServiceType,
)

_PER_1K_RE = re.compile(r"~\$([0-9.]+)\s*/\s*1k", re.IGNORECASE)
_PER_IMG_RE = re.compile(r"~\$([0-9.]+)\s*/\s*img", re.IGNORECASE)
_PAREN_USD_RE = re.compile(r"\(~\$([0-9.]+)\)")

# Rough output+input token budget per text operation (used for cost estimates).
TEXT_TOKEN_ESTIMATES: dict[str, int] = {
    "channel_name": 200,
    "channel_description": 500,
    "channel_keywords": 300,
    "channel_tags": 300,
    "lyric": 1200,
    "title": 180,
    "album": 180,
}

# Default USD per music generation (1 Suno request = Primary + Secondary package).
# Suno pack: 12 credits × $50/10k = $0.06 per request.
DEFAULT_MUSIC_COST_USD = 0.06
DEFAULT_MUSIC_COST_NOTES = "Suno pack: 12 credits x $50/10k = $0.06 per request"

_LEGACY_OPERATION_SERVICE_TYPE: dict[str, ServiceType] = {
    "music_generation": ServiceType.MUSIC_GENERATION,
    "text_generation": ServiceType.TEXT_GENERATION,
    "image_generation": ServiceType.IMAGE_GENERATION,
}


def _service_type_for_operation(operation_type: str) -> ServiceType | None:
    try:
        return OPERATION_SERVICE_TYPE[Operation(operation_type)]
    except ValueError:
        return _LEGACY_OPERATION_SERVICE_TYPE.get(operation_type)


def _suno_music_operations() -> list[str]:
    return ["music", "music_generation"]


def operation_types_for_model(ai_service: str, sub_model: str) -> list[str]:
    """Return operation types a registry model can perform (text, image, or music only)."""
    if ai_service == "suno":
        if not sub_model:
            return _suno_music_operations()
        if sub_model in SUNO_MUSIC_MODELS:
            return _suno_music_operations()
        if get_text_model_spec(ai_service, sub_model) is not None:
            if sub_model == "lyrics":
                return ["lyric"]
            return list(TEXT_OPERATIONS)

    if get_music_model_spec(ai_service, sub_model) is not None:
        return _suno_music_operations()

    if get_text_model_spec(ai_service, sub_model) is not None:
        return list(TEXT_OPERATIONS)
    if get_image_model_spec(ai_service, sub_model) is not None:
        return list(IMAGE_OPERATIONS)
    return []


def estimate_cost_usd(
    *,
    ai_service: str,
    sub_model: str,
    operation_type: str,
) -> float | None:
    """Return estimated provider cost in USD, or None if unknown."""
    allowed = operation_types_for_model(ai_service, sub_model)
    if operation_type not in allowed:
        return None

    service_type = _service_type_for_operation(operation_type)
    if service_type is None:
        return None

    if service_type == ServiceType.MUSIC_GENERATION:
        return DEFAULT_MUSIC_COST_USD

    spec = None
    if service_type == ServiceType.TEXT_GENERATION:
        spec = get_text_model_spec(ai_service, sub_model or None)
    elif service_type == ServiceType.IMAGE_GENERATION:
        spec = get_image_model_spec(ai_service, sub_model or None)

    if spec is None or not spec.cost_tier or spec.cost_tier.upper() == "SLAI":
        return None

    tier = spec.cost_tier.strip()
    per_1k = _PER_1K_RE.search(tier)
    if per_1k:
        rate_per_1k = float(per_1k.group(1))
        tokens = TEXT_TOKEN_ESTIMATES.get(operation_type, 300)
        return rate_per_1k * (tokens / 1000.0)

    per_img = _PER_IMG_RE.search(tier)
    if per_img:
        return float(per_img.group(1))

    paren_usd = _PAREN_USD_RE.search(tier)
    if paren_usd:
        return float(paren_usd.group(1))

    return None


def estimate_cost_usd_cents(
    *,
    ai_service: str,
    sub_model: str,
    operation_type: str,
) -> int | None:
    """Legacy helper: estimated cost rounded up to whole USD cents."""
    amount = estimate_cost_usd(
        ai_service=ai_service,
        sub_model=sub_model,
        operation_type=operation_type,
    )
    if amount is None:
        return None
    return max(0, int(math.ceil(amount * 100)))


def list_registry_model_pairs() -> list[dict[str, str]]:
    """Return every registered provider/model pair for seeding."""
    pairs: list[dict[str, str]] = []
    for provider, models in TEXT_MODEL_REGISTRY.items():
        for model_id in models:
            pairs.append({"ai_service": provider, "sub_model": model_id})
    for provider, models in IMAGE_MODEL_REGISTRY.items():
        for model_id in models:
            pairs.append({"ai_service": provider, "sub_model": model_id})
    for model_id in SUNO_MUSIC_MODELS:
        pairs.append({"ai_service": "suno", "sub_model": model_id})
    pairs.append({"ai_service": "suno", "sub_model": ""})
    return pairs


def build_seed_cost_rows() -> list[dict[str, Any]]:
    """Build suggested ai_model_costs rows from registry estimates."""
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for pair in list_registry_model_pairs():
        ai_service = pair["ai_service"]
        sub_model = pair["sub_model"]
        for operation_type in operation_types_for_model(ai_service, sub_model):
            key = (ai_service, sub_model, operation_type)
            if key in seen:
                continue
            seen.add(key)
            cost = estimate_cost_usd(
                ai_service=ai_service,
                sub_model=sub_model,
                operation_type=operation_type,
            )
            if cost is None:
                continue
            is_music = (
                _service_type_for_operation(operation_type)
                == ServiceType.MUSIC_GENERATION
            )
            rows.append(
                {
                    "ai_service": ai_service,
                    "sub_model": sub_model,
                    "operation_type": operation_type,
                    "cost_usd": cost,
                    "notes": (
                        DEFAULT_MUSIC_COST_NOTES
                        if is_music
                        else "Auto-estimated from registry cost tier"
                    ),
                    "source": "registry",
                }
            )
    return rows


def valid_registry_cost_keys() -> set[tuple[str, str, str]]:
    """Keys that are valid for registry-seeded model cost rows."""
    return {
        (row["ai_service"], row["sub_model"], row["operation_type"])
        for row in build_seed_cost_rows()
    }
