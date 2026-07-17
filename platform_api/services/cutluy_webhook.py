"""CutLuy webhook signature verification helpers (Phase 3).

Verifies ``X-CutLuy-Signature: t=<unix>,v1=<hex>`` as
HMAC-SHA256 of ``f"{t}.{raw_body}"`` with the endpoint signing secret.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from typing import Mapping


def parse_cutluy_signature_header(header: str | None) -> tuple[str | None, str | None]:
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


def verify_cutluy_webhook_signature(
    *,
    raw_body: bytes,
    signature_header: str | None,
    secret: str,
    max_age_seconds: int = 300,
    now: float | None = None,
) -> bool:
    """Return True when the CutLuy webhook signature is valid and fresh."""
    secret = (secret or "").strip()
    if not secret:
        return False
    timestamp, v1 = parse_cutluy_signature_header(signature_header)
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


def cutluy_event_type(headers: Mapping[str, str]) -> str | None:
    """Read ``X-CutLuy-Event`` from a case-insensitive header map."""
    for key, value in headers.items():
        if key.lower() == "x-cutluy-event":
            return value.strip() or None
    return None
