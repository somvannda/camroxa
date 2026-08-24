"""Human-readable labels and metadata helpers for credit usage transactions."""

from __future__ import annotations

import json
import re
from typing import Any

from platform_api.services.credit_units import units_to_credits

_VIA_REASON_RE = re.compile(r"^(.+?) via (.+)$", re.IGNORECASE)

_REASON_LABELS: dict[str, str] = {
    "llm_draft": "Song draft",
    "suno_generation": "Music generation (Suno)",
    "suno_generation_failed": "Refund: Suno generation failed",
    "image_generation": "Image generation",
    "draft_generation_failed": "Refund: song draft failed",
    "draft_generation_error": "Refund: song draft error",
    "suno_invalid_response": "Refund: Suno invalid response",
    "image_generation_failed": "Refund: image generation failed",
    "image_invalid_provider": "Refund: unsupported image provider",
    "credit_pack_purchase": "Credit pack purchase",
    "lifetime_bonus": "Lifetime plan bonus credits",
    "admin_adjustment": "Admin wallet adjustment",
    "v3_music": "Music generation",
    "v3_lyric": "Lyrics generation",
    "v3_title": "Title generation",
    "v3_album": "Album name generation",
    "v3_style": "Style assist",
    "v3_image": "Image generation",
    "v3_video": "Video export",
    "v3_merge": "Video merge",
    "v3_period_grant": "Period grant",
    "v3_daily_grant": "Daily grant",
    "v3_grant_expire": "Grant expired",
    "v3_pack": "Credit pack",
    "v3_web_remaining": "Web leftover",
    "v3_refund_music": "Refund: music",
    "v3_refund_lyric": "Refund: lyrics",
    "v3_refund_style": "Refund: style",
}

_OPERATION_LABELS: dict[str, str] = {
    "song_draft": "Song draft",
    "title": "Title generation",
    "album": "Album name generation",
    "lyric": "Lyrics generation",
    "lyrics": "Lyrics generation",
    "music": "Music generation",
    "suno": "Music generation (Suno)",
    "image": "Image generation",
    "background_image": "Background image",
    "thumbnail_image": "Thumbnail image",
    "channel_setup": "Channel setup",
    "channel_name": "Channel name generation",
    "channel_logo": "Channel logo generation",
    "channel_cover": "Channel cover generation",
    "channel_description": "Channel description generation",
    "channel_keywords": "Channel keyword generation",
    "channel_tags": "Channel tag generation",
    "web_music_lyrics": "Music lyric generation",
    "web_music_style": "Music style tag generation",
    "text_generation": "Text generation",
    "style": "Style assist",
    "period_grant": "Period grant",
    "daily_grant": "Daily grant",
    "grant_expire": "Grant expired",
    "quota_conversion": "Leftover conversion",
    "web_remaining": "Web leftover",
    "pack": "Credit pack",
}


def _normalize_metadata(metadata: Any) -> dict[str, Any]:
    if metadata is None:
        return {}
    if isinstance(metadata, dict):
        return metadata
    if isinstance(metadata, str):
        try:
            parsed = json.loads(metadata)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def format_operation_label(operation: str | None) -> str | None:
    if not operation:
        return None
    key = operation.strip().lower()
    return _OPERATION_LABELS.get(key, operation.replace("_", " ").title())


def infer_purpose(reason: str, metadata: dict[str, Any] | None = None) -> str:
    meta = _normalize_metadata(metadata)
    purpose = str(meta.get("purpose") or "").strip()
    if purpose:
        return purpose

    operation = str(meta.get("operation") or "").strip()
    if operation:
        op_label = format_operation_label(operation)
        provider = str(meta.get("provider") or "").strip()
        model = str(meta.get("model") or meta.get("sub_model") or "").strip()
        if provider and model:
            return f"{op_label} ({provider} / {model})"
        if provider:
            return f"{op_label} ({provider})"
        return op_label or operation

    reason_key = (reason or "").strip()
    if reason_key in _REASON_LABELS:
        return _REASON_LABELS[reason_key]

    if reason_key.startswith("admin_adjustment:"):
        return reason_key.replace("admin_adjustment:", "Admin adjustment:", 1).strip()

    via_match = _VIA_REASON_RE.match(reason_key)
    if via_match:
        operation_type, provider = via_match.groups()
        op_label = format_operation_label(operation_type) or operation_type
        return f"{op_label} ({provider})"

    if reason_key:
        return reason_key.replace("_", " ").title()
    return "Credit transaction"


