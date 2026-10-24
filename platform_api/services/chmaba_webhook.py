"""ChmabaPay webhook signature verification helpers.

ChmabaPay folds the signature into the ts/v1 (`Stripe`) header shape:

    X-ChmabaPay-Signature: t=<unix>,v1=<hex>

where ``v1`` is HMAC-SHA256 of ``f"{t}.{raw_body}"`` keyed by the endpoint's
``whsec_…`` secret. A timestamp outside the tolerance window is rejected so a
captured delivery cannot be replayed. The provider has no sandbox, so a webhook
that cannot be verified must never settle a payment.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any, Mapping

CHMABA_SIGNATURE_TOLERANCE_SECONDS = 300


def parse_chmaba_signature_header(header: str | None) -> tuple[str | None, str | None]:
    """Parse ``t=...,v1=...`` into (timestamp, v1_hex)."""
    if not header or not header.strip():
        return None, None
    parts: dict[str, str] = {}
    for piece in header.split(","):
        if "=" not in piece:
            continue
        key, value = piece.split("=", 1)
        parts[key.strip()] = value.strip()
    return parts.get("t"), parts.get("v1")


def verify_chmaba_webhook_signature(
    *,
    raw_body: bytes,
    signature_header: str | None,
    secret: str,
    max_age_seconds: int = CHMABA_SIGNATURE_TOLERANCE_SECONDS,
    now: float | None = None,
) -> bool:
    """Return True when the ChmabaPay signature is valid and fresh."""
    secret = (secret or "").strip()
    if not secret:
        return False
    timestamp, v1 = parse_chmaba_signature_header(signature_header)
    if not timestamp or not v1:
        return False
    try:
        ts = int(timestamp)
    except ValueError:
        return False

    current = time.time() if now is None else now
    if abs(current - ts) > max_age_seconds:
        return False

    expected = hmac.new(
        secret.encode("utf-8"),
        f"{timestamp}.".encode("utf-8") + raw_body,
        hashlib.sha256,
    ).hexdigest()

    try:
        return hmac.compare_digest(expected, v1)
    except (TypeError, ValueError):
        return False


def chmaba_event_type(headers: Mapping[str, str]) -> str | None:
    """Read ``X-ChmabaPay-Event`` from a case-insensitive header map."""
    for key, value in headers.items():
        if key.lower() == "x-chmabapay-event":
            return value.strip() or None
    return None


_MISSING = object()


def find_chmaba_reference_id(node: Any, depth: int = 0) -> str | None:
    """Return the first string under ``reference_id`` anywhere in an event.

    The delivery envelope is not documented field-by-field, so scanning for the
    id we set at checkout is what maps a webhook back to a local payment row.
    """
    if depth > 8 or node is None or not isinstance(node, (dict, list)):
        return None
    if isinstance(node, list):
        for item in node:
            found = find_chmaba_reference_id(item, depth + 1)
            if found:
                return found
        return None
    mapping: dict[str, Any] = node
    reference = mapping.get("reference_id", _MISSING)
    if isinstance(reference, str) and reference.strip():
        return reference.strip()
    for value in mapping.values():
        found = find_chmaba_reference_id(value, depth + 1)
        if found:
            return found
    return None


def chmaba_webhook_payload(raw_body: bytes) -> dict[str, Any]:
    """Decode a webhook body, returning an empty mapping for non-object JSON."""
    try:
        parsed = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}
