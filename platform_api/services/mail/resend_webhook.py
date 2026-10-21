"""Resend webhook verification and event mapping.

Resend signs deliveries with Svix: the secret is ``whsec_<base64 key>`` and the
headers are ``svix-id``, ``svix-timestamp`` and ``svix-signature``. The signed
content is ``{id}.{timestamp}.{body}``, HMAC-SHA256, base64. Multiple
space-separated ``v1,<sig>`` entries are accepted so key rotation does not break
in-flight deliveries.

Config-free and database-free so it can be unit-tested directly.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import time
from typing import Any

# Max accepted age/drift of a webhook timestamp, in seconds (±5 minutes).
TOLERANCE_SECONDS = 300

# Only delivery state is consumed. Opens and clicks come from our own signed
# pixel and redirect, so mapping them here would double-count every engagement.
EVENT_MAP = {
    "email.delivered": "delivered",
    "email.bounced": "bounced",
    "email.complained": "complained",
    "email.failed": "failed",
}


def _key(secret: str) -> bytes | None:
    raw = secret[len("whsec_") :] if secret.startswith("whsec_") else secret
    if not raw:
        return None
    try:
        key = base64.b64decode(raw)
    except (ValueError, TypeError):
        return None
    return key or None


def verify_signature(
    raw_body: bytes,
    *,
    svix_id: str | None,
    svix_timestamp: str | None,
    svix_signature: str | None,
    secret: str,
    now: float | None = None,
) -> bool:
    """Constant-time verification with a replay window."""
    if not secret or not svix_id or not svix_timestamp or not svix_signature:
        return False

    try:
        timestamp = int(svix_timestamp)
    except ValueError:
        return False

    current = time.time() if now is None else now
    if abs(current - timestamp) > TOLERANCE_SECONDS:
        return False

    key = _key(secret)
    if key is None:
        return False

    signed = f"{svix_id}.{svix_timestamp}.".encode() + raw_body
    expected = base64.b64encode(hmac.new(key, signed, hashlib.sha256).digest()).decode()

    for part in svix_signature.split(" "):
        version, _, value = part.partition(",")
        if version != "v1" or not value:
            continue
        if hmac.compare_digest(value, expected):
            return True
    return False


def map_event(payload: Any) -> dict[str, str | None] | None:
    """Return ``{type, email_id, recipient}`` or None for unhandled events."""
    if not isinstance(payload, dict):
        return None
    event_type = payload.get("type")
    data = payload.get("data")
    if not isinstance(event_type, str) or not isinstance(data, dict):
        return None

    mapped = EVENT_MAP.get(event_type)
    if mapped is None:
        return None

    email_id = data.get("email_id")
    if not isinstance(email_id, str) or not email_id:
        return None

    to = data.get("to")
    recipient = None
    if isinstance(to, list) and to and isinstance(to[0], str):
        recipient = to[0].strip().lower() or None

    return {"type": mapped, "email_id": email_id, "recipient": recipient}


def suppression_reason(event_type: str) -> str | None:
    if event_type == "bounced":
        return "bounce"
    if event_type == "complained":
        return "complaint"
    return None