def _infer_legacy_draft_fields(amount_units: int, reason: str) -> dict[str, Any]:
    """Best-effort provider/model reconstruction for pre-metadata llm_draft rows."""
    if reason not in {"llm_draft", "draft_generation_failed", "draft_generation_error"}:
        return {}

    slai_lyric = 216
    slai_title = 32
    slai_album = 176
    provider = "slai"
    model = "xiaomi/mimo-v2.5-pro"

    def _item(operation: str, units: int) -> dict[str, Any]:
        return {
            "operation": operation,
            "provider": provider,
            "model": model,
            "sub_model": model,
            "amount_units": units,
        }

    line_items: list[dict[str, Any]] = []
    if amount_units == slai_lyric:
        line_items = [_item("lyric", slai_lyric)]
        purpose = "Song draft (lyrics only — legacy billing)"
    elif amount_units == slai_title + slai_lyric:
        line_items = [_item("title", slai_title), _item("lyric", slai_lyric)]
        purpose = "Song draft (title + lyrics)"
    elif amount_units == slai_title + slai_album + slai_lyric:
        line_items = [
            _item("title", slai_title),
            _item("album", slai_album),
            _item("lyric", slai_lyric),
        ]
        purpose = "Song draft (title + album + lyrics)"
    else:
        purpose = f"Song draft ({amount_units} units — legacy)"
        line_items = [_item("lyric", amount_units)]

    return {
        "purpose": purpose,
        "provider": provider,
        "model": model,
        "operation": "song_draft",
        "category": "generation",
        "line_items": line_items,
        "legacy": True,
    }


def extract_usage_fields(
    reason: str,
    metadata: dict[str, Any] | None = None,
    *,
    amount_units: int | None = None,
) -> dict[str, Any]:
    meta = _normalize_metadata(metadata)
    provider = str(meta.get("provider") or "").strip() or None
    model = str(meta.get("model") or meta.get("sub_model") or "").strip() or None
    operation = str(meta.get("operation") or meta.get("op") or "").strip() or None
    category = str(meta.get("category") or "").strip() or None
    line_items = meta.get("line_items")
    if not isinstance(line_items, list):
        line_items = []
    legacy = False
    legacy_fields: dict[str, Any] = {}

    if not provider or not operation:
        via_match = _VIA_REASON_RE.match((reason or "").strip())
        if via_match:
            operation = operation or via_match.group(1)
            provider = provider or via_match.group(2)

    if not operation:
        reason_key = (reason or "").strip()
        if reason_key.startswith("v3_refund_"):
            operation = reason_key.removeprefix("v3_refund_") or None
        elif reason_key.startswith("v3_"):
            operation = reason_key.removeprefix("v3_") or None
        elif reason_key == "llm_draft":
            operation = "song_draft"
        elif reason_key == "suno_generation":
            operation = "suno"
            provider = provider or "suno"
        elif reason_key == "image_generation":
            operation = "image"
        elif reason_key in {"draft_generation_failed", "draft_generation_error"}:
            operation = operation or "song_draft"

    if (not provider or not model or not line_items) and amount_units and not meta:
        legacy_fields = _infer_legacy_draft_fields(amount_units, reason)
        if legacy_fields:
            provider = provider or legacy_fields.get("provider")
            model = model or legacy_fields.get("model")
            operation = operation or legacy_fields.get("operation")
            category = category or legacy_fields.get("category")
            if not line_items:
                line_items = legacy_fields.get("line_items") or []
            legacy = True

    purpose = legacy_fields.get("purpose") or infer_purpose(reason, meta or legacy_fields)

    return {
        "purpose": purpose,
        "provider": provider,
        "model": model,
        "operation": operation,
        "category": category,
        "line_items": line_items,
        "legacy": legacy,
    }


def format_line_items_summary(line_items: list[Any]) -> str | None:
    if not line_items:
        return None
    parts: list[str] = []
    for item in line_items:
        if not isinstance(item, dict):
            continue
        operation = format_operation_label(str(item.get("operation") or "")) or "Item"
        provider = str(item.get("provider") or "").strip()
        model = str(item.get("model") or item.get("sub_model") or "").strip()
        amount_units = item.get("amount_units")
        amount_label = ""
        if isinstance(amount_units, (int, float)):
            amount_label = f" {units_to_credits(int(amount_units)):.6g} cr"
        slot = operation
        if provider and model:
            slot = f"{operation} ({provider}/{model})"
        elif provider:
            slot = f"{operation} ({provider})"
        parts.append(f"{slot}{amount_label}")
    return "; ".join(parts) if parts else None


