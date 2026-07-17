"""Helpers for model-aware credit pricing keys."""

from __future__ import annotations


def normalize_pricing_sub_model(sub_model: str | None) -> str:
    """Empty string means provider-wide default pricing for an operation."""
    return str(sub_model or "").strip()


def normalize_suno_pricing_sub_model(sub_model: str | None) -> str:
    """Normalize Suno model ids to registry keys (per-model pricing)."""
    normalized = normalize_pricing_sub_model(sub_model)
    if not normalized:
        return ""
    key = normalized.upper().replace(".", "_").replace("-", "_")
    if key in {"V5_5", "V55"}:
        return "V5_5"
    if key == "V5":
        return "V5"
    return normalized


def pricing_lookup_key(
    ai_service: str,
    operation_type: str,
    sub_model: str | None = None,
) -> tuple[str, str, str]:
    return (
        str(ai_service or "").strip(),
        str(operation_type or "").strip(),
        normalize_pricing_sub_model(sub_model),
    )


def format_pricing_model_label(sub_model: str | None) -> str:
    """Human-readable label for admin UI."""
    normalized = normalize_pricing_sub_model(sub_model)
    return normalized if normalized else "Default (all models)"