def build_draft_usage_metadata(
    *,
    line_items: list[dict[str, Any]],
    forced_title: bool,
    forced_album: bool,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    primary = next(
        (item for item in line_items if item.get("operation") == "lyric"),
        line_items[0] if line_items else {},
    )
    provider = str(primary.get("provider") or "").strip()
    model = str(primary.get("model") or primary.get("sub_model") or "").strip() or None

    slot_labels = [format_operation_label(str(item.get("operation") or "")) or "item" for item in line_items]
    if slot_labels:
        purpose = f"Song draft ({' + '.join(slot_labels)})"
    elif forced_title and forced_album:
        purpose = "Song draft (lyrics only)"
    elif forced_title:
        purpose = "Song draft (album + lyrics)"
    elif forced_album:
        purpose = "Song draft (title + lyrics)"
    else:
        purpose = "Song draft (title + album + lyrics)"

    metadata: dict[str, Any] = {
        "category": "generation",
        "operation": "song_draft",
        "purpose": purpose,
        "provider": provider or None,
        "model": model,
        "line_items": line_items,
        "forced_title": forced_title,
        "forced_album": forced_album,
    }
    if extra:
        metadata.update({key: value for key, value in extra.items() if value is not None})
    return metadata


def build_legacy_metadata_backfill(
    *,
    amount_units: int,
    reason: str,
    trace: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Build persisted metadata for pre-metadata llm_draft credit rows."""
    legacy = _infer_legacy_draft_fields(amount_units, reason)
    if not legacy:
        return None

    line_items = legacy.get("line_items") or []
    operations = {str(item.get("operation") or "") for item in line_items if isinstance(item, dict)}
    forced_title = "title" not in operations and "lyric" in operations
    forced_album = "album" not in operations and "lyric" in operations

    extra: dict[str, Any] = {"legacy_backfill": True}
    if trace:
        extra.update({key: value for key, value in trace.items() if value is not None})

    return build_draft_usage_metadata(
        line_items=line_items,
        forced_title=forced_title,
        forced_album=forced_album,
        extra=extra,
    )


def build_generation_usage_metadata(
    *,
    operation: str,
    provider: str,
    model: str | None = None,
    purpose: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "category": "generation",
        "operation": operation,
        "provider": provider,
        "model": model,
        "purpose": purpose or infer_purpose(
            operation,
            {
                "operation": operation,
                "provider": provider,
                "model": model,
            },
        ),
    }
    if extra:
        metadata.update(extra)
    return metadata


def enrich_transaction_for_api(tx: dict[str, Any]) -> dict[str, Any]:
    reason = str(tx.get("reason") or "")
    metadata = _normalize_metadata(tx.get("metadata"))
    usage = extract_usage_fields(reason, metadata, amount_units=int(tx.get("amount") or 0))
    amount_units = int(tx.get("amount") or 0)
    direction = str(tx.get("direction") or "debit")
    signed_amount = units_to_credits(amount_units)
    if direction == "debit":
        signed_amount = -abs(signed_amount)
    elif direction == "credit":
        signed_amount = abs(signed_amount)

    line_items_summary = format_line_items_summary(usage["line_items"])
    billing = str(metadata.get("billing") or "").strip() or None
    list_credit_units = metadata.get("list_credit_units")
    charged_credit_units = metadata.get("charged_credit_units")
    coverage = str(metadata.get("coverage") or "").strip() or None

    return {
        **tx,
        "metadata": metadata or None,
        "amount": signed_amount,
        "amount_units": amount_units,
        "purpose": usage["purpose"],
        "provider": usage["provider"],
        "model": usage["model"],
        "operation": usage["operation"],
        "category": usage["category"],
        "line_items": usage["line_items"],
        "line_items_summary": line_items_summary,
        "legacy": usage.get("legacy", False),
        "billing": billing,
        "list_credit_units": list_credit_units,
        "charged_credit_units": charged_credit_units,
        "coverage": coverage,
        "batch_id": metadata.get("batch_id"),
        "song_id": metadata.get("song_id"),
        "batch_index": metadata.get("batch_index"),
        "attempts_used": metadata.get("attempts_used"),
        "llm_calls_title": metadata.get("llm_calls_title"),
        "llm_calls_album": metadata.get("llm_calls_album"),
        "llm_calls_lyric": metadata.get("llm_calls_lyric"),
        "source": metadata.get("source"),
    }
